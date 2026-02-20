"""
D&D AI Dungeon Master — Discord Bot Client

This is the core bot setup, event handling, and message routing.
All !commands live in Cogs (bot/cogs/). The AI pipelines live here
as _handle_game_table() and _handle_war_room().

Replaces the old orchestration/bot.py god file.
"""

import os
import time
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
from tools.state_manager import StateManager
from tools.action_queue import ActionQueue, QueuedAction
from agents.tools.foundry_tool import FoundryClient

# Agents — Live DM Team
from agents.board_monitor import BoardMonitorAgent
from agents.rules_lawyer import RulesLawyerAgent
from agents.storyteller import StorytellerAgent
from agents.foundry_architect import FoundryArchitectAgent
from agents.message_router import MessageRouterAgent
from agents.chronicler import ChroniclerAgent


# LangGraph pipeline
from pipeline.graph import build_game_pipeline

# Agents — Prep Team
from agents.world_architect import WorldArchitectAgent
from agents.campaign_planner import CampaignPlannerAgent
from agents.prep_router import PrepRouterAgent, PrepIntent
from agents.cartographer import CartographerAgent

logger = logging.getLogger("DND_Bot")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODERATOR_LOG_CHANNEL_ID = os.getenv("MODERATOR_LOG_CHANNEL_ID")
WAR_ROOM_CHANNEL_ID = os.getenv("WAR_ROOM_CHANNEL_ID")
GAME_TABLE_CHANNEL_ID = os.getenv("GAME_TABLE_CHANNEL_ID")

# Player-to-Character mapping
PLAYER_MAP = {}
raw_map = os.getenv("PLAYER_MAP", "")
if raw_map:
    for pair in raw_map.split(","):
        pair = pair.strip()
        if ":" in pair:
            discord_name, char_name = pair.split(":", 1)
            PLAYER_MAP[discord_name.strip().lower()] = char_name.strip()

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/dnd_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# ---------------------------------------------------------------------------
# Gemini Client
# ---------------------------------------------------------------------------
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment.")
    gemini_client = None
else:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

MODEL_ID = "gemini-2.0-flash"

# ---------------------------------------------------------------------------
# Campaign Manager & Vault
# ---------------------------------------------------------------------------
campaign_manager = CampaignManager(root_dir=".")
campaign_manager.ensure_migration()

vault = VaultManager(vault_path="campaign_vault")
ref_manager = ReferenceManager()
state_manager = StateManager()  # async connect happens in on_ready
context_assembler = ContextAssembler(vault, reference_manager=ref_manager, state_manager=state_manager)
logger.info(f"ReferenceManager: {ref_manager.get_stats()}")

# ---------------------------------------------------------------------------
# Foundry VTT Connection (async connect happens in on_ready)
# ---------------------------------------------------------------------------
foundry_client = FoundryClient()

# ---------------------------------------------------------------------------
# Action Queue — DM Admin Console state
# ---------------------------------------------------------------------------
action_queue = ActionQueue()

# ---------------------------------------------------------------------------
# Agents — Live DM Team (Game Table channel)
# ---------------------------------------------------------------------------
board_monitor = BoardMonitorAgent(gemini_client, foundry=foundry_client)
rules_lawyer = RulesLawyerAgent(gemini_client, context_assembler, model_id=MODEL_ID)
storyteller = StorytellerAgent(gemini_client, context_assembler, model_id=MODEL_ID)
foundry_architect = FoundryArchitectAgent(gemini_client, foundry=foundry_client, model_id=MODEL_ID)
message_router = MessageRouterAgent(gemini_client, context_assembler, model_id=MODEL_ID)
chronicler = ChroniclerAgent(gemini_client, vault, context_assembler, model_id=MODEL_ID)

# ---------------------------------------------------------------------------
# Agents — Prep Team (War Room channel)
# ---------------------------------------------------------------------------
world_architect = WorldArchitectAgent(gemini_client, vault, context_assembler, model_id=MODEL_ID)
campaign_planner = CampaignPlannerAgent(gemini_client, vault, context_assembler, model_id=MODEL_ID)
prep_router = PrepRouterAgent(gemini_client, context_assembler, model_id=MODEL_ID)
cartographer_agent = CartographerAgent(
    gemini_client,
    foundry=foundry_client,
    vault=vault,
    model_id=MODEL_ID,
    output_dir=os.path.join(vault.vault_path, "Assets", "Maps"),
)

# Set the starting location from the world clock / vault
_world_clock = vault.read_world_clock()
_start_location = _world_clock.get("current_location", "The Yawning Portal") if _world_clock else "The Yawning Portal"
storyteller.set_location(_start_location)
logger.info(f"Starting location: {_start_location}")

# ---------------------------------------------------------------------------
# LangGraph Pipeline — replaces the imperative if/else chain
# ---------------------------------------------------------------------------
game_pipeline = build_game_pipeline({
    "message_router": message_router,
    "board_monitor": board_monitor,
    "rules_lawyer": rules_lawyer,
    "storyteller": storyteller,
    "chronicler": chronicler,
    "context_assembler": context_assembler,
    "gemini_client": gemini_client,
    "model_id": MODEL_ID,
    "vault_manager": vault,
    "state_manager": state_manager,
    "foundry_client": foundry_client,
})
logger.info("LangGraph game pipeline built and compiled.")

# Track current session number
current_session = context_assembler.current_session

# Restore conversation memory from last checkpoint
context_assembler.load_checkpoint()
logger.info("Memory checkpoint loaded.")

# ---------------------------------------------------------------------------
# Discord Bot Instance
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)


# ---------------------------------------------------------------------------
# Moderator Log Helper
# ---------------------------------------------------------------------------
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
            chunk = str(content)[i : i + 1900]
            await channel.send(f"```\n{chunk}\n```")
    except Exception as e:
        logger.error(f"Failed to send to moderator log: {e}")
        logger.error(content)


# ---------------------------------------------------------------------------
# Attach shared services to bot so cogs can access them via self.bot
# ---------------------------------------------------------------------------
bot.campaign_manager = campaign_manager
bot.vault = vault
bot.context_assembler = context_assembler
bot.state_manager = state_manager
bot.ref_manager = ref_manager
bot.foundry_client = foundry_client
bot.foundry_architect = foundry_architect
bot.gemini_client = gemini_client
bot.model_id = MODEL_ID
bot.storyteller = storyteller
bot.world_architect = world_architect
bot.campaign_planner = campaign_planner
bot.cartographer_agent = cartographer_agent
bot.send_to_moderator_log = send_to_moderator_log
bot.war_room_channel_id = WAR_ROOM_CHANNEL_ID


# ---------------------------------------------------------------------------
# Scene Sync Helpers
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
    request += f"\n\nNarrative context: {str(narrative)[:500]}"
    return request


async def _run_architect_safe(request: str, channel):
    """Run FoundryArchitect in background with error handling."""
    status_msg = None
    try:
        status_msg = await channel.send("🗺️ *Updating the scene...*")
        await gemini_limiter.acquire()
        result = await foundry_architect.process_request(request)
        logger.info(f"FoundryArchitect result: {result}")
        if status_msg:
            try:
                await status_msg.edit(content="🗺️ *Scene updated!*")
            except Exception:
                pass
    except Exception as e:
        logger.error(f"FoundryArchitect background error: {e}", exc_info=True)
        if status_msg:
            try:
                await status_msg.edit(content="🗺️ *Scene update skipped — Foundry error logged.*")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Game Table Pipeline — Driven by LangGraph
# ---------------------------------------------------------------------------
async def _handle_game_table(message, user_input: str):
    """Handle messages in the Game Table channel via the LangGraph pipeline.

    Flow: router → board_monitor → rules → storyteller → scene_sync → chronicler
    All agent calls happen inside LangGraph nodes. This function only handles
    Discord I/O (delivery, Foundry dispatch) after the pipeline finishes.
    """
    logger.info(f"[Game Table] {message.author}: {user_input}")

    # Resolve player identity
    discord_name = message.author.name.lower()
    character_name = PLAYER_MAP.get(discord_name)
    if character_name:
        user_input = f"[{character_name}]: {user_input}"
        logger.info(f"Player identified: {discord_name} -> {character_name}")

    try:
        # Build the initial state and invoke the pipeline
        initial_state = {
            "player_input": user_input,
            "character_name": character_name,
            "session": current_session,
            "current_location": storyteller._current_location,
        }

        async with message.channel.typing():
            result = await game_pipeline.ainvoke(initial_state)

        logger.info(f"Pipeline complete. Keys returned: {list(result.keys())}")

        # --- Discord I/O after pipeline ---

        # Direct response (out-of-game question answered by router)
        if result.get("direct_reply"):
            reply = result["direct_reply"]
            if len(reply) > 2000:
                for i in range(0, len(reply), 2000):
                    await message.channel.send(reply[i : i + 2000])
            else:
                await message.channel.send(reply)
            return

        # Casual chat — the router already decided to stop
        if result.get("message_type") == "casual_chat":
            logger.info("Casual chat detected — ignoring.")
            return

        # Narrative delivery
        narrative = result.get("narrative", "")
        if narrative:
            if len(narrative) > 2000:
                for i in range(0, len(narrative), 2000):
                    await message.channel.send(narrative[i : i + 2000])
            else:
                await message.channel.send(narrative)

        # Foundry VTT dispatch (runs AFTER delivery, non-blocking)
        scene_changes = result.get("scene_changes")
        if scene_changes and scene_changes.get("foundry_actions_needed"):
            if foundry_client.is_connected:
                architect_request = _build_architect_request(scene_changes, narrative)
                if architect_request:
                    asyncio.create_task(_run_architect_safe(architect_request, message.channel))
                    logger.info(f"FoundryArchitect dispatched: {str(architect_request)[:100]}...")
            else:
                logger.info("Scene change detected but Foundry not connected — skipping.")

        # Error surfacing (pipeline nodes log their own errors, but surface fatal ones)
        if result.get("error"):
            logger.error(f"Pipeline returned error: {result['error']}")

    except Exception as e:
        logger.error(f"Error processing message: {e}", exc_info=True)
        await send_to_moderator_log(
            f"[on_message] Error processing message from {message.author}:\n"
            f"Content: {user_input}\n{traceback.format_exc()}"
        )
        await message.channel.send("⚠️ Something went wrong processing that. The DM has been notified.")


# ---------------------------------------------------------------------------
# Batch Resolve — Called by the DM Admin Console's Resolve Turn button
# ---------------------------------------------------------------------------
async def _send_chunked(channel, text: str):
    """Send a long message in 2000-char chunks."""
    if len(text) <= 2000:
        await channel.send(text)
    else:
        for i in range(0, len(text), 2000):
            await channel.send(text[i : i + 2000])


async def handle_batch_resolve(actions, game_table_channel):
    """Process a batch of curated actions through the pipeline.

    Called by AdminConsoleView.resolve_turn(). Accepts a list of QueuedAction
    objects that the DM has reviewed and approved.
    """
    from tools.action_queue import QueuedAction

    # Build combined input — one line per action with all context
    combined_parts = []
    dice_results = {}
    dm_context_parts = []

    for action in actions:
        prefix = f"[{action.character_name}]" if action.character_name else "[DM]"
        line = f"{prefix}: {action.player_input}"
        if action.resolved_rolls and action.character_name:
            roll_strs = []
            roll_data = []
            for roll in action.resolved_rolls:
                dc_str = f" vs DC {roll.dc}" if roll.dc else ""
                roll_strs.append(f"{roll.roll_type} {roll.detail}{dc_str}")
                roll_data.append({
                    "type": roll.roll_type,
                    "result": roll.result,
                    "dc": roll.dc,
                })
            line += f" [Rolls: {'; '.join(roll_strs)}]"
            dice_results[action.character_name] = {"rolls": roll_data}
        if action.dm_annotation:
            line += f" {{DM Note: {action.dm_annotation}}}"
            dm_context_parts.append(action.dm_annotation)
        combined_parts.append(line)

    # Include monster/NPC rolls in the batch context
    monster_rolls = await action_queue.flush_monster_rolls()
    for mr in monster_rolls:
        target_str = f" targeting {mr.target}" if mr.target else ""
        combined_parts.append(
            f"[{mr.monster_name}]: {mr.roll_type}{target_str} "
            f"[Roll: {mr.roll_type} {mr.detail}]"
        )
        dice_results[mr.monster_name] = {
            "rolls": [{"type": mr.roll_type, "result": mr.result, "dc": None}]
        }

    batched_input = "\n".join(combined_parts)
    is_batched = len(actions) > 1 or len(monster_rolls) > 0

    initial_state = {
        "player_input": batched_input,
        "character_name": actions[0].character_name if len(actions) == 1 and not monster_rolls else None,
        "session": current_session,
        "current_location": storyteller._current_location,
        "dm_context": "\n".join(dm_context_parts) if dm_context_parts else None,
        "dice_results": dice_results if dice_results else None,
        "is_batched": is_batched,
    }

    try:
        async with game_table_channel.typing():
            result = await game_pipeline.ainvoke(initial_state)

        logger.info(f"Batch resolve complete. Keys: {list(result.keys())}")

        # Separate secret vs public actions
        secret_actions = [a for a in actions if a.is_secret]
        has_public = any(not a.is_secret for a in actions)

        # Deliver narrative
        narrative = result.get("narrative", "")
        if narrative:
            # Public narrative goes to game table
            if has_public:
                await _send_chunked(game_table_channel, narrative)

            # Secret action results go to each player's private thread
            for action in secret_actions:
                if action.private_thread_id:
                    try:
                        guild = game_table_channel.guild
                        thread = guild.get_thread(action.private_thread_id)
                        if thread:
                            secret_note = (
                                f"**[Secret Result for {action.character_name}]**\n"
                                f"_{action.player_input}_\n\n{narrative}"
                            )
                            await _send_chunked(thread, secret_note)
                    except Exception as e:
                        logger.error(f"Failed to send secret result: {e}")

        # Direct reply fallback
        if result.get("direct_reply"):
            await _send_chunked(game_table_channel, result["direct_reply"])

        # Scene sync (same as _handle_game_table)
        scene_changes = result.get("scene_changes")
        if scene_changes and scene_changes.get("foundry_actions_needed"):
            if foundry_client.is_connected:
                architect_request = _build_architect_request(scene_changes, narrative)
                if architect_request:
                    asyncio.create_task(_run_architect_safe(architect_request, game_table_channel))

        if result.get("error"):
            logger.error(f"Batch resolve pipeline error: {result['error']}")

        # Advance conversation history decay once per resolve (not per message)
        context_assembler.history.advance_turn()

        # Pipeline succeeded — clear the backup so restore_batch() is a no-op
        await action_queue.confirm_batch()

        # Post sync report to DM console
        sync_report = result.get("sync_report")
        if sync_report:
            admin_cog = bot.get_cog("Admin Console")
            if admin_cog:
                await admin_cog.post_sync_report(sync_report)

    except Exception as e:
        logger.error(f"Batch resolve error: {e}", exc_info=True)
        await send_to_moderator_log(f"[batch_resolve] Error:\n{traceback.format_exc()}")
        await game_table_channel.send(
            "\u26a0\ufe0f Something went wrong resolving the turn. The DM has been notified."
        )
        # Restore flushed actions back to queue so the DM can retry
        restored = await action_queue.restore_batch()
        if restored:
            logger.info(f"Restored {restored} actions to queue after pipeline failure")
            admin_cog = bot.get_cog("Admin Console")
            if admin_cog:
                await admin_cog.refresh_console()


# ---------------------------------------------------------------------------
# War Room Pipeline
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

        if response:
            text_response = str(response)
            if len(text_response) > 2000:
                for i in range(0, len(text_response), 2000):
                    await message.channel.send(text_response[i : i + 2000])
            else:
                await message.channel.send(text_response)

    except Exception as e:
        logger.error(f"[War Room] Error: {e}", exc_info=True)
        await send_to_moderator_log(
            f"[War Room] Error from {message.author}:\n{user_input}\n{traceback.format_exc()}"
        )
        await message.channel.send("⚠️ Something went wrong in the War Room. Check the log.")


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    logger.info(f"Vault path: {vault.vault_path}")
    logger.info(f"Current session: {current_session}")

    # Async-connect StateManager (MongoDB) — non-blocking, degrades gracefully
    if await state_manager.connect():
        logger.info("StateManager connected — DB-backed context active.")
    else:
        logger.warning("StateManager unavailable — running in vault-only mode.")

    # Async-connect Foundry VTT — non-blocking, degrades gracefully
    if foundry_client.api_key:
        if await foundry_client.connect():
            logger.info(f"Foundry VTT connected: client={foundry_client.client_id}")
        else:
            logger.warning("Foundry VTT connection failed — running without live board data.")
    else:
        logger.info("Foundry VTT disabled (no API key set).")

    # Register persistent views so admin console buttons survive restarts
    from bot.views.admin_views import AdminConsoleView
    admin_cog = bot.get_cog("Admin Console")
    if admin_cog:
        bot.add_view(AdminConsoleView(admin_cog))
        logger.info("Admin console persistent view registered.")

    # Sync slash commands (needed for /console)
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        logger.error(f"Slash command sync failed: {e}")

    print("D&D AI System Online. Vault-backed state is active.")


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Let commands go through the normal handler
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    user_input = message.content
    channel_id = str(message.channel.id)

    # Check if this message is in the admin console thread
    admin_cog = bot.get_cog("Admin Console")
    is_console_thread = (
        isinstance(message.channel, discord.Thread)
        and admin_cog
        and admin_cog.is_console_thread(message.channel.id)
    )

    if is_console_thread:
        if admin_cog._is_ooc:
            await admin_cog.handle_ooc_message(message)
        else:
            # IC mode: treat as DM's action (queue or pipeline)
            discord_name = message.author.name.lower()
            character_name = PLAYER_MAP.get(discord_name)
            if action_queue.is_queue_mode:
                action = QueuedAction(
                    discord_user_id=message.author.id,
                    discord_message_id=message.id,
                    channel_id=message.channel.id,
                    character_name=character_name,
                    player_input=user_input,
                )
                await action_queue.enqueue(action)
                try:
                    await message.add_reaction("\u23f3")
                except discord.HTTPException:
                    pass
                await admin_cog.refresh_console()
            else:
                await _handle_game_table(message, user_input)
        return  # Don't fall through to other handlers

    # Check if this message is in a player's private console thread
    is_player_thread = (
        isinstance(message.channel, discord.Thread)
        and action_queue.is_player_thread(message.channel.id)
    )

    if WAR_ROOM_CHANNEL_ID and channel_id == WAR_ROOM_CHANNEL_ID:
        await _handle_war_room(message, user_input)
    elif is_player_thread or (GAME_TABLE_CHANNEL_ID and channel_id == GAME_TABLE_CHANNEL_ID):
        # Queue mode: capture the action instead of running the pipeline
        if action_queue.is_queue_mode:
            discord_name = message.author.name.lower()
            character_name = PLAYER_MAP.get(discord_name)
            action = QueuedAction(
                discord_user_id=message.author.id,
                discord_message_id=message.id,
                channel_id=message.channel.id,
                character_name=character_name,
                player_input=user_input,
                is_secret=is_player_thread,
                private_thread_id=message.channel.id if is_player_thread else None,
            )
            await action_queue.enqueue(action)
            try:
                await message.add_reaction("\u23f3")  # Hourglass — action received
            except discord.HTTPException:
                pass  # Reaction failed (permissions, deleted message) — non-critical
            # Refresh admin console embed
            admin_cog = bot.get_cog("Admin Console")
            if admin_cog:
                await admin_cog.refresh_console()
        else:
            await _handle_game_table(message, user_input)
    else:
        await _handle_game_table(message, user_input)


# ---------------------------------------------------------------------------
# Cog Loading & Entry Point
# ---------------------------------------------------------------------------
async def load_cogs():
    """Load all Cog extensions."""
    await bot.load_extension("bot.cogs.dm_cog")
    await bot.load_extension("bot.cogs.foundry_cog")
    await bot.load_extension("bot.cogs.prep_cog")
    await bot.load_extension("bot.cogs.admin_cog")
    await bot.load_extension("bot.cogs.player_cog")
    await bot.load_extension("bot.cogs.sync_cog")
    logger.info("All Cogs loaded.")


async def main():
    """Async entry point — load cogs then start the bot."""
    try:
        async with bot:
            await load_cogs()
            await bot.start(DISCORD_TOKEN)
    finally:
        await foundry_client.close()


def run():
    """Synchronous entry point for scripts."""
    if not DISCORD_TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found via os.getenv")
        return
    asyncio.run(main())
