"""
Prep Cog — Session preparation and worldbuilding commands (War Room).

Commands: !prep, !brainstorm, !plan
"""

import logging
import traceback
import discord
from discord.ext import commands

logger = logging.getLogger("Prep_Cog")


class PrepCog(commands.Cog, name="Prep Commands"):
    """Session preparation — blind prep, brainstorming, and session planning."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        from bot.client import (
            vault, gemini_client, MODEL_ID, foundry_client,
            world_architect, campaign_planner, foundry_architect,
            cartographer_agent, send_to_moderator_log,
            WAR_ROOM_CHANNEL_ID,
        )
        self.vault = vault
        self.gemini_client = gemini_client
        self.model_id = MODEL_ID
        self.foundry_client = foundry_client
        self.world_architect = world_architect
        self.campaign_planner = campaign_planner
        self.foundry_architect = foundry_architect
        self.cartographer_agent = cartographer_agent
        self.send_to_moderator_log = send_to_moderator_log
        self.war_room_channel_id = WAR_ROOM_CHANNEL_ID

    # ------------------------------------------------------------------
    # !prep
    # ------------------------------------------------------------------
    @commands.command(name="prep")
    async def prep_cmd(self, ctx, *, description: str):
        """Blind session prep — AI prepares scenes, NPCs, and encounters without spoilers."""
        from tools.blind_prep import run_blind_prep

        logger.info(f"Blind prep from {ctx.author}: {description}")
        await ctx.send("🧙 **Blind Prep Started** — AI is preparing your session...")
        await ctx.send("*Spoiler-free details will appear in the moderator log.*")

        try:
            async with ctx.typing():
                prep_result = await run_blind_prep(
                    description=description,
                    campaign_planner=self.campaign_planner,
                    world_architect=self.world_architect,
                    foundry_architect=self.foundry_architect,
                    cartographer=self.cartographer_agent,
                    foundry_client=self.foundry_client,
                    gemini_client=self.gemini_client,
                    model_id=self.model_id,
                    vault=self.vault,
                )

            if prep_result.details:
                await self.send_to_moderator_log(prep_result.details)

            embed = discord.Embed(
                title="✅ Session Prep Complete",
                description=prep_result.summary,
                color=0x2ECC71,
            )
            embed.set_footer(text="Check the moderator log for full prep details.")
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Blind prep failed: {e}", exc_info=True)
            await self.send_to_moderator_log(f"[!prep] Error: {traceback.format_exc()}")
            await ctx.send("⚠️ Prep encountered an error. Check the moderator log.")

    # ------------------------------------------------------------------
    # !brainstorm
    # ------------------------------------------------------------------
    @commands.command(name="brainstorm")
    async def brainstorm_cmd(self, ctx, *, topic: str):
        """Brainstorm worldbuilding ideas."""
        if self.war_room_channel_id and str(ctx.channel.id) != self.war_room_channel_id:
            await ctx.send("🗺️ Brainstorming is only available in the War Room channel.")
            return

        logger.info(f"Brainstorm from {ctx.author}: {topic}")
        try:
            async with ctx.typing():
                response = await self.world_architect.brainstorm(topic)
            if len(response) > 2000:
                for i in range(0, len(response), 2000):
                    await ctx.send(response[i : i + 2000])
            else:
                await ctx.send(response)
        except Exception as e:
            logger.error(f"Brainstorm failed: {e}", exc_info=True)
            await self.send_to_moderator_log(f"[!brainstorm] Error: {traceback.format_exc()}")
            await ctx.send("⚠️ Brainstorming failed. Check the log.")

    # ------------------------------------------------------------------
    # !plan
    # ------------------------------------------------------------------
    @commands.command(name="plan")
    async def plan_cmd(self, ctx, *, notes: str):
        """Plan a session."""
        if self.war_room_channel_id and str(ctx.channel.id) != self.war_room_channel_id:
            await ctx.send("🗺️ Session planning is only available in the War Room channel.")
            return

        logger.info(f"Session plan from {ctx.author}: {notes}")
        try:
            async with ctx.typing():
                response = await self.campaign_planner.plan_session(notes)
            if len(response) > 2000:
                for i in range(0, len(response), 2000):
                    await ctx.send(response[i : i + 2000])
            else:
                await ctx.send(response)
        except Exception as e:
            logger.error(f"Session planning failed: {e}", exc_info=True)
            await self.send_to_moderator_log(f"[!plan] Error: {traceback.format_exc()}")
            await ctx.send("⚠️ Session planning failed. Check the log.")


async def setup(bot: commands.Bot):
    await bot.add_cog(PrepCog(bot))
