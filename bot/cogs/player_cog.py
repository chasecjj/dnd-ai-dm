"""
Player Cog — Per-player private console for secret actions and individual decisions.

Commands: /whisper (slash command) — creates a private thread for the player
Players can type actions in their private thread that only the DM sees.
"""

import logging
import discord
from discord import app_commands
from discord.ext import commands

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
            "**Private Console**\n"
            "Type actions here that only the DM will see.\n\n"
            "**How it works:**\n"
            "- Your message is added to the DM's queue as a *secret action*\n"
            "- Other players won't know what you did\n"
            "- The DM resolves it during the turn\n"
            "- Results appear here in your private thread\n\n"
            "**Dice rolls:** If the DM needs you to roll, "
            "you'll be prompted in the Game Table channel with `!roll`.\n\n"
            "**Regular actions:** Use the Game Table channel for "
            "actions the whole party should see."
        )
        await interaction.response.send_message(help_text, ephemeral=True)


class PlayerCog(commands.Cog, name="Player Console"):
    """Per-player private consoles for secret actions."""

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
        user_id = interaction.user.id
        discord_name = interaction.user.name.lower()
        character_name = self.player_map.get(discord_name, discord_name)

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
                "This is your private channel with the DM.\n\n"
                "**Type any action here** and it will be added to the DM's "
                "queue as a *secret action*. Other players won't see it.\n\n"
                "The DM will resolve your action during the turn, and the "
                "results will appear here."
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


async def setup(bot: commands.Bot):
    await bot.add_cog(PlayerCog(bot))
