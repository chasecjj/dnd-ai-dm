"""
Admin Cog — DM Console for managing the action queue, session lifecycle, and game flow.

Commands: /console (slash command)
Creates a private thread with a persistent embed + button controls.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("Admin_Cog")

# Status emoji mapping
STATUS_EMOJI = {
    "pending": "\U0001f7e1",       # yellow circle
    "analyzing": "\U0001f50d",     # magnifying glass
    "awaiting_roll": "\U0001f3b2", # dice
    "ready": "\U0001f7e2",        # green circle
    "resolved": "\u2705",          # check mark
}


class AdminCog(commands.Cog, name="Admin Console"):
    """DM Console for managing the action queue and game flow."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        from bot.client import (
            action_queue,
            vault,
            context_assembler,
            storyteller,
            rules_lawyer,
            foundry_client,
            GAME_TABLE_CHANNEL_ID,
            PLAYER_MAP,
        )
        self.queue = action_queue
        self.vault = vault
        self.context_assembler = context_assembler
        self.storyteller = storyteller
        self.rules_lawyer = rules_lawyer
        self.foundry = foundry_client
        self.game_table_id = GAME_TABLE_CHANNEL_ID
        self.player_map = PLAYER_MAP

        # Console state — tracks where the embed lives
        self._console_thread_id: int | None = None
        self._console_message_id: int | None = None
        self._dm_user_id: int | None = None  # Set when /console is first run

    # ------------------------------------------------------------------
    # Console Creation
    # ------------------------------------------------------------------
    @app_commands.command(name="console", description="Open the DM Admin Console")
    async def console_cmd(self, interaction: discord.Interaction):
        """Create or reopen the DM admin console in a private thread."""
        # Create a private thread in the current channel
        channel = interaction.channel
        if not isinstance(channel, (discord.TextChannel, discord.ForumChannel)):
            await interaction.response.send_message(
                "Use this command in a text channel.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Capture who the DM is (first person to open the console)
        if self._dm_user_id is None:
            self._dm_user_id = interaction.user.id
            logger.info(f"DM identified as user {interaction.user.name} (id={self._dm_user_id})")

        # Reuse existing thread if still valid
        if self._console_thread_id:
            existing = channel.guild.get_thread(self._console_thread_id)
            if existing and not existing.archived:
                await self._refresh_console(existing)
                await interaction.followup.send(
                    f"Console refreshed in {existing.mention}", ephemeral=True
                )
                return

        # Create a new private thread
        thread = await channel.create_thread(
            name="DM Console",
            type=discord.ChannelType.private_thread,
            invitable=False,
        )
        self._console_thread_id = thread.id

        # Import view here to avoid circular imports
        from bot.views.admin_views import AdminConsoleView

        embed = self.build_dashboard_embed()
        view = AdminConsoleView(self)
        msg = await thread.send(embed=embed, view=view)
        self._console_message_id = msg.id

        await interaction.followup.send(
            f"Console created: {thread.mention}", ephemeral=True
        )
        logger.info(f"Admin console created in thread {thread.id}")

    # ------------------------------------------------------------------
    # Embed Builder
    # ------------------------------------------------------------------
    def build_dashboard_embed(self) -> discord.Embed:
        """Build the main dashboard embed showing queue, party, and game state."""
        import asyncio

        # Get queue contents via sync-safe snapshot property
        actions = self.queue.actions_snapshot

        mode_str = "ON" if self.queue.is_queue_mode else "OFF"
        foundry_str = "Connected" if self.foundry.is_connected else "Disconnected"
        session_num = self.context_assembler.current_session

        embed = discord.Embed(
            title="DM Console",
            color=discord.Color.gold() if self.queue.is_queue_mode else discord.Color.greyple(),
        )

        # Header line
        location = getattr(self.storyteller, '_current_location', 'Unknown')
        embed.description = (
            f"**Session {session_num}** | {location}\n"
            f"Queue Mode: **{mode_str}** | Foundry: {foundry_str}\n"
            f"\u2500" * 40
        )

        # Queue section
        if actions:
            queue_lines = []
            for i, action in enumerate(actions, 1):
                emoji = STATUS_EMOJI.get(action.status, "\u26aa")
                name_tag = f"[{action.character_name}]" if action.character_name else "[DM]"
                line = f"{i}. {emoji} {name_tag} \"{action.player_input[:60]}\""
                # Add roll info if present
                for roll in action.rolls:
                    if roll.resolved:
                        dc_str = f" DC {roll.dc}" if roll.dc else ""
                        passed = ""
                        if roll.dc and roll.result is not None and roll.result >= roll.dc:
                            passed = " PASS"
                        elif roll.dc and roll.result is not None:
                            passed = " FAIL"
                        line += f"\n   \U0001f3b2 {roll.roll_type}{dc_str}: **{roll.result}**{passed}"
                    elif roll == action.current_pending_roll:
                        line += f"\n   \u23f3 Waiting: {roll.roll_type} `{roll.formula}`"
                    else:
                        line += f"\n   \u23f3 Queued: {roll.roll_type} `{roll.formula}`"
                if action.dm_annotation:
                    line += f"\n   \U0001f4dd _{action.dm_annotation[:40]}_"
                queue_lines.append(line)
            embed.add_field(
                name=f"Queued Actions ({len(actions)})",
                value="\n".join(queue_lines)[:1024],
                inline=False,
            )
        else:
            embed.add_field(
                name="Queued Actions",
                value="_No actions queued._",
                inline=False,
            )

        # Monster rolls section
        monster_rolls = self.queue.monster_rolls_snapshot
        if monster_rolls:
            roll_lines = []
            for mr in monster_rolls:
                target_str = f" vs {mr.target}" if mr.target else ""
                if mr.result is not None:
                    roll_lines.append(
                        f"\U0001f9cc {mr.monster_name} {mr.roll_type}{target_str}: **{mr.result}** ({mr.detail})"
                    )
                else:
                    roll_lines.append(
                        f"\U0001f9cc {mr.monster_name} {mr.roll_type}{target_str}: _pending..._"
                    )
            embed.add_field(
                name=f"Monster Rolls ({len(monster_rolls)})",
                value="\n".join(roll_lines)[:1024],
                inline=False,
            )

        # Party section
        party_info = self._get_party_summary()
        if party_info:
            embed.add_field(name="Party", value=party_info[:1024], inline=False)

        # Footer
        embed.set_footer(text="Use buttons below to manage the game.")
        return embed

    def _get_party_summary(self) -> str:
        """Build a compact party status string from the vault."""
        try:
            characters = self.vault.list_characters()
            if not characters:
                return "_No characters found._"
            lines = []
            for char_data in characters:
                name = char_data.get("name", "Unknown")
                hp = char_data.get("hp_current", "?")
                hp_max = char_data.get("hp_max", "?")
                ac = char_data.get("ac", "?")
                conditions = char_data.get("conditions", [])
                cond_str = f" | {', '.join(conditions)}" if conditions else ""
                lines.append(f"  {name} \u2014 {hp}/{hp_max} HP | AC {ac}{cond_str}")
            return "\n".join(lines)
        except Exception as e:
            logger.error(f"Party summary error: {e}")
            return "_Could not load party state._"

    # ------------------------------------------------------------------
    # Console Refresh
    # ------------------------------------------------------------------
    async def refresh_console(self):
        """Update the console embed in-place. Called after queue state changes."""
        if not self._console_thread_id or not self._console_message_id:
            return
        try:
            guild = self.bot.guilds[0] if self.bot.guilds else None
            if not guild:
                return
            thread = guild.get_thread(self._console_thread_id)
            if not thread:
                return
            msg = await thread.fetch_message(self._console_message_id)
            embed = self.build_dashboard_embed()
            await msg.edit(embed=embed)
        except discord.NotFound:
            logger.warning("Console message not found — thread may have been deleted.")
            self._console_thread_id = None
            self._console_message_id = None
        except Exception as e:
            logger.error(f"Console refresh error: {e}")

    async def _refresh_console(self, thread: discord.Thread):
        """Refresh console in a specific thread."""
        if not self._console_message_id:
            return
        try:
            msg = await thread.fetch_message(self._console_message_id)
            embed = self.build_dashboard_embed()
            await msg.edit(embed=embed)
        except Exception as e:
            logger.error(f"Console refresh error: {e}")

    # ------------------------------------------------------------------
    # Game Table Helper
    # ------------------------------------------------------------------
    def get_game_table_channel(self) -> discord.TextChannel | None:
        """Get the game table channel for posting prompts/narratives."""
        if not self.game_table_id:
            return None
        try:
            return self.bot.get_channel(int(self.game_table_id))
        except (ValueError, TypeError):
            return None

    def get_console_thread(self) -> discord.Thread | None:
        """Get the admin console thread, if it exists."""
        if not self._console_thread_id:
            return None
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if not guild:
            return None
        return guild.get_thread(self._console_thread_id)

    def is_dm_character(self, action) -> bool:
        """Check if a queued action belongs to the DM's own player character."""
        return (
            self._dm_user_id is not None
            and action.discord_user_id == self._dm_user_id
            and not action.is_dm_event
        )

    def get_dm_character_name(self) -> str | None:
        """Resolve the DM's character name from PLAYER_MAP."""
        if not self._dm_user_id:
            return None
        # Find the DM's discord username from any guild member list
        guild = self.bot.guilds[0] if self.bot.guilds else None
        if guild:
            member = guild.get_member(self._dm_user_id)
            if member:
                return self.player_map.get(member.name.lower())
        return None

    async def send_dm_roll_prompt(self, action, roll_type: str, formula: str, dc: int | None):
        """Send an inline roll button to the console thread for the DM's character.

        Instead of prompting in Game Table (which the DM isn't watching),
        posts a roll button directly in the admin console thread.
        """
        thread = self.get_console_thread()
        if not thread:
            return

        from bot.views.admin_views import InlineRollView

        dc_str = f" DC {dc}" if dc else ""
        view = InlineRollView(self, action.id, formula)
        await thread.send(
            f"\U0001f3b2 **{action.character_name}** needs to roll "
            f"**{roll_type}**{dc_str}: `{formula}`",
            view=view,
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(AdminCog(bot))
