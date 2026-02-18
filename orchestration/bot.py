"""
D&D AI Dungeon Master — Discord Bot Orchestrator

Wires together the vault-backed agent pipeline:
  MessageRouter → RulesLawyer → Storyteller → Chronicler (silent)

All state is persisted in the Obsidian vault via VaultManager.
"""

import os
import asyncio
import logging
import traceback
import discord
from discord.ext import commands
from dotenv import load_dotenv

from google import genai

# Core utilities
from tools.campaign_manager import CampaignManager
from tools.vault_manager import VaultManager
from tools.context_assembler import ContextAssembler
from tools.reference_manager import ReferenceManager
from tools.rate_limiter import gemini_limiter
from agents.tools.foundry_tool import FoundryClient, format_stat_block_text

# Agents — Live DM Team
from agents.board_monitor import BoardMonitorAgent
from agents.rules_lawyer import RulesLawyerAgent
from agents.storyteller import StorytellerAgent
from agents.foundry_architect import FoundryArchitectAgent
from agents.message_router import MessageRouterAgent, MessageType
from agents.chronicler import ChroniclerAgent
from tools.scene_classifier import classify_scene_changes
from tools.blind_prep import run_blind_prep, BlindPrepResult

# Agents — Prep Team
from agents.world_architect import WorldArchitectAgent
from agents.campaign_planner import CampaignPlannerAgent
from agents.prep_router import PrepRouterAgent, PrepIntent
from agents.cartographer import CartographerAgent

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')
MODERATOR_LOG_CHANNEL_ID = os.getenv('MODERATOR_LOG_CHANNEL_ID')
WAR_ROOM_CHANNEL_ID = os.getenv('WAR_ROOM_CHANNEL_ID')
GAME_TABLE_CHANNEL_ID = os.getenv('GAME_TABLE_CHANNEL_ID')

# Player-to-Character mapping: discord_username -> character_name
# Format in .env: PLAYER_MAP=username1:Character One,username2:Character Two
PLAYER_MAP = {}
raw_map = os.getenv('PLAYER_MAP', '')
if raw_map:
    for pair in raw_map.split(','):
        pair = pair.strip()
        if ':' in pair:
            discord_name, char_name = pair.split(':', 1)
            PLAYER_MAP[discord_name.strip().lower()] = char_name.strip()

# Configure Logging
if not os.path.exists('logs'):
    os.makedirs('logs')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.FileHandler('logs/dnd_bot.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger('DND_Bot')

# ---------------------------------------------------------------------------
# Gemini Client
# ---------------------------------------------------------------------------
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment.")
    client = None
else:
    client = genai.Client(api_key=GEMINI_API_KEY)

MODEL_ID = "gemini-2.0-flash"

# ---------------------------------------------------------------------------
# Vault & Context (the new state backbone)
# ---------------------------------------------------------------------------
# Initialize Campaign Manager & Ensure Migration
campaign_manager = CampaignManager(root_dir=".")
campaign_manager.ensure_migration()

vault = VaultManager(vault_path="campaign_vault")
ref_manager = ReferenceManager()
context_assembler = ContextAssembler(vault, reference_manager=ref_manager)
logger.info(f"ReferenceManager: {ref_manager.get_stats()}")

# ---------------------------------------------------------------------------
# Foundry VTT Connection
# ---------------------------------------------------------------------------
foundry_client = FoundryClient()
if foundry_client.api_key:
    if foundry_client.connect():
        logger.info(f"Foundry VTT connected: client={foundry_client.client_id}")
    else:
        logger.warning("Foundry VTT connection failed — running without live board data.")
else:
    logger.info("Foundry VTT disabled (no API key set).")

# ---------------------------------------------------------------------------
# Agents — Live DM Team (Game Table channel)
# ---------------------------------------------------------------------------
board_monitor = BoardMonitorAgent(client, foundry=foundry_client)
rules_lawyer = RulesLawyerAgent(client, context_assembler, model_id=MODEL_ID)
storyteller = StorytellerAgent(client, context_assembler, model_id=MODEL_ID)
foundry_architect = FoundryArchitectAgent(client, foundry=foundry_client, model_id=MODEL_ID)
message_router = MessageRouterAgent(client, context_assembler, model_id=MODEL_ID)
chronicler = ChroniclerAgent(client, vault, context_assembler, model_id=MODEL_ID)

# ---------------------------------------------------------------------------
# Agents — Prep Team (War Room channel)
# ---------------------------------------------------------------------------
world_architect = WorldArchitectAgent(client, vault, context_assembler, model_id=MODEL_ID)
campaign_planner = CampaignPlannerAgent(client, vault, context_assembler, model_id=MODEL_ID)
prep_router = PrepRouterAgent(client, context_assembler, model_id=MODEL_ID)
cartographer_agent = CartographerAgent(client, foundry=foundry_client, vault=vault, model_id=MODEL_ID, output_dir=os.path.join(vault.vault_path, "Assets", "Maps"))

# Set the starting location from the world clock / vault
_world_clock = vault.read_world_clock()
_start_location = _world_clock.get('current_location', 'The Yawning Portal') if _world_clock else 'The Yawning Portal'
storyteller.set_location(_start_location)
logger.info(f"Starting location: {_start_location}")

# Track current session number
current_session = context_assembler.current_session

# Restore conversation memory from last checkpoint (survives bot restarts)
context_assembler.load_checkpoint()
logger.info("Memory checkpoint loaded.")

# ---------------------------------------------------------------------------
# Discord Bot
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix='!', intents=intents)


async def send_to_moderator_log(content: str):
    """Send a message to the moderator log channel."""
    if not MODERATOR_LOG_CHANNEL_ID:
        logger.warning("MODERATOR_LOG_CHANNEL_ID not set — logging error locally only.")
        logger.error(content)
        return

    try:
        channel = bot.get_channel(int(MODERATOR_LOG_CHANNEL_ID))
        if channel is None:
            logger.warning(f"Could not find moderator log channel {MODERATOR_LOG_CHANNEL_ID}")
            logger.error(content)
            return

        for i in range(0, len(content), 1900):
            chunk = content[i:i + 1900]
            await channel.send(f"```\n{chunk}\n```")
    except Exception as e:
        logger.error(f"Failed to send to moderator log: {e}")
        logger.error(content)


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    logger.info(f'Logged in as {bot.user.name} ({bot.user.id})')
    logger.info(f'Vault path: {vault.vault_path}')
    logger.info(f'Current session: {current_session}')
    print('D&D AI System Online. Vault-backed state is active.')


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------
@bot.group(name='campaign', invoke_without_command=True)
async def campaign_cmd(ctx):
    """Manage campaigns.
    Usage: !campaign list
           !campaign new <name>
           !campaign load <name>
    """
    await ctx.send("available subcommands: `list`, `new`, `load`")

@campaign_cmd.command(name='list')
async def campaign_list(ctx):
    """List all available campaigns."""
    campaigns = campaign_manager.list_campaigns()
    active = campaign_manager.get_active_campaign()
    
    lines = ["**Available Campaigns:**"]
    for c in campaigns:
        icon = "🟢" if c == active else "⚪"
        lines.append(f"{icon} {c}")
    
    await ctx.send('\n'.join(lines))

@campaign_cmd.command(name='new')
async def campaign_new(ctx, *, name: str):
    """Create a new campaign."""
    # Sanitize name slightly to prevent path issues
    safe_name = "".join(c for c in name if c.isalnum() or c in " -_").strip()
    if not safe_name:
        await ctx.send("❌ Invalid campaign name.")
        return

    if campaign_manager.create_campaign(safe_name):
        await ctx.send(f"✅ Created campaign **{safe_name}**. Use `!campaign load {safe_name}` to switch.")
    else:
        await ctx.send(f"❌ Failed to create campaign **{safe_name}**. It might already exist.")

@campaign_cmd.command(name='load')
async def campaign_load(ctx, *, name: str):
    """Switch to a different campaign."""
    if campaign_manager.set_campaign(name):
        # We need to clear the in-memory caches of our agents
        context_assembler.history.clear()
        
        # Reload world clock to check if it's a fresh campaign
        clock = vault.read_world_clock()
        loc = clock.get('current_location', 'Unknown')
        storyteller.set_location(loc)
        
        await ctx.send(f"✅ **Loaded Campaign: {name}**\n📍 Location: {loc}\n📝 Memory cleared for new context.")
    else:
        await ctx.send(f"❌ Failed to load campaign **{name}**. Does it exist?")

@bot.command(name='save')
async def save_game(ctx):
    """Confirm that the game state is saved."""
    # Since we use a file-based vault, it is always saved. 
    # This is mostly for player peace of mind or forcing a git commit if we added that later.
    await ctx.send("💾 **Game Saved.** (Vault state is persistent)")


@bot.command(name='reset')
async def reset_game(ctx):
    """Resets agent state (conversation history). Vault data is preserved.
    Usage: !reset
    """
    # Safety confirmation
    await ctx.send("⚠️ This will clear the conversation memory (history will decay). "
                   "Vault files are **not** affected.\nReact with ✅ to confirm or ❌ to cancel.")
    
    confirm_msg = await ctx.send("Waiting for confirmation...")
    await confirm_msg.add_reaction('✅')
    await confirm_msg.add_reaction('❌')
    
    def check(reaction, user):
        return user == ctx.author and str(reaction.emoji) in ['✅', '❌'] and reaction.message.id == confirm_msg.id
    
    try:
        reaction, _ = await bot.wait_for('reaction_add', timeout=30.0, check=check)
        
        if str(reaction.emoji) == '✅':
            context_assembler.history.clear()
            logger.info(f"Conversation history cleared by {ctx.author}")
            await ctx.send("✅ **Memory cleared.** Vault data intact. Ready to continue! 🎲")
        else:
            await ctx.send("❌ Reset cancelled.")
    except Exception:
        await ctx.send("⏰ Reset timed out — no changes made.")


@bot.command(name='recap')
async def recap(ctx, session_num: int = None):  # type: ignore[assignment]
    """Shows a recap of the specified session (or the latest).
    Usage: !recap [session_number]
    """
    try:
        if session_num is not None:
            result = vault.get_session(session_num)
            if not result:
                await ctx.send(f"❌ Session {session_num} not found.")
                return
            fm, body = result
        else:
            result = vault.get_latest_session()
            if not result:
                await ctx.send("❌ No session logs found.")
                return
            fm, body = result

        # Build a concise recap
        session_title = f"Session {fm.get('session_number', '?')}"
        date = fm.get('ingame_date', '?')
        location = fm.get('location', '?')
        
        # Extract just the Summary section
        summary = ""
        in_summary = False
        for line in body.split('\n'):
            if line.strip().startswith('## Summary'):
                in_summary = True
                continue
            if line.strip().startswith('## ') and in_summary:
                break
            if in_summary:
                summary += line + '\n'
        
        recap_text = (
            f"📜 **{session_title}** — {date} @ {location}\n\n"
            f"{summary.strip()}"
        )
        
        if len(recap_text) > 2000:
            recap_text = recap_text[:1997] + "..."
        
        await ctx.send(recap_text)
    except Exception as e:
        logger.error(f"Recap command failed: {e}", exc_info=True)
        await ctx.send("⚠️ Couldn't generate recap. Check the log.")


@bot.command(name='status')
async def party_status(ctx):
    """Shows current party status from the vault.
    Usage: !status
    """
    try:
        party = vault.get_party_state()
        if not party:
            await ctx.send("❌ No party data found in the vault.")
            return
        
        clock = vault.read_world_clock()
        status_lines = [
            f"⏰ **{clock.get('current_date', '?')}** — {clock.get('time_of_day', '?')}",
            ""
        ]
        
        for member in party:
            fm = member['frontmatter']
            name = fm.get('name', '?')
            hp_cur = fm.get('hp_current', '?')
            hp_max = fm.get('hp_max', '?')
            ac = fm.get('ac', '?')
            conditions = fm.get('conditions', [])
            cond_str = f" | ⚡ {', '.join(conditions)}" if conditions else ""
            
            status_lines.append(f"🛡️ **{name}** — HP: {hp_cur}/{hp_max} | AC: {ac}{cond_str}")
        
        # Active quests
        quests = vault.get_active_quests()
        if quests:
            status_lines.append("")
            status_lines.append("📋 **Active Quests:**")
            for q in quests:
                qfm = q['frontmatter']
                status_lines.append(f"  • {qfm.get('name', '?')} ({qfm.get('status', '?')})")
        
        await ctx.send('\n'.join(status_lines))
    except Exception as e:
        logger.error(f"Status command failed: {e}", exc_info=True)
        await ctx.send("⚠️ Couldn't fetch status. Check the log.")


@bot.command(name='setup')
async def setup_encounter(ctx, *, prompt: str):
    """Sets up an encounter in Foundry VTT.
    Usage: !setup A group of 3 goblins ambushing from the trees
    """
    logger.info(f"Received setup command from {ctx.author}: {prompt}")
    await ctx.send("🏗️ Architect is drafting plans...")
    try:
        response = str(await foundry_architect.process_request(prompt))
        if len(response) > 2000:
            for i in range(0, len(response), 2000):
                await ctx.send(response[i:i+2000])
        else:
            await ctx.send(response)
    except Exception as e:
        logger.error(f"Setup command failed: {e}")
        await send_to_moderator_log(
            f"[!setup] Error from {ctx.author}:\n"
            f"Prompt: {prompt}\n"
            f"{traceback.format_exc()}"
        )
        await ctx.send("⚠️ Something went wrong setting up the encounter. The DM has been notified.")


@bot.command(name='image')
async def image_search(ctx, *, query: str):
    """Search for images from D&D source books and send them.
    Usage: !image troll
    Usage: !image yawning portal map
    """
    logger.info(f"Image search from {ctx.author}: {query}")
    
    try:
        results = ref_manager.find_asset(query, max_results=3)
        
        if not results:
            await ctx.send(f"🔍 No images found for **{query}**. Try different keywords.")
            return
        
        for asset in results:
            filepath = asset['file']
            if not os.path.exists(filepath):
                logger.warning(f"Asset file not found: {filepath}")
                continue
            
            # Build a nice embed
            book_name = asset['book_slug'].replace('_', ' ').title()
            embed = discord.Embed(
                title=f"📖 {book_name} — Page {asset['page']}",
                description=asset.get('context', '')[:200],
                color=0x7B2D26  # D&D red
            )
            embed.set_footer(text=f"{asset['width']}×{asset['height']}px | {asset['size_bytes'] // 1024} KB")
            
            file = discord.File(filepath, filename=os.path.basename(filepath))
            embed.set_image(url=f"attachment://{os.path.basename(filepath)}")
            
            await ctx.send(embed=embed, file=file)
        
    except Exception as e:
        logger.error(f"Image search failed: {e}", exc_info=True)
        await ctx.send("⚠️ Image search failed. Check the log.")


# ---------------------------------------------------------------------------
# Foundry VTT Commands
# ---------------------------------------------------------------------------
@bot.command(name='roll')
async def roll_cmd(ctx, *, expression: str):
    """Roll dice using Foundry's dice engine.
    Usage: !roll 1d20+5 attack roll
    Usage: !roll 4d6kh3
    Usage: !roll 8d6 fireball
    """
    # Split formula from optional reason
    parts = expression.split(None, 1)
    formula = parts[0]
    reason = parts[1] if len(parts) > 1 else ''

    if not foundry_client.is_connected:
        # Fallback: basic dice roll message
        await ctx.send("⚠️ Foundry VTT not connected. Cannot roll dice remotely.")
        return

    try:
        result = foundry_client.roll_dice(formula)
        total = result['total']
        is_crit = result.get('isCritical', False)
        is_fumble = result.get('isFumble', False)

        # Format individual dice results
        dice_details = []
        for die_group in result.get('dice', []):
            faces = die_group.get('faces', '?')
            rolls = [r.get('result', '?') for r in die_group.get('results', [])]
            active = [r.get('result', '?') for r in die_group.get('results', []) if r.get('active', True)]
            if len(rolls) != len(active):
                dice_details.append(f"d{faces}: [{', '.join(str(r) for r in rolls)}] → kept {active}")
            else:
                dice_details.append(f"d{faces}: [{', '.join(str(r) for r in rolls)}]")

        # Build the response
        reason_str = f" ({reason})" if reason else ''
        dice_str = ' '.join(dice_details) if dice_details else ''

        if is_crit:
            response = f"🎲 **NAT 20!** 🌟 `{formula}`{reason_str}: **{total}** {dice_str}"
        elif is_fumble:
            response = f"🎲 **NAT 1!** 💀 `{formula}`{reason_str}: **{total}** {dice_str}"
        else:
            response = f"🎲 `{formula}`{reason_str}: **{total}** {dice_str}"

        await ctx.send(response)
    except Exception as e:
        logger.error(f"Roll command failed: {e}", exc_info=True)
        await ctx.send(f"⚠️ Roll failed: {e}")


@bot.command(name='monster')
async def monster_cmd(ctx, *, name: str):
    """Look up a monster's stat block.
    Usage: !monster goblin
    Usage: !monster ancient red dragon
    """
    if not foundry_client.is_connected:
        await ctx.send("⚠️ Foundry VTT not connected.")
        return

    try:
        async with ctx.typing():
            results = foundry_client.search_actors(name)
            if not results:
                await ctx.send(f"🔍 No monsters found for **{name}**.")
                return

            # Use the first result
            actor = results[0]
            uuid = actor.get('uuid', '')
            stat = foundry_client.get_actor_stat_block(uuid)

            # Format as Discord embed
            ab = stat.get('abilities', {})
            ab_line = ' | '.join(
                f"**{a.upper()}** {ab[a]['value']}({ab[a]['mod']:+d})"
                for a in ['str', 'dex', 'con', 'int', 'wis', 'cha']
                if a in ab
            )

            hp = stat.get('hp', {})
            hp_str = f"{hp.get('max', '?')}"
            if hp.get('formula'):
                hp_str += f" ({hp['formula']})"

            mv = stat.get('movement', {})
            speed: str = str(mv.get('walk', '30')) + ' ft.'
            for mode in ['fly', 'swim', 'climb', 'burrow']:
                if mv.get(mode) and mv[mode] != '0':
                    speed += f", {mode} {mv[mode]} ft."

            embed = discord.Embed(
                title=f"📋 {stat['name']}",
                description=f"*{stat.get('type', 'npc').title()}* | CR {stat.get('cr', '?')}",
                color=0xCC0000
            )
            embed.add_field(name="HP", value=hp_str, inline=True)
            embed.add_field(name="AC", value=str(stat.get('ac', '?')), inline=True)
            embed.add_field(name="Speed", value=speed, inline=True)
            embed.add_field(name="Abilities", value=ab_line, inline=False)

            features = stat.get('features', [])
            if features:
                embed.add_field(
                    name="Features",
                    value=', '.join(features[:15]),
                    inline=False
                )

            equipment = stat.get('equipment', [])
            if equipment:
                embed.add_field(
                    name="Equipment",
                    value=', '.join(equipment[:10]),
                    inline=False
                )

            spells = stat.get('spells', [])
            if spells:
                spell_text = ', '.join(s['name'] for s in spells[:15])
                embed.add_field(name="Spells", value=spell_text, inline=False)

            # Show other matches
            if len(results) > 1:
                others = ', '.join(r['name'] for r in results[1:5])
                embed.set_footer(text=f"Also found: {others}")

            await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Monster command failed: {e}", exc_info=True)
        await ctx.send(f"⚠️ Monster lookup failed: {e}")


@bot.command(name='scene')
async def scene_cmd(ctx, *, query: str):
    """Search for battle maps / scenes.
    Usage: !scene forest
    Usage: !scene cave entrance
    Usage: !scene tavern
    """
    if not foundry_client.is_connected:
        await ctx.send("⚠️ Foundry VTT not connected.")
        return

    try:
        async with ctx.typing():
            results = foundry_client.search_scenes(query)
            if not results:
                await ctx.send(f"🔍 No scenes found for **{query}**.")
                return

            embed = discord.Embed(
                title=f"🗺️ Scenes matching '{query}'",
                description=f"Found {len(results)} scene(s)",
                color=0x2E8B57
            )

            for scene in results[:10]:
                source = scene.get('packageName', 'World')
                embed.add_field(
                    name=scene['name'],
                    value=f"📦 {source}\n`{scene.get('uuid', 'N/A')}`",
                    inline=True
                )

            if len(results) > 10:
                embed.set_footer(text=f"Showing 10 of {len(results)} results")

            await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Scene command failed: {e}", exc_info=True)
        await ctx.send(f"⚠️ Scene search failed: {e}")


@bot.command(name='pc')
async def pc_cmd(ctx, *, name: str):
    """Look up a player character or any actor's details.
    Usage: !pc Krusk
    Usage: !pc Player Character 1
    """
    if not foundry_client.is_connected:
        await ctx.send("⚠️ Foundry VTT not connected.")
        return

    try:
        async with ctx.typing():
            # First search for the actor
            results = foundry_client.search_actors(name)
            if not results:
                await ctx.send(f"🔍 No character found for **{name}**. Try a different name.")
                return

            actor = results[0]
            uuid = actor.get('uuid', '')
            stat = foundry_client.get_actor_stat_block(uuid)

            # Build a character-focused embed
            ab = stat.get('abilities', {})
            ab_line = ' | '.join(
                f"**{a.upper()}** {ab[a]['value']}({ab[a]['mod']:+d})"
                for a in ['str', 'dex', 'con', 'int', 'wis', 'cha']
                if a in ab
            )

            hp = stat.get('hp', {})
            hp_str = f"{hp.get('current', '?')}/{hp.get('max', '?')}"

            char_type = stat.get('type', 'character').title()
            details = stat.get('details', {})
            race = details.get('race', {}) if isinstance(details.get('race'), dict) else {}
            race_name = race.get('name', '') if race else ''
            level_info = details.get('level', '')

            desc = f"*{char_type}*"
            if race_name:
                desc += f" | {race_name}"
            if level_info:
                desc += f" | Level {level_info}"

            embed = discord.Embed(
                title=f"🧙 {stat['name']}",
                description=desc,
                color=0x4169E1
            )
            embed.add_field(name="HP", value=hp_str, inline=True)
            embed.add_field(name="AC", value=str(stat.get('ac', '?')), inline=True)
            embed.add_field(name="Abilities", value=ab_line, inline=False)

            # Spells (grouped by level)
            spells = stat.get('spells', [])
            if spells:
                by_level: dict[int, list[str]] = {}
                for s in spells:
                    lvl = s.get('level', 0)
                    by_level.setdefault(lvl, []).append(s['name'])
                spell_lines = []
                for lvl in sorted(by_level.keys()):
                    label = "Cantrips" if lvl == 0 else f"Lvl {lvl}"
                    spell_lines.append(f"**{label}:** {', '.join(by_level[lvl])}")
                spell_text = '\n'.join(spell_lines)
                if len(spell_text) > 1024:
                    spell_text = spell_text[:1021] + '...'
                embed.add_field(name="Spells", value=spell_text, inline=False)

            # Features
            features = stat.get('features', [])
            if features:
                feat_text = ', '.join(features[:20])
                if len(feat_text) > 1024:
                    feat_text = feat_text[:1021] + '...'
                embed.add_field(name="Features", value=feat_text, inline=False)

            # Equipment
            equipment = stat.get('equipment', [])
            if equipment:
                equip_text = ', '.join(equipment[:15])
                if len(equip_text) > 1024:
                    equip_text = equip_text[:1021] + '...'
                embed.add_field(name="Equipment", value=equip_text, inline=False)

            await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"PC command failed: {e}", exc_info=True)
        await ctx.send(f"⚠️ Character lookup failed: {e}")


@bot.command(name='prep')
async def prep_cmd(ctx, *, description: str):
    """Blind session prep — AI prepares scenes, NPCs, and encounters without spoilers.
    Usage: !prep The party is heading toward the Zhentarim warehouse
    Usage: !prep forest ambush on the road to Neverwinter
    """
    logger.info(f"Blind prep from {ctx.author}: {description}")
    await ctx.send("🧙 **Blind Prep Started** — AI is preparing your session...")
    await ctx.send("*Spoiler-free details will appear in the moderator log.*")

    try:
        async with ctx.typing():
            prep_result = await run_blind_prep(
                description=description,
                campaign_planner=campaign_planner,
                world_architect=world_architect,
                foundry_architect=foundry_architect,
                cartographer=cartographer_agent,
                foundry_client=foundry_client,
                gemini_client=client,
                model_id=MODEL_ID,
                vault=vault,
            )

        # Send spoiler details to moderator log ONLY
        if prep_result.details:
            await send_to_moderator_log(prep_result.details)

        # Send non-spoiler summary to the player
        embed = discord.Embed(
            title="✅ Session Prep Complete",
            description=prep_result.summary,
            color=0x2ECC71
        )
        embed.set_footer(text="Check the moderator log for full prep details.")
        await ctx.send(embed=embed)

    except Exception as e:
        logger.error(f"Blind prep failed: {e}", exc_info=True)
        await send_to_moderator_log(f"[!prep] Error: {traceback.format_exc()}")
        await ctx.send("⚠️ Prep encountered an error. Check the moderator log.")


@bot.command(name='daytime')
async def daytime_cmd(ctx):
    """Set the active scene to daytime lighting.
    Usage: !daytime
    """
    if not foundry_client.is_connected:
        await ctx.send("⚠️ Foundry VTT not connected.")
        return

    try:
        scenes = foundry_client.get_world_scenes()
        if not scenes:
            await ctx.send("⚠️ No scenes found in the world.")
            return

        # Update all world scenes (typically you'd want the active one)
        for scene in scenes:
            foundry_client.update_scene_lighting(scene['uuid'], darkness=0.0)

        await ctx.send("☀️ **Daytime!** Scene lighting set to full brightness.")
    except Exception as e:
        logger.error(f"Daytime command failed: {e}", exc_info=True)
        await ctx.send(f"⚠️ Failed to set daytime: {e}")


@bot.command(name='nighttime')
async def nighttime_cmd(ctx):
    """Set the active scene to nighttime lighting.
    Usage: !nighttime
    """
    if not foundry_client.is_connected:
        await ctx.send("⚠️ Foundry VTT not connected.")
        return

    try:
        scenes = foundry_client.get_world_scenes()
        if not scenes:
            await ctx.send("⚠️ No scenes found in the world.")
            return

        for scene in scenes:
            foundry_client.update_scene_lighting(scene['uuid'], darkness=1.0)

        await ctx.send("🌙 **Nighttime!** Scene lighting set to darkness.")
    except Exception as e:
        logger.error(f"Nighttime command failed: {e}", exc_info=True)
        await ctx.send(f"⚠️ Failed to set nighttime: {e}")


@bot.command(name='build')
async def build_cmd(ctx, *, description: str):
    """
    Build an encounter on a scene — searches for monsters, picks a map,
    and places tokens at tactical positions.
    Usage: !build 4 goblins ambush the party in a forest clearing
    Usage: !build boss fight — troll in a cave with 2 goblin minions
    """
    if not foundry_client.is_connected:
        await ctx.send("⚠️ Foundry VTT not connected.")
        return

    logger.info(f"Build command from {ctx.author}: {description}")
    status_msg = await ctx.send("🏗️ **Encounter Builder** — Analyzing your request...")

    try:
        async with ctx.typing():
            # Step 1: Use AI to extract monsters, scene, and positioning
            build_prompt = f"""You are an encounter builder for D&D 5e using Foundry VTT.
Analyze this encounter description and produce a JSON plan.

Description: {description}

Return a JSON object with:
{{
    "scene_keywords": ["keyword1", "keyword2"],
    "monsters": [
        {{"name": "Goblin", "count": 4, "role": "ambusher"}},
        {{"name": "Hobgoblin Captain", "count": 1, "role": "leader"}}
    ],
    "formation": "ambush|defensive|scattered|clustered|surrounding",
    "lighting": 0.0
}}

Rules:
- scene_keywords: 2-3 words to search for battle maps (e.g. "forest", "cave", "tavern")
- monsters: Use standard D&D 5e monster names that would be in the SRD
- formation: How the monsters should be arranged
- lighting: 0.0 = daylight, 0.5 = twilight, 1.0 = darkness
- count: How many of each monster

JSON:"""

            import json as json_mod
            response = await client.aio.models.generate_content(
                model=MODEL_ID,
                contents=build_prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            plan = json_mod.loads(response.text)
            logger.info(f"Build plan: {plan}")

            # Step 2: Find a scene
            await status_msg.edit(content="🏗️ **Encounter Builder** — Searching for battle maps...")
            scene_uuid = None
            scene_name = "Unknown"

            for kw in plan.get('scene_keywords', []):
                scenes = foundry_client.search_scenes(kw)
                if scenes:
                    # Prefer world scenes first, then compendium
                    world_scenes = [s for s in scenes if not s.get('uuid', '').startswith('Compendium')]
                    if world_scenes:
                        scene_uuid = world_scenes[0]['uuid']
                        scene_name = world_scenes[0]['name']
                    else:
                        # Found a compendium scene plan to import it
                        compendium_scene = scenes[0]
                        compendium_uuid = compendium_scene['uuid']
                        c_name = compendium_scene['name']
                        
                        await status_msg.edit(content=f"🏗️ **Encounter Builder** — Importing map **{c_name}**...")
                        logger.info(f"Importing compendium scene: {compendium_uuid}")
                        
                        import_result = foundry_client.import_compendium_scene(compendium_uuid)
                        if isinstance(import_result, dict) and (import_result.get('uuid') or import_result.get('_id')):
                            scene_uuid = import_result.get('uuid') or import_result.get('_id')
                            scene_name = import_result.get('name') or c_name
                            logger.info(f"Imported scene UUID: {scene_uuid}")
                        else:
                            logger.error(f"Failed to import scene: {import_result}")
                            await ctx.send(f"⚠️ Failed to import scene **{c_name}**.")
                            return
                    break

            if not scene_uuid:
                # Use the active scene
                world_scenes = foundry_client.get_world_scenes()
                active = [s for s in world_scenes if s.get('active')]
                if active:
                    scene_uuid = active[0]['uuid']
                    scene_name = active[0]['name']
                elif world_scenes:
                    scene_uuid = world_scenes[0]['uuid']
                    scene_name = world_scenes[0]['name']
                else:
                    await ctx.send("⚠️ No scenes found in the world.")
                    return

            # Step 3: Search for and import monsters
            await status_msg.edit(
                content=f"🏗️ **Encounter Builder** — Found map: **{scene_name}**\nSearching for monsters..."
            )

            placements = []
            monsters_found = []

            # Get scene dimensions for position calculation
            scene_data = foundry_client.get_entity(scene_uuid).get('data', {})
            scene_width = scene_data.get('width', 4000)
            scene_height = scene_data.get('height', 3000)
            grid_size = scene_data.get('grid', {}).get('size', 100)

            for monster_info in plan.get('monsters', []):
                m_name = monster_info.get('name', 'Goblin')
                m_count = min(monster_info.get('count', 1), 8)  # Cap at 8

                # Search for this monster
                results = foundry_client.search_actors(m_name)
                if not results:
                    monsters_found.append(f"❌ {m_name} — not found")
                    continue

                actor = results[0]
                actor_uuid = actor.get('uuid', '')
                actor_name = actor.get('name', m_name)

                # If it's a compendium actor, import it to the world
                if actor_uuid.startswith('Compendium'):
                    await status_msg.edit(
                        content=f"🏗️ **Encounter Builder** — Importing **{actor_name}** to world..."
                    )
                    import_result = foundry_client.import_compendium_actor(actor_uuid)
                    actor_uuid = import_result.get('uuid', actor_uuid)

                monsters_found.append(f"✅ {actor_name} ×{m_count}")

                # Calculate positions based on formation
                formation = plan.get('formation', 'scattered')
                positions = _calculate_positions(
                    m_count, formation, scene_width, scene_height, grid_size
                )

                for i, (px, py) in enumerate(positions):
                    token_name = f"{actor_name}" if m_count == 1 else f"{actor_name} {i+1}"
                    placements.append({
                        'actor_uuid': actor_uuid,
                        'x': px,
                        'y': py,
                        'name': token_name,
                        'hidden': False,
                    })

            if not placements:
                await ctx.send(
                    f"⚠️ Could not find any of the requested monsters.\n"
                    f"Searched for: {', '.join(m['name'] for m in plan.get('monsters', []))}"
                )
                return

            # Step 4: Place all tokens
            await status_msg.edit(
                content=f"🏗️ **Encounter Builder** — Placing {len(placements)} tokens on **{scene_name}**..."
            )
            foundry_client.place_tokens_on_scene(scene_uuid, placements)

            # Step 5: Set lighting
            darkness = plan.get('lighting', 0.0)
            if darkness > 0:
                foundry_client.update_scene_lighting(scene_uuid, darkness)

            # Build the report
            embed = discord.Embed(
                title="🏗️ Encounter Built!",
                description=description,
                color=discord.Color.green()
            )
            embed.add_field(
                name="📍 Scene",
                value=scene_name,
                inline=True
            )
            embed.add_field(
                name="🌓 Lighting",
                value=f"{'☀️ Day' if darkness < 0.3 else '🌅 Twilight' if darkness < 0.7 else '🌙 Night'}",
                inline=True
            )
            embed.add_field(
                name="👹 Monsters",
                value="\n".join(monsters_found) or "None",
                inline=False
            )
            embed.add_field(
                name="📌 Tokens Placed",
                value=f"{len(placements)} tokens on the map",
                inline=True
            )
            embed.set_footer(text="Check Foundry VTT to see the encounter!")

            await status_msg.edit(content=None, embed=embed)

    except Exception as e:
        logger.error(f"Build command failed: {e}", exc_info=True)
        await ctx.send(f"⚠️ Encounter build failed: {e}")


def _calculate_positions(
    count: int,
    formation: str,
    scene_width: int,
    scene_height: int,
    grid_size: int,
) -> list:
    """
    Calculate token positions based on formation type.
    Returns a list of (x, y) tuples in pixel coordinates.
    """
    import math
    import random

    # Center of the scene
    cx = scene_width // 2
    cy = scene_height // 2
    spread = grid_size * 3  # How far apart tokens are

    positions = []

    if formation == 'clustered':
        # Tight group near center
        for i in range(count):
            angle = (2 * math.pi * i) / max(count, 1)
            r = spread if count > 1 else 0
            x = int(cx + r * math.cos(angle))
            y = int(cy + r * math.sin(angle))
            positions.append((x, y))

    elif formation == 'surrounding':
        # Ring around center (like surrounding the party)
        ring_radius = spread * 2
        for i in range(count):
            angle = (2 * math.pi * i) / max(count, 1)
            x = int(cx + ring_radius * math.cos(angle))
            y = int(cy + ring_radius * math.sin(angle))
            positions.append((x, y))

    elif formation == 'defensive':
        # Line formation, like defending an entrance
        start_x = cx - (count * grid_size) // 2
        for i in range(count):
            x = start_x + i * grid_size * 2
            y = cy
            positions.append((x, y))

    elif formation == 'ambush':
        # Two groups on opposite sides
        half = count // 2
        for i in range(half):
            # Left flank
            x = cx - spread * 3
            y = cy - (half * grid_size) // 2 + i * grid_size * 2
            positions.append((x, y))
        for i in range(count - half):
            # Right flank
            x = cx + spread * 3
            y = cy - ((count - half) * grid_size) // 2 + i * grid_size * 2
            positions.append((x, y))

    else:  # scattered (default)
        for i in range(count):
            x = cx + random.randint(-spread * 2, spread * 2)
            y = cy + random.randint(-spread * 2, spread * 2)
            positions.append((x, y))

    # Clamp to scene bounds
    margin = grid_size * 2
    positions = [
        (max(margin, min(x, scene_width - margin)),
         max(margin, min(y, scene_height - margin)))
        for x, y in positions
    ]

    return positions


# ---------------------------------------------------------------------------
# Prep Team Commands (War Room only)
# ---------------------------------------------------------------------------
@bot.command(name='brainstorm')
async def brainstorm_cmd(ctx, *, topic: str):
    """Brainstorm worldbuilding ideas.
    Usage: !brainstorm a mysterious thieves guild
    """
    if WAR_ROOM_CHANNEL_ID and str(ctx.channel.id) != WAR_ROOM_CHANNEL_ID:
        await ctx.send("🗺️ Brainstorming is only available in the War Room channel.")
        return

    logger.info(f"Brainstorm from {ctx.author}: {topic}")
    try:
        async with ctx.typing():
            response = await world_architect.brainstorm(topic)
        if len(response) > 2000:
            for i in range(0, len(response), 2000):
                await ctx.send(response[i:i + 2000])
        else:
            await ctx.send(response)
    except Exception as e:
        logger.error(f"Brainstorm failed: {e}", exc_info=True)
        await send_to_moderator_log(f"[!brainstorm] Error: {traceback.format_exc()}")
        await ctx.send("⚠️ Brainstorming failed. Check the log.")


@bot.command(name='plan')
async def plan_cmd(ctx, *, notes: str):
    """Plan a session.
    Usage: !plan The party needs to infiltrate the Zhentarim warehouse
    """
    if WAR_ROOM_CHANNEL_ID and str(ctx.channel.id) != WAR_ROOM_CHANNEL_ID:
        await ctx.send("🗺️ Session planning is only available in the War Room channel.")
        return

    logger.info(f"Session plan from {ctx.author}: {notes}")
    try:
        async with ctx.typing():
            response = await campaign_planner.plan_session(notes)
        if len(response) > 2000:
            for i in range(0, len(response), 2000):
                await ctx.send(response[i:i + 2000])
        else:
            await ctx.send(response)
    except Exception as e:
        logger.error(f"Session planning failed: {e}", exc_info=True)
        await send_to_moderator_log(f"[!plan] Error: {traceback.format_exc()}")
        await ctx.send("⚠️ Session planning failed. Check the log.")





# ---------------------------------------------------------------------------
# Main Message Handler (channel-based team routing)
# ---------------------------------------------------------------------------
async def _handle_war_room(message, user_input: str):
    """Handle messages in the War Room channel — Prep Team pipeline."""
    logger.info(f"[War Room] {message.author}: {user_input}")

    try:
        route = await prep_router.route(user_input)
        logger.info(f"[War Room] Routed as: {route}")

        async with message.channel.typing():
            if route.intent == PrepIntent.NPC_CREATE:
                response = await world_architect.create_npc(user_input)
            elif route.intent == PrepIntent.LOCATION_CREATE:
                response = await world_architect.create_location(user_input)
            elif route.intent == PrepIntent.SESSION_PLANNING:
                response = await campaign_planner.process_request(user_input)
            elif route.intent == PrepIntent.SCENE_SETUP:
                response = await foundry_architect.process_request(user_input)
            elif route.intent == PrepIntent.GENERAL_QUESTION:
                response = await message_router.generate_direct_response(user_input)
            else:  # WORLDBUILDING (default)
                response = await world_architect.brainstorm(user_input)

        # Deliver
        if response:
            if len(response) > 2000:
                for i in range(0, len(response), 2000):
                    await message.channel.send(response[i:i + 2000])
            else:
                await message.channel.send(response)

    except Exception as e:
        logger.error(f"[War Room] Error: {e}", exc_info=True)
        await send_to_moderator_log(
            f"[War Room] Error from {message.author}:\n{user_input}\n{traceback.format_exc()}"
        )
        await message.channel.send("⚠️ Something went wrong in the War Room. Check the log.")


# ---------------------------------------------------------------------------
# Scene Sync Helpers (Phase 4.5 — FoundryArchitect dispatch)
# ---------------------------------------------------------------------------

def _build_architect_request(scene_changes: dict, narrative: str) -> str:
    """Translate scene classifier output into a natural-language FoundryArchitect request."""
    parts = []

    if scene_changes.get("combat_started"):
        monsters = scene_changes.get("monsters_introduced", [])
        if monsters:
            parts.append(f"Start a combat encounter with: {', '.join(monsters)}")
        else:
            parts.append("Start a combat encounter with the enemies described")

    if scene_changes.get("location_changed") and scene_changes.get("new_location"):
        parts.append(f"Scene change to: {scene_changes['new_location']}")

    if scene_changes.get("lighting_change") is not None:
        parts.append(f"Set scene darkness level to {scene_changes['lighting_change']}")

    if scene_changes.get("combat_ended"):
        parts.append("End the current combat encounter")

    if not parts:
        return ""

    request = ". ".join(parts)
    # Include truncated narrative for context
    request += f"\n\nNarrative context: {narrative[:500]}"
    return request


async def _run_architect_safe(request: str, channel):
    """Run FoundryArchitect in background with error handling and Discord feedback."""
    status_msg = None
    try:
        # Post a subtle status indicator
        status_msg = await channel.send("🗺️ *Updating the scene...*")

        await gemini_limiter.acquire()
        result = await foundry_architect.process_request(request)
        logger.info(f"FoundryArchitect result: {result}")

        # Update the status message on success
        if status_msg:
            try:
                await status_msg.edit(content="🗺️ *Scene updated!*")
            except Exception:
                pass  # If edit fails, no big deal

    except Exception as e:
        logger.error(f"FoundryArchitect background error: {e}", exc_info=True)
        # Clean up the status message on failure
        if status_msg:
            try:
                await status_msg.edit(content="🗺️ *Scene update skipped — Foundry error logged.*")
            except Exception:
                pass


async def _handle_game_table(message, user_input: str):
    """Handle messages in the Game Table channel — Live DM Team pipeline."""
    logger.info(f"[Game Table] {message.author}: {user_input}")

    # Resolve player identity — prefix the message with character context
    discord_name = message.author.name.lower()
    character_name = PLAYER_MAP.get(discord_name)
    if character_name:
        user_input = f"[{character_name}]: {user_input}"
        logger.info(f"Player identified: {discord_name} -> {character_name}")

    try:
        # ----- Phase 0: Route the message -----
        await gemini_limiter.acquire()
        route = await message_router.route(user_input)
        logger.info(f"Message routed as: {route}")

        # ---- Casual chat — ignore silently ----
        if route.message_type == MessageType.CASUAL_CHAT:
            logger.info("Casual chat detected — ignoring.")
            return

        # ---- Out-of-game question — respond directly ----
        if route.direct_response:
            async with message.channel.typing():
                await gemini_limiter.acquire()
                response = await message_router.generate_direct_response(user_input)
            await message.channel.send(response)
            return

        # ---- Game action / game question — full agent pipeline ----
        async with message.channel.typing():

            # Phase 1: Spatial context (board monitor)
            board_context = ""
            if route.needs_board_monitor:
                board_context = await board_monitor.process_request(user_input)
                if board_context != "No specific board state queried.":
                    logger.info(f"Board Context: {board_context}")

            # Track the player's query so reference lookups are contextual
            context_assembler.set_query(user_input)

            # Phase 2: Mechanical ruling (rules lawyer)
            rules_ruling = None
            if route.needs_rules_lawyer:
                await gemini_limiter.acquire()
                rules_ruling = await rules_lawyer.process_request(user_input, board_context)
                logger.info(f"Rules Ruling: {rules_ruling}")

            # Phase 3: Narrative generation (storyteller)
            narrative = ""
            if route.needs_storyteller:
                await gemini_limiter.acquire()
                if rules_ruling is not None:
                    narrative = await storyteller.process_request(user_input, rules_ruling)
                else:
                    narrative = await storyteller.process_request(
                        user_input,
                        {"valid": True, "mechanic_used": "None", "result": board_context},
                    )
                logger.info(f"Generated Narrative (len={len(narrative)})")

        # Phase 4: Delivery to player
        if narrative:
            if len(narrative) > 2000:
                for i in range(0, len(narrative), 2000):
                    await message.channel.send(narrative[i:i + 2000])
            else:
                await message.channel.send(narrative)

        # Phase 4.5: Scene sync — detect board changes and dispatch to FoundryArchitect
        if narrative:
            try:
                await gemini_limiter.acquire()
                scene_changes = await classify_scene_changes(
                    narrative=narrative,
                    rules_json=rules_ruling,
                    current_location=storyteller._current_location,
                    client=client,
                    model_id=MODEL_ID,
                )

                # Update location tracking dynamically
                if scene_changes.get("location_changed") and scene_changes.get("new_location"):
                    old_loc = storyteller._current_location
                    storyteller.set_location(scene_changes["new_location"])
                    logger.info(f"Location updated: {old_loc} -> {scene_changes['new_location']}")

                # Dispatch to FoundryArchitect if board needs updating
                if scene_changes.get("foundry_actions_needed"):
                    if foundry_client.is_connected:
                        architect_request = _build_architect_request(scene_changes, narrative)
                        if architect_request:
                            asyncio.create_task(_run_architect_safe(architect_request, message.channel))
                            logger.info(f"FoundryArchitect dispatched: {architect_request[:100]}...")
                    else:
                        logger.info("Scene change detected but Foundry not connected — skipping board sync.")

            except Exception as e:
                # Scene sync errors should NEVER block the game
                logger.warning(f"Scene classifier error (non-blocking): {e}", exc_info=True)

        # Phase 5: Chronicler (silent — updates vault, never speaks to player)
        if route.needs_rules_lawyer or route.needs_storyteller:
            try:
                rules_text = str(rules_ruling) if rules_ruling else "N/A"
                await gemini_limiter.acquire()
                await chronicler.process_exchange(
                    player_action=user_input,
                    rules_response=rules_text,
                    story_response=narrative,
                    session_number=current_session,
                    current_location=storyteller._current_location
                )
                # Checkpoint memory after every chronicler pass
                context_assembler.save_checkpoint()
            except Exception as e:
                # Chronicler errors should never impact the player experience
                logger.error(f"Chronicler error (non-blocking): {e}", exc_info=True)

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)

        await send_to_moderator_log(
            f"[on_message] Error processing message from {message.author}:\n"
            f"Content: {user_input}\n"
            f"{traceback.format_exc()}"
        )

        await message.channel.send(
            "⚠️ Something went wrong processing that. The DM has been notified."
        )


@bot.event
async def on_message(message):
    # Ignore self
    if message.author == bot.user:
        return

    # Let commands go through the normal handler
    if message.content.startswith('!'):
        await bot.process_commands(message)
        return

    user_input = message.content
    channel_id = str(message.channel.id)

    # Route to the correct team based on channel
    if WAR_ROOM_CHANNEL_ID and channel_id == WAR_ROOM_CHANNEL_ID:
        await _handle_war_room(message, user_input)
    elif GAME_TABLE_CHANNEL_ID and channel_id == GAME_TABLE_CHANNEL_ID:
        await _handle_game_table(message, user_input)
    else:
        # Messages in other channels — fallback to the game table pipeline
        # so the bot still works if channel IDs aren't configured
        await _handle_game_table(message, user_input)


if __name__ == "__main__":
    if DISCORD_TOKEN:
        bot.run(DISCORD_TOKEN)
    else:
        print("Error: DISCORD_BOT_TOKEN not found via os.getenv")
