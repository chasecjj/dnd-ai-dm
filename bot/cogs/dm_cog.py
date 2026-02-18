"""
DM Cog — Campaign management, party status, session recap, and utility commands.

Commands: !campaign, !save, !reset, !recap, !status, !image
"""

import os
import logging
import discord
from discord.ext import commands

logger = logging.getLogger("DM_Cog")


class DMCog(commands.Cog, name="DM Commands"):
    """Campaign management, party status, and session utilities."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # Import shared state from bot.client
        from bot.client import (
            campaign_manager, vault, context_assembler, storyteller,
            ref_manager,
        )
        self.campaign_manager = campaign_manager
        self.vault = vault
        self.context_assembler = context_assembler
        self.storyteller = storyteller
        self.ref_manager = ref_manager

    # ------------------------------------------------------------------
    # !campaign group
    # ------------------------------------------------------------------
    @commands.group(name="campaign", invoke_without_command=True)
    async def campaign_cmd(self, ctx):
        """Manage campaigns. Subcommands: list, new, load"""
        await ctx.send("available subcommands: `list`, `new`, `load`")

    @campaign_cmd.command(name="list")
    async def campaign_list(self, ctx):
        """List all available campaigns."""
        campaigns = self.campaign_manager.list_campaigns()
        active = self.campaign_manager.get_active_campaign()
        lines = ["**Available Campaigns:**"]
        for c in campaigns:
            icon = "🟢" if c == active else "⚪"
            lines.append(f"{icon} {c}")
        await ctx.send("\n".join(lines))

    @campaign_cmd.command(name="new")
    async def campaign_new(self, ctx, *, name: str):
        """Create a new campaign."""
        safe_name = "".join(c for c in name if c.isalnum() or c in " -_").strip()
        if not safe_name:
            await ctx.send("❌ Invalid campaign name.")
            return
        if self.campaign_manager.create_campaign(safe_name):
            await ctx.send(f"✅ Created campaign **{safe_name}**. Use `!campaign load {safe_name}` to switch.")
        else:
            await ctx.send(f"❌ Failed to create campaign **{safe_name}**. It might already exist.")

    @campaign_cmd.command(name="load")
    async def campaign_load(self, ctx, *, name: str):
        """Switch to a different campaign."""
        if self.campaign_manager.set_campaign(name):
            self.context_assembler.history.clear()
            clock = self.vault.read_world_clock()
            loc = clock.get("current_location", "Unknown")
            self.storyteller.set_location(loc)
            await ctx.send(f"✅ **Loaded Campaign: {name}**\n📍 Location: {loc}\n📝 Memory cleared for new context.")
        else:
            await ctx.send(f"❌ Failed to load campaign **{name}**. Does it exist?")

    # ------------------------------------------------------------------
    # !save
    # ------------------------------------------------------------------
    @commands.command(name="save")
    async def save_game(self, ctx):
        """Confirm that the game state is saved."""
        await ctx.send("💾 **Game Saved.** (Vault state is persistent)")

    # ------------------------------------------------------------------
    # !reset
    # ------------------------------------------------------------------
    @commands.command(name="reset")
    async def reset_game(self, ctx):
        """Resets agent state (conversation history). Vault data is preserved."""
        await ctx.send(
            "⚠️ This will clear the conversation memory (history will decay). "
            "Vault files are **not** affected.\nReact with ✅ to confirm or ❌ to cancel."
        )
        confirm_msg = await ctx.send("Waiting for confirmation...")
        await confirm_msg.add_reaction("✅")
        await confirm_msg.add_reaction("❌")

        def check(reaction, user):
            return (
                user == ctx.author
                and str(reaction.emoji) in ["✅", "❌"]
                and reaction.message.id == confirm_msg.id
            )

        try:
            reaction, _ = await self.bot.wait_for("reaction_add", timeout=30.0, check=check)
            if str(reaction.emoji) == "✅":
                self.context_assembler.history.clear()
                logger.info(f"Conversation history cleared by {ctx.author}")
                await ctx.send("✅ **Memory cleared.** Vault data intact. Ready to continue! 🎲")
            else:
                await ctx.send("❌ Reset cancelled.")
        except Exception:
            await ctx.send("⏰ Reset timed out — no changes made.")

    # ------------------------------------------------------------------
    # !recap
    # ------------------------------------------------------------------
    @commands.command(name="recap")
    async def recap(self, ctx, session_num: int = None):  # type: ignore[assignment]
        """Shows a recap of the specified session (or the latest)."""
        try:
            if session_num is not None:
                result = self.vault.get_session(session_num)
                if not result:
                    await ctx.send(f"❌ Session {session_num} not found.")
                    return
                fm, body = result
            else:
                result = self.vault.get_latest_session()
                if not result:
                    await ctx.send("❌ No session logs found.")
                    return
                fm, body = result

            session_title = f"Session {fm.get('session_number', '?')}"
            date = fm.get("ingame_date", "?")
            location = fm.get("location", "?")

            summary = ""
            in_summary = False
            for line in body.split("\n"):
                if line.strip().startswith("## Summary"):
                    in_summary = True
                    continue
                if line.strip().startswith("## ") and in_summary:
                    break
                if in_summary:
                    summary += line + "\n"

            recap_text = f"📜 **{session_title}** — {date} @ {location}\n\n{summary.strip()}"
            if len(recap_text) > 2000:
                recap_text = recap_text[:1997] + "..."
            await ctx.send(recap_text)
        except Exception as e:
            logger.error(f"Recap command failed: {e}", exc_info=True)
            await ctx.send("⚠️ Couldn't generate recap. Check the log.")

    # ------------------------------------------------------------------
    # !status
    # ------------------------------------------------------------------
    @commands.command(name="status")
    async def party_status(self, ctx):
        """Shows current party status from the vault."""
        try:
            party = self.vault.get_party_state()
            if not party:
                await ctx.send("❌ No party data found in the vault.")
                return
            clock = self.vault.read_world_clock()
            status_lines = [f"⏰ **{clock.get('current_date', '?')}** — {clock.get('time_of_day', '?')}", ""]
            for member in party:
                fm = member["frontmatter"]
                name = fm.get("name", "?")
                hp_cur = fm.get("hp_current", "?")
                hp_max = fm.get("hp_max", "?")
                ac = fm.get("ac", "?")
                conditions = fm.get("conditions", [])
                cond_str = f" | ⚡ {', '.join(conditions)}" if conditions else ""
                status_lines.append(f"🛡️ **{name}** — HP: {hp_cur}/{hp_max} | AC: {ac}{cond_str}")
            quests = self.vault.get_active_quests()
            if quests:
                status_lines.append("")
                status_lines.append("📋 **Active Quests:**")
                for q in quests:
                    qfm = q["frontmatter"]
                    status_lines.append(f"  • {qfm.get('name', '?')} ({qfm.get('status', '?')})")
            await ctx.send("\n".join(status_lines))
        except Exception as e:
            logger.error(f"Status command failed: {e}", exc_info=True)
            await ctx.send("⚠️ Couldn't fetch status. Check the log.")

    # ------------------------------------------------------------------
    # !image
    # ------------------------------------------------------------------
    @commands.command(name="image")
    async def image_search(self, ctx, *, query: str):
        """Search for images from D&D source books."""
        logger.info(f"Image search from {ctx.author}: {query}")
        try:
            results = self.ref_manager.find_asset(query, max_results=3)
            if not results:
                await ctx.send(f"🔍 No images found for **{query}**. Try different keywords.")
                return
            for asset in results:
                filepath = asset["file"]
                if not os.path.exists(filepath):
                    logger.warning(f"Asset file not found: {filepath}")
                    continue
                book_name = asset["book_slug"].replace("_", " ").title()
                embed = discord.Embed(
                    title=f"📖 {book_name} — Page {asset['page']}",
                    description=asset.get("context", "")[:200],
                    color=0x7B2D26,
                )
                embed.set_footer(text=f"{asset['width']}×{asset['height']}px | {asset['size_bytes'] // 1024} KB")
                file = discord.File(filepath, filename=os.path.basename(filepath))
                embed.set_image(url=f"attachment://{os.path.basename(filepath)}")
                await ctx.send(embed=embed, file=file)
        except Exception as e:
            logger.error(f"Image search failed: {e}", exc_info=True)
            await ctx.send("⚠️ Image search failed. Check the log.")


async def setup(bot: commands.Bot):
    await bot.add_cog(DMCog(bot))
