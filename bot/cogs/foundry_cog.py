"""
Foundry Cog — All Foundry VTT-related commands.

Commands: !roll, !monster, !scene, !pc, !build, !daytime, !nighttime, !setup, !foundry
"""

import asyncio
import math
import random
import json as json_mod
import logging
import traceback
import discord
from discord.ext import commands

from google import genai

logger = logging.getLogger("Foundry_Cog")


def _calculate_positions(
    count: int,
    formation: str,
    scene_width: int,
    scene_height: int,
    grid_size: int,
) -> list:
    """Calculate token positions based on formation type."""
    cx = scene_width // 2
    cy = scene_height // 2
    spread = grid_size * 3

    positions = []

    if formation == "clustered":
        for i in range(count):
            angle = (2 * math.pi * i) / max(count, 1)
            r = spread if count > 1 else 0
            x = int(cx + r * math.cos(angle))
            y = int(cy + r * math.sin(angle))
            positions.append((x, y))
    elif formation == "surrounding":
        ring_radius = spread * 2
        for i in range(count):
            angle = (2 * math.pi * i) / max(count, 1)
            x = int(cx + ring_radius * math.cos(angle))
            y = int(cy + ring_radius * math.sin(angle))
            positions.append((x, y))
    elif formation == "defensive":
        start_x = cx - (count * grid_size) // 2
        for i in range(count):
            x = start_x + i * grid_size * 2
            y = cy
            positions.append((x, y))
    elif formation == "ambush":
        half = count // 2
        for i in range(half):
            x = cx - spread * 3
            y = cy - (half * grid_size) // 2 + i * grid_size * 2
            positions.append((x, y))
        for i in range(count - half):
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
        (max(margin, min(x, scene_width - margin)), max(margin, min(y, scene_height - margin)))
        for x, y in positions
    ]
    return positions


class FoundryCog(commands.Cog, name="Foundry VTT Commands"):
    """Foundry VTT integration — dice, monsters, scenes, encounters."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        from bot.client import (
            foundry_client, foundry_architect, gemini_client, MODEL_ID,
            send_to_moderator_log, action_queue,
        )
        self.foundry = foundry_client
        self.foundry_architect = foundry_architect
        self.gemini_client = gemini_client
        self.model_id = MODEL_ID
        self.send_to_moderator_log = send_to_moderator_log
        self.action_queue = action_queue

    # ------------------------------------------------------------------
    # !foundry — health check
    # ------------------------------------------------------------------
    @commands.command(name="foundry")
    async def foundry_status_cmd(self, ctx):
        """Show Foundry VTT connection status."""
        try:
            status = await self.foundry.health_check()

            relay_ok = status.get('relay_reachable', False)
            foundry_ok = status.get('foundry_connected', False)
            client_id = status.get('client_id', 'N/A')

            if relay_ok and foundry_ok:
                color = discord.Color.green()
                overall = "Connected"
            elif relay_ok:
                color = discord.Color.orange()
                overall = "Relay OK — Foundry Offline"
            else:
                color = discord.Color.red()
                overall = "Disconnected"

            embed = discord.Embed(
                title="Foundry VTT Status",
                description=overall,
                color=color,
            )
            embed.add_field(
                name="Relay Server",
                value=f"{'Online' if relay_ok else 'Offline'}",
                inline=True,
            )
            embed.add_field(
                name="Foundry VTT",
                value=f"{'Connected' if foundry_ok else 'Not Connected'}",
                inline=True,
            )
            embed.add_field(name="Client ID", value=client_id or "N/A", inline=True)
            await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Foundry status check failed: {e}", exc_info=True)
            await ctx.send(f"Foundry VTT Status: Disconnected ({e})")

    # ------------------------------------------------------------------
    # !setup
    # ------------------------------------------------------------------
    @commands.command(name="setup")
    async def setup_encounter(self, ctx, *, prompt: str):
        """Sets up an encounter in Foundry VTT."""
        logger.info(f"Received setup command from {ctx.author}: {prompt}")
        await ctx.send("Architect is drafting plans...")
        try:
            response = str(await self.foundry_architect.process_request(prompt))
            if len(response) > 2000:
                for i in range(0, len(response), 2000):
                    await ctx.send(response[i : i + 2000])
            else:
                await ctx.send(response)
        except Exception as e:
            logger.error(f"Setup command failed: {e}")
            await self.send_to_moderator_log(
                f"[!setup] Error from {ctx.author}:\nPrompt: {prompt}\n{traceback.format_exc()}"
            )
            await ctx.send("Something went wrong setting up the encounter. The DM has been notified.")

    # ------------------------------------------------------------------
    # !roll
    # ------------------------------------------------------------------
    @commands.command(name="roll")
    async def roll_cmd(self, ctx, *, expression: str):
        """Roll dice using Foundry's dice engine."""
        parts = expression.split(None, 1)
        formula = parts[0]
        reason = parts[1] if len(parts) > 1 else ""

        if not self.foundry.is_connected:
            await ctx.send("Foundry VTT not connected. Cannot roll dice remotely.")
            return

        try:
            result = await self.foundry.roll_dice(formula)
            total = result["total"]
            is_crit = result.get("isCritical", False)
            is_fumble = result.get("isFumble", False)

            dice_details = []
            for die_group in result.get("dice", []):
                faces = die_group.get("faces", "?")
                rolls = [r.get("result", "?") for r in die_group.get("results", [])]
                active = [r.get("result", "?") for r in die_group.get("results", []) if r.get("active", True)]
                if len(rolls) != len(active):
                    dice_details.append(f"d{faces}: [{', '.join(str(r) for r in rolls)}] -> kept {active}")
                else:
                    dice_details.append(f"d{faces}: [{', '.join(str(r) for r in rolls)}]")

            reason_str = f" ({reason})" if reason else ""
            dice_str = " ".join(dice_details) if dice_details else ""

            if is_crit:
                response = f"**NAT 20!** `{formula}`{reason_str}: **{total}** {dice_str}"
            elif is_fumble:
                response = f"**NAT 1!** `{formula}`{reason_str}: **{total}** {dice_str}"
            else:
                response = f"`{formula}`{reason_str}: **{total}** {dice_str}"

            await ctx.send(response)

            # Intercept: check if this roll fulfills a pending queue request
            if self.action_queue.is_queue_mode:
                detail = f"{formula}: {' '.join(dice_details)} = {total}" if dice_details else f"{formula} = {total}"
                action, next_roll = await self.action_queue.update_roll_result(
                    user_id=ctx.author.id,
                    result=total,
                    detail=detail,
                )
                if action:
                    admin_cog = self.bot.get_cog("Admin Console")
                    # If there's another roll in the sequence, prompt for it
                    if next_roll:
                        if admin_cog and admin_cog.is_dm_character(action):
                            await admin_cog.send_dm_roll_prompt(
                                action, next_roll.roll_type, next_roll.formula, next_roll.dc,
                            )
                        elif action.character_name:
                            await ctx.send(
                                f"**{action.character_name}**, now roll {next_roll.roll_type}: "
                                f"`!roll {next_roll.formula}`"
                            )
                    if admin_cog:
                        await admin_cog.refresh_console()

        except Exception as e:
            logger.error(f"Roll command failed: {e}", exc_info=True)
            await ctx.send(f"Roll failed: {e}")

    # ------------------------------------------------------------------
    # !monster
    # ------------------------------------------------------------------
    @commands.command(name="monster")
    async def monster_cmd(self, ctx, *, name: str):
        """Look up a monster's stat block."""
        if not self.foundry.is_connected:
            await ctx.send("Foundry VTT not connected.")
            return

        try:
            async with ctx.typing():
                results = await self.foundry.search_actors(name)
                if not results:
                    await ctx.send(f"No monsters found for **{name}**.")
                    return

                actor = results[0]
                uuid = actor.get("uuid", "")
                stat = await self.foundry.get_actor_stat_block(uuid)

                ab = stat.get("abilities", {})
                ab_line = " | ".join(
                    f"**{a.upper()}** {ab[a]['value']}({ab[a]['mod']:+d})"
                    for a in ["str", "dex", "con", "int", "wis", "cha"]
                    if a in ab
                )

                hp = stat.get("hp", {})
                hp_str = f"{hp.get('max', '?')}"
                if hp.get("formula"):
                    hp_str += f" ({hp['formula']})"

                mv = stat.get("movement", {})
                speed = str(mv.get("walk", "30")) + " ft."
                for mode in ["fly", "swim", "climb", "burrow"]:
                    if mv.get(mode) and mv[mode] != "0":
                        speed += f", {mode} {mv[mode]} ft."

                embed = discord.Embed(
                    title=f"{stat['name']}",
                    description=f"*{stat.get('type', 'npc').title()}* | CR {stat.get('cr', '?')}",
                    color=0xCC0000,
                )
                embed.add_field(name="HP", value=hp_str, inline=True)
                embed.add_field(name="AC", value=str(stat.get("ac", "?")), inline=True)
                embed.add_field(name="Speed", value=speed, inline=True)
                embed.add_field(name="Abilities", value=ab_line, inline=False)

                features = stat.get("features", [])
                if features:
                    embed.add_field(name="Features", value=", ".join(features[:15]), inline=False)

                equipment = stat.get("equipment", [])
                if equipment:
                    embed.add_field(name="Equipment", value=", ".join(equipment[:10]), inline=False)

                spells = stat.get("spells", [])
                if spells:
                    spell_text = ", ".join(s["name"] for s in spells[:15])
                    embed.add_field(name="Spells", value=spell_text, inline=False)

                if len(results) > 1:
                    others = ", ".join(r["name"] for r in results[1:5])
                    embed.set_footer(text=f"Also found: {others}")

                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Monster command failed: {e}", exc_info=True)
            await ctx.send(f"Monster lookup failed: {e}")

    # ------------------------------------------------------------------
    # !scene
    # ------------------------------------------------------------------
    @commands.command(name="scene")
    async def scene_cmd(self, ctx, *, query: str):
        """Search for battle maps / scenes."""
        if not self.foundry.is_connected:
            await ctx.send("Foundry VTT not connected.")
            return

        try:
            async with ctx.typing():
                results = await self.foundry.search_scenes(query)
                if not results:
                    await ctx.send(f"No scenes found for **{query}**.")
                    return

                embed = discord.Embed(
                    title=f"Scenes matching '{query}'",
                    description=f"Found {len(results)} scene(s)",
                    color=0x2E8B57,
                )
                for scene in results[:10]:
                    source = scene.get("packageName", "World")
                    embed.add_field(
                        name=scene["name"],
                        value=f"Source: {source}\n`{scene.get('uuid', 'N/A')}`",
                        inline=True,
                    )
                if len(results) > 10:
                    embed.set_footer(text=f"Showing 10 of {len(results)} results")
                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"Scene command failed: {e}", exc_info=True)
            await ctx.send(f"Scene search failed: {e}")

    # ------------------------------------------------------------------
    # !pc
    # ------------------------------------------------------------------
    @commands.command(name="pc")
    async def pc_cmd(self, ctx, *, name: str):
        """Look up a player character or any actor's details."""
        if not self.foundry.is_connected:
            await ctx.send("Foundry VTT not connected.")
            return

        try:
            async with ctx.typing():
                results = await self.foundry.search_actors(name)
                if not results:
                    await ctx.send(f"No character found for **{name}**. Try a different name.")
                    return

                actor = results[0]
                uuid = actor.get("uuid", "")
                stat = await self.foundry.get_actor_stat_block(uuid)

                ab = stat.get("abilities", {})
                ab_line = " | ".join(
                    f"**{a.upper()}** {ab[a]['value']}({ab[a]['mod']:+d})"
                    for a in ["str", "dex", "con", "int", "wis", "cha"]
                    if a in ab
                )

                hp = stat.get("hp", {})
                hp_str = f"{hp.get('current', '?')}/{hp.get('max', '?')}"

                char_type = stat.get("type", "character").title()
                details = stat.get("details", {})
                race = details.get("race", {}) if isinstance(details.get("race"), dict) else {}
                race_name = race.get("name", "") if race else ""
                level_info = details.get("level", "")

                desc = f"*{char_type}*"
                if race_name:
                    desc += f" | {race_name}"
                if level_info:
                    desc += f" | Level {level_info}"

                embed = discord.Embed(title=stat['name'], description=desc, color=0x4169E1)
                embed.add_field(name="HP", value=hp_str, inline=True)
                embed.add_field(name="AC", value=str(stat.get("ac", "?")), inline=True)
                embed.add_field(name="Abilities", value=ab_line, inline=False)

                spells = stat.get("spells", [])
                if spells:
                    by_level: dict[int, list[str]] = {}
                    for s in spells:
                        lvl = s.get("level", 0)
                        by_level.setdefault(lvl, []).append(s["name"])
                    spell_lines = []
                    for lvl in sorted(by_level.keys()):
                        label = "Cantrips" if lvl == 0 else f"Lvl {lvl}"
                        spell_lines.append(f"**{label}:** {', '.join(by_level[lvl])}")
                    spell_text = "\n".join(spell_lines)
                    if len(spell_text) > 1024:
                        spell_text = spell_text[:1021] + "..."
                    embed.add_field(name="Spells", value=spell_text, inline=False)

                features = stat.get("features", [])
                if features:
                    feat_text = ", ".join(features[:20])
                    if len(feat_text) > 1024:
                        feat_text = feat_text[:1021] + "..."
                    embed.add_field(name="Features", value=feat_text, inline=False)

                equipment = stat.get("equipment", [])
                if equipment:
                    equip_text = ", ".join(equipment[:15])
                    if len(equip_text) > 1024:
                        equip_text = equip_text[:1021] + "..."
                    embed.add_field(name="Equipment", value=equip_text, inline=False)

                await ctx.send(embed=embed)

        except Exception as e:
            logger.error(f"PC command failed: {e}", exc_info=True)
            await ctx.send(f"Character lookup failed: {e}")

    # ------------------------------------------------------------------
    # !daytime / !nighttime — only affect the ACTIVE scene
    # ------------------------------------------------------------------
    @commands.command(name="daytime")
    async def daytime_cmd(self, ctx):
        """Set the active scene to daytime lighting."""
        if not self.foundry.is_connected:
            await ctx.send("Foundry VTT not connected.")
            return
        try:
            scenes = await self.foundry.get_world_scenes()
            active = [s for s in scenes if s.get("active")]
            if not active:
                await ctx.send("No active scene found.")
                return
            scene = active[0]
            await self.foundry.update_scene_lighting(scene["uuid"], darkness=0.0)
            await ctx.send(f"**Daytime!** Lighting on **{scene.get('name', '?')}** set to full brightness.")
        except Exception as e:
            logger.error(f"Daytime command failed: {e}", exc_info=True)
            await ctx.send(f"Failed to set daytime: {e}")

    @commands.command(name="nighttime")
    async def nighttime_cmd(self, ctx):
        """Set the active scene to nighttime lighting."""
        if not self.foundry.is_connected:
            await ctx.send("Foundry VTT not connected.")
            return
        try:
            scenes = await self.foundry.get_world_scenes()
            active = [s for s in scenes if s.get("active")]
            if not active:
                await ctx.send("No active scene found.")
                return
            scene = active[0]
            await self.foundry.update_scene_lighting(scene["uuid"], darkness=1.0)
            await ctx.send(f"**Nighttime!** Lighting on **{scene.get('name', '?')}** set to darkness.")
        except Exception as e:
            logger.error(f"Nighttime command failed: {e}", exc_info=True)
            await ctx.send(f"Failed to set nighttime: {e}")

    # ------------------------------------------------------------------
    # !build — with parallel monster searches
    # ------------------------------------------------------------------
    @commands.command(name="build")
    async def build_cmd(self, ctx, *, description: str):
        """Build an encounter on a scene — searches monsters, picks map, places tokens."""
        if not self.foundry.is_connected:
            await ctx.send("Foundry VTT not connected.")
            return

        logger.info(f"Build command from {ctx.author}: {description}")
        status_msg = await ctx.send("**Encounter Builder** — Analyzing your request...")

        try:
            async with ctx.typing():
                # Step 1: AI-extract monsters, scene, positioning
                build_prompt = f"""You are an encounter builder for D&D 5e using Foundry VTT.
Analyze this encounter description and produce a JSON plan.

Description: {description}

Return a JSON object with:
{{
    "scene_keywords": ["keyword1", "keyword2"],
    "monsters": [
        {{"name": "Goblin", "count": 4, "role": "ambusher"}}
    ],
    "formation": "ambush|defensive|scattered|clustered|surrounding",
    "lighting": 0.0
}}

Rules:
- scene_keywords: 2-3 words to search for battle maps
- monsters: Use standard D&D 5e monster names
- formation: How the monsters should be arranged
- lighting: 0.0 = daylight, 0.5 = twilight, 1.0 = darkness

JSON:"""

                response = await self.gemini_client.aio.models.generate_content(
                    model=self.model_id,
                    contents=build_prompt,
                    config=genai.types.GenerateContentConfig(response_mime_type="application/json"),
                )
                plan = json_mod.loads(response.text)
                logger.info(f"Build plan: {plan}")

                # Step 2: Find a scene
                await status_msg.edit(content="**Encounter Builder** — Searching for battle maps...")
                scene_uuid = None
                scene_name = "Unknown"

                for kw in plan.get("scene_keywords", []):
                    scenes = await self.foundry.search_scenes(kw)
                    if scenes:
                        world_scenes = [s for s in scenes if not s.get("uuid", "").startswith("Compendium")]
                        if world_scenes:
                            scene_uuid = world_scenes[0]["uuid"]
                            scene_name = world_scenes[0]["name"]
                        else:
                            compendium_scene = scenes[0]
                            compendium_uuid = compendium_scene["uuid"]
                            c_name = compendium_scene["name"]
                            await status_msg.edit(content=f"**Encounter Builder** — Importing map **{c_name}**...")
                            import_result = await self.foundry.import_compendium_scene(compendium_uuid)
                            if isinstance(import_result, dict) and (import_result.get("uuid") or import_result.get("_id")):
                                scene_uuid = import_result.get("uuid") or import_result.get("_id")
                                scene_name = import_result.get("name") or c_name
                            else:
                                await ctx.send(f"Failed to import scene **{c_name}**.")
                                return
                        break

                if not scene_uuid:
                    world_scenes = await self.foundry.get_world_scenes()
                    active = [s for s in world_scenes if s.get("active")]
                    if active:
                        scene_uuid = active[0]["uuid"]
                        scene_name = active[0]["name"]
                    elif world_scenes:
                        scene_uuid = world_scenes[0]["uuid"]
                        scene_name = world_scenes[0]["name"]
                    else:
                        await ctx.send("No scenes found in the world.")
                        return

                # Step 3: Search monsters IN PARALLEL, then import sequentially
                await status_msg.edit(
                    content=f"**Encounter Builder** — Found map: **{scene_name}**\nSearching for monsters..."
                )

                monster_list = plan.get("monsters", [])
                monster_names = [m.get("name", "Goblin") for m in monster_list]

                # Fire all search_actors calls concurrently
                search_tasks = [self.foundry.search_actors(name) for name in monster_names]
                search_results = await asyncio.gather(*search_tasks, return_exceptions=True)

                # Get scene dimensions for token positioning
                scene_data = await self.foundry.get_entity(scene_uuid)
                scene_inner = scene_data.get("data", {})
                scene_width = scene_inner.get("width", 4000)
                scene_height = scene_inner.get("height", 3000)
                grid_size = scene_inner.get("grid", {}).get("size", 100)

                placements = []
                monsters_found = []

                for monster_info, results in zip(monster_list, search_results):
                    m_name = monster_info.get("name", "Goblin")
                    m_count = min(monster_info.get("count", 1), 8)

                    # If the search itself raised an exception, skip
                    if isinstance(results, Exception):
                        logger.warning(f"Search failed for {m_name}: {results}")
                        monsters_found.append(f"x {m_name} — search error")
                        continue

                    if not results:
                        monsters_found.append(f"x {m_name} — not found")
                        continue

                    actor = results[0]
                    actor_uuid = actor.get("uuid", "")
                    actor_name = actor.get("name", m_name)

                    # Import from compendium if needed (must be sequential)
                    if actor_uuid.startswith("Compendium"):
                        await status_msg.edit(
                            content=f"**Encounter Builder** — Importing **{actor_name}** to world..."
                        )
                        import_result = await self.foundry.import_compendium_actor(actor_uuid)
                        actor_uuid = import_result.get("uuid", actor_uuid)

                    monsters_found.append(f"{actor_name} x{m_count}")

                    formation = plan.get("formation", "scattered")
                    positions = _calculate_positions(m_count, formation, scene_width, scene_height, grid_size)

                    for i, (px, py) in enumerate(positions):
                        token_name = f"{actor_name}" if m_count == 1 else f"{actor_name} {i + 1}"
                        placements.append({
                            "actor_uuid": actor_uuid,
                            "x": px, "y": py,
                            "name": token_name,
                            "hidden": False,
                        })

                if not placements:
                    await ctx.send(
                        f"Could not find any of the requested monsters.\n"
                        f"Searched for: {', '.join(monster_names)}"
                    )
                    return

                # Step 4: Place tokens
                await status_msg.edit(
                    content=f"**Encounter Builder** — Placing {len(placements)} tokens on **{scene_name}**..."
                )
                await self.foundry.place_tokens_on_scene(scene_uuid, placements)

                # Step 5: Set lighting
                darkness = plan.get("lighting", 0.0)
                if darkness > 0:
                    await self.foundry.update_scene_lighting(scene_uuid, darkness)

                # Build report
                embed = discord.Embed(
                    title="Encounter Built!",
                    description=description,
                    color=discord.Color.green(),
                )
                embed.add_field(name="Scene", value=scene_name, inline=True)
                embed.add_field(
                    name="Lighting",
                    value=f"{'Day' if darkness < 0.3 else 'Twilight' if darkness < 0.7 else 'Night'}",
                    inline=True,
                )
                embed.add_field(
                    name="Monsters",
                    value="\n".join(monsters_found) or "None",
                    inline=False,
                )
                embed.add_field(
                    name="Tokens Placed",
                    value=f"{len(placements)} tokens on the map",
                    inline=True,
                )
                embed.set_footer(text="Check Foundry VTT to see the encounter!")
                await status_msg.edit(content=None, embed=embed)

        except Exception as e:
            logger.error(f"Build command failed: {e}", exc_info=True)
            await ctx.send(f"Encounter build failed: {e}")


async def setup(bot: commands.Bot):
    await bot.add_cog(FoundryCog(bot))
