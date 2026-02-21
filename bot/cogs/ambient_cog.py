"""
Ambient Cog — Background ambient narration + post-turn story hooks.

Provides two features:
1. Ambient Narration: When the game table is idle for a configurable time,
   generates atmospheric prose (environmental details, NPC activity, time passing).
2. Post-Turn Story Hooks: After each pipeline resolve, generates a 1-2 sentence
   "what happens next" beat to maintain story momentum.

Both features are session-gated and individually togglable.
"""

import time
import logging
import discord
from discord.ext import commands, tasks

from tools.rate_limiter import gemini_limiter

logger = logging.getLogger("AmbientCog")

# Prompts kept short to minimize token usage
AMBIENT_PROMPT = """You are an atmospheric narrator for a D&D game. Generate 1-3 sentences of
ambient description based on the current scene. Focus on sensory details: sounds, smells,
lighting shifts, background NPC activity, weather changes, or subtle environmental hints.

Rules:
- NO dialogue from named NPCs
- NO mechanical effects (damage, conditions, saves)
- NO plot advancement or new encounters
- Keep it short and atmospheric — this is background flavor
- Write in present tense, second person ("You notice...", "The air grows...")
- Do NOT repeat details already established in the scene

Current location: {location}
Recent context: {context}

Write the ambient narration:"""

STORY_HOOK_PROMPT = """You are a D&D Dungeon Master generating a brief story hook after a scene.
Write exactly 1-2 sentences that create forward momentum — a subtle hint, an unresolved detail,
or a sensory shift that makes the players curious about what comes next.

Rules:
- NO dialogue
- NO mechanical effects
- NO new encounters or combat
- NO repeating what just happened
- Just atmosphere and a gentle pull toward "what's next?"
- Write in present tense, second person

What just happened: {narrative}
Current location: {location}

Write the story hook:"""


class AmbientCog(commands.Cog, name="Ambient"):
    """Background ambient narration and post-turn story hooks."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.storyteller = bot.storyteller
        self.context_assembler = bot.context_assembler
        self.gemini_client = bot.gemini_client
        self.model_id = bot.model_id

        # State
        self._last_activity: float = time.time()
        self._idle_threshold: int = 300  # 5 minutes default
        self._session_active: bool = False
        self._ambient_enabled: bool = False
        self._hooks_enabled: bool = False
        self._last_ambient_time: float = 0  # prevents spam

    def cog_unload(self):
        self._ambient_loop.cancel()

    # ------------------------------------------------------------------
    # Session lifecycle (called by admin_views start/end session)
    # ------------------------------------------------------------------
    def set_session_active(self, active: bool):
        self._session_active = active
        if active and not self._ambient_loop.is_running():
            self._ambient_loop.start()
            logger.info("Ambient loop started.")
        elif not active and self._ambient_loop.is_running():
            self._ambient_loop.cancel()
            logger.info("Ambient loop stopped.")

    def record_activity(self):
        """Called on every game table message to reset the idle timer."""
        self._last_activity = time.time()

    # ------------------------------------------------------------------
    # Ambient Narration — background task
    # ------------------------------------------------------------------
    @tasks.loop(minutes=1)
    async def _ambient_loop(self):
        """Check for idle time and generate ambient narration if needed."""
        if not self._session_active or not self._ambient_enabled:
            return

        # Don't fire during queue mode
        aq = getattr(self.bot, "action_queue", None)
        if aq and aq.is_queue_mode:
            return

        idle_seconds = time.time() - self._last_activity
        if idle_seconds < self._idle_threshold:
            return

        # Prevent firing more often than every 3 minutes
        if time.time() - self._last_ambient_time < 180:
            return

        game_table_id = getattr(self.bot, "game_table_channel_id", None)
        if not game_table_id:
            from os import getenv
            game_table_id = getenv("GAME_TABLE_CHANNEL_ID")
        if not game_table_id:
            return

        channel = self.bot.get_channel(int(game_table_id))
        if channel is None:
            return

        try:
            location = self.storyteller._current_location or "Unknown"
            context = self.context_assembler.build_storyteller_context()
            # Trim context to save tokens
            context_short = context[:800] if context else "No recent context."

            prompt = AMBIENT_PROMPT.format(location=location, context=context_short)

            await gemini_limiter.acquire()
            response = await self.gemini_client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config={"temperature": 0.9},
            )

            text = response.text.strip() if response.text else None
            if text:
                # Post as italicized flavor text
                await channel.send(f"*{text}*")

                # Record in context with low impact so it fades quickly
                self.context_assembler.history.add(
                    text=f"[Ambient] {text}",
                    impact=2,
                )
                self._last_ambient_time = time.time()
                self._last_activity = time.time()  # Reset idle timer
                logger.info(f"Ambient narration posted: {text[:60]}...")

        except Exception as e:
            logger.error(f"Ambient narration error: {e}", exc_info=True)

    @_ambient_loop.before_loop
    async def _before_ambient(self):
        await self.bot.wait_until_ready()

    # ------------------------------------------------------------------
    # Post-Turn Story Hook
    # ------------------------------------------------------------------
    async def generate_story_hook(self, narrative: str) -> str | None:
        """Generate a 1-2 sentence story hook based on recent narrative."""
        if not self._hooks_enabled or not self._session_active:
            return None

        if not narrative or len(narrative) < 50:
            return None

        try:
            location = self.storyteller._current_location or "Unknown"
            prompt = STORY_HOOK_PROMPT.format(
                narrative=narrative[:1000],
                location=location,
            )

            await gemini_limiter.acquire()
            response = await self.gemini_client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config={"temperature": 0.9},
            )

            return response.text.strip() if response.text else None

        except Exception as e:
            logger.error(f"Story hook generation error: {e}", exc_info=True)
            return None

    async def post_story_hook(self, channel, narrative: str):
        """Wait briefly then post a story hook after narrative delivery."""
        import asyncio
        await asyncio.sleep(3)

        hook = await self.generate_story_hook(narrative)
        if hook:
            await channel.send(f"*{hook}*")
            self.context_assembler.history.add(
                text=f"[Story Hook] {hook}",
                impact=3,
            )
            logger.info(f"Story hook posted: {hook[:60]}...")

    # ------------------------------------------------------------------
    # Commands
    # ------------------------------------------------------------------
    @commands.command(name="ambient")
    async def ambient_cmd(self, ctx, setting: str = None):  # type: ignore[assignment]
        """Toggle ambient narration. Usage: !ambient [on|off]"""
        if setting is None:
            status = "on" if self._ambient_enabled else "off"
            await ctx.send(f"Ambient narration: **{status}** (idle threshold: {self._idle_threshold}s)")
            return

        if setting.lower() == "on":
            self._ambient_enabled = True
            await ctx.send("Ambient narration **enabled**.")
        elif setting.lower() == "off":
            self._ambient_enabled = False
            await ctx.send("Ambient narration **disabled**.")
        else:
            # Try to set idle threshold
            try:
                seconds = int(setting)
                if 60 <= seconds <= 1800:
                    self._idle_threshold = seconds
                    self._ambient_enabled = True
                    await ctx.send(f"Ambient narration enabled. Idle threshold: **{seconds}s**.")
                else:
                    await ctx.send("Threshold must be between 60 and 1800 seconds.")
            except ValueError:
                await ctx.send("Usage: `!ambient [on|off|<seconds>]`")

    @commands.command(name="hooks")
    async def hooks_cmd(self, ctx, setting: str = None):  # type: ignore[assignment]
        """Toggle post-turn story hooks. Usage: !hooks [on|off]"""
        if setting is None:
            status = "on" if self._hooks_enabled else "off"
            await ctx.send(f"Story hooks: **{status}**")
            return

        if setting.lower() == "on":
            self._hooks_enabled = True
            await ctx.send("Post-turn story hooks **enabled**.")
        elif setting.lower() == "off":
            self._hooks_enabled = False
            await ctx.send("Post-turn story hooks **disabled**.")
        else:
            await ctx.send("Usage: `!hooks [on|off]`")


async def setup(bot: commands.Bot):
    await bot.add_cog(AmbientCog(bot))
