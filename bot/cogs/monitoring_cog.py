"""
Monitoring Cog — Bot health and pipeline observability.

Commands:
  /bot-status     — System health overview (ephemeral)
  /solo-sessions  — List active solo adventures (ephemeral)
"""

import time
import logging
import discord
from discord import app_commands
from discord.ext import commands

logger = logging.getLogger("Monitoring_Cog")


def _format_uptime(seconds: float) -> str:
    """Format seconds into a human-readable uptime string."""
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m {seconds % 60}s"
    hours = minutes // 60
    remaining_min = minutes % 60
    if hours < 24:
        return f"{hours}h {remaining_min}m"
    days = hours // 24
    remaining_hours = hours % 24
    return f"{days}d {remaining_hours}h {remaining_min}m"


def _status_dot(ok: bool) -> str:
    """Green or red status dot."""
    return "\u25cf" if ok else "\u25cb"  # ● or ○


class MonitoringCog(commands.Cog, name="Monitoring"):
    """Bot health and pipeline observability commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(
        name="bot-status", description="Show bot system health and pipeline stats"
    )
    async def system_status(self, interaction: discord.Interaction):
        """Display a health overview of all system components."""
        await interaction.response.defer(ephemeral=True)

        metrics = self.bot.pipeline_metrics
        summary = metrics.get_summary()

        # --- System Components ---
        # Discord
        latency_ms = round(self.bot.latency * 1000)
        discord_ok = self.bot.is_ready()
        discord_line = f"{_status_dot(discord_ok)} **Discord** \u2014 Connected ({latency_ms}ms latency)"

        # Gemini
        gemini_ok = self.bot.gemini_client is not None
        gemini_detail = "Client loaded"
        try:
            from tools.rate_limiter import gemini_limiter
            tokens = int(gemini_limiter.available)
            gemini_detail += f" ({tokens}/{gemini_limiter.max_tokens} tokens)"
        except Exception:
            pass
        if not gemini_ok:
            gemini_detail = "NOT LOADED"
        gemini_line = f"{_status_dot(gemini_ok)} **Gemini** \u2014 {gemini_detail}"

        # MongoDB
        mongo_ok = self.bot.state_manager.is_connected
        mongo_detail = "Connected" if mongo_ok else "Vault-only mode"
        mongo_line = f"{_status_dot(mongo_ok)} **MongoDB** \u2014 {mongo_detail}"

        # Foundry
        foundry_ok = self.bot.foundry_client.is_connected
        foundry_detail = "Connected"
        if foundry_ok:
            cid = getattr(self.bot.foundry_client, "client_id", None)
            if cid:
                foundry_detail += f" (client={cid})"
        else:
            foundry_detail = "Disconnected"
        foundry_line = f"{_status_dot(foundry_ok)} **Foundry** \u2014 {foundry_detail}"

        components = (
            f"{discord_line}\n{gemini_line}\n{mongo_line}\n{foundry_line}"
        )

        # --- Pipeline Stats ---
        total = summary["total_requests"]
        if total > 0:
            success_pct = round(summary["success_count"] / total * 100, 1)
            pipeline_stats = (
                f"**Requests:** {total} total "
                f"({summary['group_requests']} group, {summary['solo_requests']} solo)\n"
                f"**Success:** {summary['success_count']}/{total} ({success_pct}%)\n"
                f"**Avg latency:** {summary['avg_latency']}s"
            )

            # Last request timing
            secs_ago = summary["seconds_since_last"]
            if secs_ago is not None:
                pipeline_stats += f"\n**Last request:** {_format_uptime(secs_ago)} ago"

            # Slowest node
            if summary["slowest_node"]:
                pipeline_stats += (
                    f"\n**Slowest node:** {summary['slowest_node']} "
                    f"(avg {summary['slowest_node_avg']}s)"
                )

            # Per-node breakdown
            node_avgs = summary.get("node_averages", {})
            if node_avgs:
                node_lines = []
                for name in ["router", "board", "rules", "storyteller", "scene_sync", "chronicler"]:
                    if name in node_avgs:
                        node_lines.append(f"`{name}`: {node_avgs[name]}s")
                if node_lines:
                    pipeline_stats += "\n**Node averages:** " + " \u2022 ".join(node_lines)
        else:
            pipeline_stats = "No requests processed yet."

        # --- Errors ---
        error_section = ""
        if summary["error_types"]:
            error_lines = [
                f"`{etype}`: {count}"
                for etype, count in sorted(
                    summary["error_types"].items(), key=lambda x: -x[1]
                )
            ]
            error_section = "\n".join(error_lines)
        else:
            error_section = "None"

        # --- Solo Sessions ---
        solo_count = len(self.bot.solo_manager.all_active())

        # --- Uptime ---
        uptime_str = _format_uptime(summary["uptime_seconds"])

        # --- Embed color based on error rate ---
        error_pct = summary["error_rate"]
        if error_pct >= 20:
            color = discord.Color.red()
        elif error_pct >= 5:
            color = discord.Color.yellow()
        else:
            color = discord.Color.green()

        embed = discord.Embed(
            title="Bot Status",
            color=color,
        )
        embed.add_field(name="System Components", value=components, inline=False)
        embed.add_field(name="Pipeline Stats", value=pipeline_stats, inline=False)
        embed.add_field(name="Errors", value=error_section, inline=True)
        embed.add_field(
            name="Solo Sessions",
            value=f"{solo_count} active",
            inline=True,
        )
        embed.add_field(name="Uptime", value=uptime_str, inline=True)

        await interaction.followup.send(embed=embed, ephemeral=True)

    @app_commands.command(
        name="solo-sessions",
        description="List active solo adventure sessions",
    )
    async def solo_sessions(self, interaction: discord.Interaction):
        """Show all currently active solo adventure sessions."""
        sessions = self.bot.solo_manager.all_active()

        if not sessions:
            embed = discord.Embed(
                title="Solo Sessions",
                description="No active solo sessions.",
                color=discord.Color.light_grey(),
            )
            await interaction.response.send_message(embed=embed, ephemeral=True)
            return

        lines = []
        now = time.time()
        for s in sessions:
            elapsed = _format_uptime(now - s.started_at)
            lines.append(
                f"**{s.character_name}**\n"
                f"\u2003Thread: <#{s.thread_id}>\n"
                f"\u2003Location: {s.current_location}\n"
                f"\u2003Turns: {s.turn_count} \u00b7 Elapsed: {elapsed}"
            )

        embed = discord.Embed(
            title=f"Solo Sessions ({len(sessions)} active)",
            description="\n\n".join(lines),
            color=discord.Color.purple(),
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(MonitoringCog(bot))
