"""
Player Cog — Per-player private console for secret actions and individual decisions.

Commands:
  /whisper — creates a private thread for the player
  /import  — import a character sheet from the creation wizard
Players can type actions in their private thread that only the DM sees.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands
from pydantic import ValidationError

from tools.vault_manager import VaultManager, parse_frontmatter
from tools.models import PartyMember

logger = logging.getLogger("Player_Cog")


class PlayerStatusView(discord.ui.View):
    """Simple persistent view shown in a player's private thread."""

    def __init__(self, player_cog, user_id: int):
        super().__init__(timeout=None)
        self.player_cog = player_cog
        self.user_id = user_id

    @discord.ui.button(
        label="My Queue Status",
        custom_id="player:status",
        style=discord.ButtonStyle.primary,
        emoji="\U0001f4cb",
    )
    async def check_status(self, interaction: discord.Interaction, button):
        """Show the player their queued actions and their status."""
        actions = await self.player_cog.queue.get_all()
        my_actions = [a for a in actions if a.discord_user_id == self.user_id]

        if not my_actions:
            await interaction.response.send_message(
                "_You have no actions in the queue._", ephemeral=True
            )
            return

        lines = []
        for a in my_actions:
            status_emoji = {
                "pending": "\U0001f7e1",
                "analyzing": "\U0001f50d",
                "awaiting_roll": "\U0001f3b2",
                "ready": "\U0001f7e2",
            }.get(a.status, "\u26aa")
            secret_tag = " [SECRET]" if a.is_secret else ""
            line = f"{status_emoji} \"{a.player_input[:50]}\"{secret_tag} — {a.status}"
            if a.status == "awaiting_roll":
                line += f"\n  Roll needed: {a.roll_type} `{a.roll_formula}`"
            lines.append(line)

        await interaction.response.send_message(
            "**Your queued actions:**\n" + "\n".join(lines),
            ephemeral=True,
        )

    @discord.ui.button(
        label="Help",
        custom_id="player:help",
        style=discord.ButtonStyle.secondary,
        emoji="\u2753",
    )
    async def show_help(self, interaction: discord.Interaction, button):
        """Show help text for the player console."""
        help_text = (
            "**Private Console — Brainstorm Mode**\n"
            "Chat here to brainstorm with your AI advisor!\n\n"
            "**What you can ask:**\n"
            "- \"What abilities do I have?\"\n"
            "- \"How can I sneak past the guards?\"\n"
            "- \"What spells would help here?\"\n"
            "- \"Help me come up with a cool move\"\n\n"
            "**Committing an action:**\n"
            "`!commit <your action>` — sends it to the Game Table\n\n"
            "**Your brainstorming is private.** Only committed actions "
            "are visible to other players.\n\n"
            "**Queue Mode:** When the DM enables queue mode, messages "
            "here become secret actions instead of brainstorming."
        )
        await interaction.response.send_message(help_text, ephemeral=True)


class CharacterImportModal(discord.ui.Modal, title="Import Character Sheet"):
    """Modal for pasting character sheet markdown from the creation wizard."""

    sheet = discord.ui.TextInput(
        label="Paste your character sheet here",
        style=discord.TextStyle.long,
        placeholder="---\nname: Character Name\nrace: Race\nclass: Class\n...",
        max_length=4000,
        required=True,
    )

    def __init__(self, vault: VaultManager, state_manager):
        super().__init__()
        self.vault = vault
        self.state_manager = state_manager

    async def on_submit(self, interaction: discord.Interaction):
        raw = self.sheet.value

        # 1. Parse YAML frontmatter
        frontmatter, body = parse_frontmatter(raw)
        if not frontmatter:
            await interaction.response.send_message(
                "Could not parse YAML frontmatter. Make sure your paste "
                "starts with `---` and has valid YAML.",
                ephemeral=True,
            )
            return

        # 2. Auto-fill player field with Discord username
        if not frontmatter.get("player"):
            frontmatter["player"] = interaction.user.display_name

        # 3. Validate with PartyMember
        try:
            member = PartyMember(**frontmatter)
        except ValidationError as e:
            field_errors = []
            for err in e.errors():
                loc = " → ".join(str(p) for p in err["loc"])
                field_errors.append(f"**{loc}**: {err['msg']}")
            await interaction.response.send_message(
                "Validation failed. Please fix and try again:\n"
                + "\n".join(field_errors),
                ephemeral=True,
            )
            return

        char_name = member.name

        # 4. Write to vault
        file_path = f"{VaultManager.PARTY}/{char_name}.md"
        success = self.vault.write_file(file_path, frontmatter, body)
        if not success:
            await interaction.response.send_message(
                f"Failed to write `{file_path}` to the vault. Check bot logs.",
                ephemeral=True,
            )
            return

        # 5. Upsert to MongoDB (if connected)
        mongo_status = ""
        if self.state_manager and self.state_manager.is_connected:
            try:
                ok = await self.state_manager.upsert_character(frontmatter)
                mongo_status = "Synced to database." if ok else "Database sync failed (validation)."
            except Exception as exc:
                logger.warning(f"MongoDB upsert failed for {char_name}: {exc}")
                mongo_status = "Database unavailable — vault-only."
        else:
            mongo_status = "Database not connected — vault-only."

        # 6. Build confirmation embed
        embed = discord.Embed(
            title=f"Character Imported: {char_name}",
            color=discord.Color.green(),
        )
        embed.add_field(
            name="Race / Class",
            value=f"{frontmatter.get('race', '?')} {frontmatter.get('class', '?')}",
            inline=True,
        )
        embed.add_field(
            name="Level",
            value=str(frontmatter.get("level", 1)),
            inline=True,
        )
        embed.add_field(
            name="HP",
            value=f"{frontmatter.get('hp_current', '?')}/{frontmatter.get('hp_max', '?')}",
            inline=True,
        )
        embed.add_field(name="AC", value=str(frontmatter.get("ac", "?")), inline=True)
        embed.add_field(
            name="Player",
            value=frontmatter.get("player", interaction.user.display_name),
            inline=True,
        )
        embed.set_footer(text=mongo_status)

        logger.info(
            f"Character imported: {char_name} by {interaction.user.name} "
            f"→ {file_path}"
        )
        await interaction.response.send_message(embed=embed)


class _CommitProxy:
    """Minimal message-like object so _handle_game_table can direct output to Game Table."""

    def __init__(self, channel, author):
        self.channel = channel
        self.author = author


class PlayerCog(commands.Cog, name="Player Console"):
    """Per-player private consoles for brainstorming and secret actions."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        from bot.client import action_queue, PLAYER_MAP, GAME_TABLE_CHANNEL_ID
        self.queue = action_queue
        self.player_map = PLAYER_MAP
        self.game_table_id = GAME_TABLE_CHANNEL_ID

    @app_commands.command(
        name="whisper",
        description="Open your private console for secret actions",
    )
    async def whisper_cmd(self, interaction: discord.Interaction):
        """Create a private thread for this player's secret actions."""
        from tools.player_identity import resolve_from_message_author
        user_id = interaction.user.id
        character_name = resolve_from_message_author(interaction.user) or interaction.user.name

        # Check if player already has a thread
        existing_thread_id = self.queue.get_player_thread(user_id)
        if existing_thread_id:
            guild = interaction.guild
            existing = guild.get_thread(existing_thread_id) if guild else None
            if existing and not existing.archived:
                await interaction.response.send_message(
                    f"Your private console is already open: {existing.mention}",
                    ephemeral=True,
                )
                return

        # Create private thread in the current channel
        channel = interaction.channel
        if not isinstance(channel, discord.TextChannel):
            await interaction.response.send_message(
                "Use this in a text channel.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        thread = await channel.create_thread(
            name=f"{character_name}'s Console",
            type=discord.ChannelType.private_thread,
            invitable=False,
        )

        # Register the thread
        self.queue.register_player_thread(user_id, thread.id)

        # Send welcome message with persistent view
        embed = discord.Embed(
            title=f"{character_name}'s Private Console",
            description=(
                "This is your private brainstorming space with the AI advisor.\n\n"
                "**Ask anything** about your character's abilities, spells, "
                "tactics, or what you could do in the current situation. "
                "The advisor knows your character sheet and the game state.\n\n"
                "**When you're ready**, commit your action to the Game Table:\n"
                "`!commit I flip a coin to Durnan and ask about factions`\n\n"
                "Your brainstorming stays private. Only committed actions "
                "appear in the Game Table."
            ),
            color=discord.Color.dark_purple(),
        )
        embed.set_footer(text="Only you and the DM can see this thread.")

        view = PlayerStatusView(self, user_id)
        await thread.send(embed=embed, view=view)

        await interaction.followup.send(
            f"Private console created: {thread.mention}", ephemeral=True
        )
        logger.info(
            f"Player console created for {character_name} "
            f"(user={user_id}, thread={thread.id})"
        )


    @commands.command(name="commit")
    async def commit_cmd(self, ctx, *, action: str):
        """Commit a brainstormed action to the Game Table.

        Usage (in whisper thread): !commit I flip a coin to Durnan and ask about factions
        """
        # Verify this is a player thread
        if not self.queue.is_player_thread(ctx.channel.id):
            await ctx.send("Use this in your private console (`/whisper` thread).")
            return

        from tools.player_identity import resolve_from_message_author
        character_name = resolve_from_message_author(ctx.author) or ctx.author.display_name

        game_channel = self.bot.get_channel(int(self.game_table_id)) if self.game_table_id else None
        if not game_channel:
            await ctx.send("Game Table channel not found.")
            return

        from bot.client import action_queue

        if action_queue.is_queue_mode:
            # Queue mode: add as public action for DM review
            from tools.action_queue import QueuedAction
            queued = QueuedAction(
                discord_user_id=ctx.author.id,
                discord_message_id=ctx.message.id,
                channel_id=int(self.game_table_id),
                character_name=character_name,
                player_input=action,
                is_secret=False,
            )
            await action_queue.enqueue(queued)
            await ctx.send("Action queued for the DM's next turn! Check the Game Table.")
            admin_cog = self.bot.get_cog("Admin Console")
            if admin_cog:
                await admin_cog.refresh_console()
        else:
            # Auto mode: post to Game Table and process through pipeline
            await game_channel.send(f"**{character_name}**: *{action}*")
            await ctx.send("Action committed! Watch the Game Table.")

            from bot.client import _handle_game_table
            proxy = _CommitProxy(channel=game_channel, author=ctx.author)
            await _handle_game_table(proxy, action)

    @app_commands.command(
        name="import",
        description="Import a character sheet from the creation wizard",
    )
    async def import_cmd(self, interaction: discord.Interaction):
        """Open a modal to paste and import a character sheet."""
        vault = getattr(self.bot, "vault", None)
        state_mgr = getattr(self.bot, "state_manager", None)
        if not vault:
            await interaction.response.send_message(
                "Vault is not configured. Cannot import.", ephemeral=True
            )
            return
        modal = CharacterImportModal(vault=vault, state_manager=state_mgr)
        await interaction.response.send_modal(modal)


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCog(bot))
