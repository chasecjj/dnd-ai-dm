"""
Sync Cog — Standalone commands for character registration and sync.

Fallback interface for use outside the DM Console (e.g., Game Table or War Room).
The console buttons (Register/Sync) are the primary interface.

Commands:
    !register <character_name>  — Import a Foundry Actor into vault + DB
    !sync                       — Pull latest HP/conditions from Foundry
    !unregister <character_name> — Remove foundry_uuid from vault (keeps the .md file)
"""

import logging
import discord
from discord.ext import commands

logger = logging.getLogger("Sync_Cog")


class SyncCog(commands.Cog, name="Character Sync"):
    """Standalone commands for Foundry ↔ vault character sync."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        from bot.client import vault, state_manager, foundry_client
        self.vault = vault
        self.state_manager = state_manager
        self.foundry = foundry_client

    @commands.command(name="register")
    async def register_cmd(self, ctx: commands.Context, *, character_name: str):
        """Import a Foundry VTT actor into the vault and MongoDB."""
        if not self.foundry.is_connected:
            await ctx.send("Foundry VTT not connected.")
            return

        async with ctx.typing():
            from tools.character_sync import register_character
            result = await register_character(
                name=character_name,
                foundry_client=self.foundry,
                vault_manager=self.vault,
                state_manager=self.state_manager,
                player_discord_name=ctx.author.name,
            )

        if result["success"]:
            data = result["data"]
            embed = discord.Embed(
                title=f"Registered: {data['name']}",
                color=discord.Color.green(),
            )
            embed.add_field(name="Class", value=data["class"], inline=True)
            embed.add_field(name="HP", value=f"{data['hp_current']}/{data['hp_max']}", inline=True)
            embed.add_field(name="AC", value=str(data["ac"]), inline=True)
            embed.set_footer(text=f"UUID: {data['foundry_uuid'][:30]}...")
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"Registration failed: {result['message']}")

    @commands.command(name="sync")
    async def sync_cmd(self, ctx: commands.Context):
        """Pull latest HP/conditions from Foundry for all linked characters."""
        if not self.foundry.is_connected:
            await ctx.send("Foundry VTT not connected.")
            return

        async with ctx.typing():
            from tools.character_sync import sync_foundry_to_local
            changes = await sync_foundry_to_local(
                self.foundry, self.vault, self.state_manager
            )

        if changes:
            lines = [f"  {c['name']}: {c['field']} {c['old']} \u2192 {c['new']}" for c in changes]
            await ctx.send(f"**Synced {len(changes)} change(s):**\n" + "\n".join(lines))
        else:
            await ctx.send("All characters up to date.")

    @commands.command(name="unregister")
    async def unregister_cmd(self, ctx: commands.Context, *, character_name: str):
        """Remove the Foundry UUID from a character (keeps the vault file)."""
        party = self.vault.get_party_state()
        found = False
        for entry in party:
            fm = entry.get("frontmatter", {})
            if fm.get("name", "").lower() == character_name.lower():
                if not fm.get("foundry_uuid"):
                    await ctx.send(f"{fm['name']} is not linked to Foundry.")
                    return
                self.vault.update_party_member(fm["name"], {"foundry_uuid": None})
                await ctx.send(f"Unregistered **{fm['name']}** from Foundry sync. Vault file preserved.")
                found = True
                break
        if not found:
            await ctx.send(f"No party member named '{character_name}' found in vault.")


async def setup(bot: commands.Bot):
    await bot.add_cog(SyncCog(bot))
