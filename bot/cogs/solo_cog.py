"""
Solo Cog — Between-session 1-on-1 adventure commands.

Commands:
  /solo      — Start a solo adventure in a private thread
  /solo_end  — End the current solo adventure
  /solo_undo — Undo the last turn (multi-turn rewind, max 5)

Features:
  - Session recap on startup (Phase 1.1)
  - Merge summary on end (Phase 4.1)
  - Concurrent play guards (Phase 4.3)
  - Per-session history isolation (Phase 0.1)
"""

import logging
import os
import discord
from discord import app_commands
from discord.ext import commands

from tools.player_identity import resolve_from_message_author

logger = logging.getLogger("Solo_Cog")


class SoloCog(commands.Cog, name="Solo"):
    """Solo adventure commands for between-session play."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @property
    def solo_manager(self):
        return self.bot.solo_manager

    @app_commands.command(name="solo", description="Start a solo adventure in a private thread")
    @app_commands.describe(character="(Admin only) Override character for testing")
    async def solo_start(self, interaction: discord.Interaction, character: str = None):
        """Create a private thread for a solo adventure session."""
        # Admin character override for testing
        if character:
            is_admin = (
                interaction.user.guild_permissions.administrator
                if interaction.guild
                else False
            )
            if not is_admin:
                await interaction.response.send_message(
                    "The `character` parameter is admin-only.",
                    ephemeral=True,
                )
                return
            character_name = character
        else:
            # Resolve character from PLAYER_MAP
            character_name = resolve_from_message_author(interaction.user)
            if not character_name:
                await interaction.response.send_message(
                    "I can't find your character. Make sure you're in the `PLAYER_MAP`.",
                    ephemeral=True,
                )
                return

        # Check for existing session (same user)
        existing = self.solo_manager.get_by_user(interaction.user.id)
        if existing:
            await interaction.response.send_message(
                f"You already have an active solo session in <#{existing.thread_id}>. "
                f"Use `/solo_end` there first, or continue your adventure!",
                ephemeral=True,
            )
            return

        # Concurrent play guard (Phase 4.3): same character can't be in group + solo
        existing_char = self.solo_manager.get_by_character(character_name)
        if existing_char:
            await interaction.response.send_message(
                f"{character_name} is already in a solo session "
                f"in <#{existing_char.thread_id}>.",
                ephemeral=True,
            )
            return

        await interaction.response.defer(ephemeral=True)

        # Create private thread
        thread_name = f"{character_name}'s Solo Adventure"
        try:
            thread = await interaction.channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.private_thread,
                auto_archive_duration=1440,  # 24 hours
            )
        except discord.HTTPException:
            # Fallback to public thread if private threads not available
            thread = await interaction.channel.create_thread(
                name=thread_name,
                type=discord.ChannelType.public_thread,
                auto_archive_duration=1440,
            )

        # Get character location
        storyteller = self.bot.storyteller
        location = (
            storyteller.get_character_location(character_name)
            or storyteller._current_location
            or "Unknown"
        )

        # Get current session number
        current_session = self.bot.context_assembler.current_session

        # Register session
        session = await self.solo_manager.start_session(
            discord_user_id=interaction.user.id,
            thread_id=thread.id,
            character_name=character_name,
            current_location=location,
            session_number=current_session,
        )

        # Build solo log path with unique sub-session suffix
        # Scan for existing logs to avoid appending to a stale file
        import glob as globmod
        solo_log_dir = os.path.join(
            self.bot.vault.vault_path, "00 - Session Log", "Solo"
        )
        base_pattern = f"{character_name}_Solo_S{current_session:03d}"
        existing = globmod.glob(os.path.join(solo_log_dir, f"{base_pattern}*.md"))
        # Filter out merge files
        existing = [f for f in existing if "_merge" not in f]
        sub = len(existing) + 1 if existing else 1
        if sub == 1:
            log_filename = f"{base_pattern}.md"
        else:
            log_filename = f"{base_pattern}_{sub}.md"
        session.solo_log_path = f"00 - Session Log/Solo/{log_filename}"

        # Build session recap (Phase 1.1)
        recap_text = self._build_session_recap(character_name, current_session)

        # Build character brief for the welcome embed
        char_brief = self._build_character_brief(character_name)

        # Build welcome embed
        embed = discord.Embed(
            title=f"{character_name}'s Solo Adventure",
            description=(
                f"**{character_name}** — {char_brief.get('tagline', 'Adventurer')}\n"
                f"**Location:** {location}\n"
                f"**HP:** {char_brief.get('hp', '?')} | "
                f"**AC:** {char_brief.get('ac', '?')} | "
                f"**Level:** {char_brief.get('level', '?')}"
            ),
            color=discord.Color.purple(),
        )

        # Add recap to embed if available
        if recap_text:
            embed.add_field(
                name="Previously...",
                value=recap_text[:1024],  # Discord embed field limit
                inline=False,
            )

        # Character capabilities
        capabilities = char_brief.get("capabilities", "")
        if capabilities:
            embed.add_field(
                name="Your Toolkit",
                value=capabilities[:1024],
                inline=False,
            )

        # Notable gear
        gear = char_brief.get("gear_highlights", "")
        if gear:
            embed.add_field(
                name="Notable Gear",
                value=gear[:1024],
                inline=True,
            )

        # Personality hook
        personality = char_brief.get("personality_hook", "")
        if personality:
            embed.add_field(
                name="Character Drive",
                value=personality[:1024],
                inline=True,
            )

        embed.set_footer(
            text="Type your actions naturally. "
                 "/solo_undo to rewind (up to 5), /solo_end when done."
        )

        await thread.send(embed=embed)

        # Generate opening scene via Storyteller
        try:
            from tools.rate_limiter import gemini_limiter

            # Build rich opening prompt with character context and recap
            opening_prompt = self._build_opening_prompt(
                character_name, location, recap_text, char_brief
            )

            # Build initial state for the pipeline
            from bot.client import game_pipeline, _pipeline_semaphore

            # Build campaign context for solo startup (Phase 4.2)
            campaign_context = ""
            try:
                from tools.solo_merge import build_campaign_context_for_solo
                campaign_context = build_campaign_context_for_solo(
                    self.bot.vault, character_name
                )
            except Exception:
                pass

            if campaign_context:
                opening_prompt = campaign_context + "\n\n" + opening_prompt

            initial_state = {
                "player_input": opening_prompt,
                "character_name": character_name,
                "session": current_session,
                "current_location": location,
                "is_solo": True,
                "_solo_thread_id": thread.id,
            }

            async with _pipeline_semaphore:
                result = await game_pipeline.ainvoke(initial_state)

            narrative = result.get("narrative", "")
            if narrative:
                # Chunk if needed
                if len(narrative) > 2000:
                    for i in range(0, len(narrative), 2000):
                        await thread.send(narrative[i : i + 2000])
                else:
                    await thread.send(narrative)
            else:
                await thread.send(
                    f"*{character_name} finds a quiet moment at {location}...*\n\n"
                    "What would you like to do?"
                )

            # Log the opening turn
            vault = self.bot.vault
            vault.append_to_solo_log(
                character_name=character_name,
                session_number=current_session,
                turn_number=0,
                player_input="[Session Start]",
                narrative=narrative or f"*Solo adventure begins at {location}.*",
                log_path=session.solo_log_path,
            )
            await self.solo_manager.increment_turn(thread.id)

        except Exception as e:
            logger.error(f"Solo opening scene failed: {e}", exc_info=True)
            await thread.send(
                f"*{character_name} settles in at {location}...*\n\n"
                "What would you like to do?"
            )

        # Send confirmation to player
        await interaction.followup.send(
            f"Solo adventure started! Head to {thread.mention}",
            ephemeral=True,
        )

        # Admin notification
        try:
            await self.bot.send_to_moderator_log(
                f"[Solo] {character_name} started a solo adventure "
                f"(thread={thread.id}, location={location})"
            )
        except Exception:
            pass

    @app_commands.command(
        name="solo_end", description="End your current solo adventure"
    )
    async def solo_end(self, interaction: discord.Interaction):
        """End the solo adventure in the current thread."""
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "This command must be used in a solo adventure thread.",
                ephemeral=True,
            )
            return

        session = self.solo_manager.get_session(interaction.channel.id)
        if not session:
            await interaction.response.send_message(
                "This isn't an active solo adventure thread.",
                ephemeral=True,
            )
            return

        if session.discord_user_id != interaction.user.id:
            await interaction.response.send_message(
                "Only the adventurer can end their solo session.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        # Generate merge summary (Phase 4.1)
        merge_summary = None
        try:
            from tools.solo_merge import generate_merge_summary, write_merge_file

            session_data = session.to_dict()
            merge_summary = generate_merge_summary(session_data)

            # Write merge file for DM review
            vault = self.bot.vault
            write_merge_file(
                vault, session.character_name,
                session.session_number, merge_summary,
            )
        except Exception as e:
            logger.warning(f"Merge summary generation failed: {e}")

        # Generate brief summary
        summary_lines = [
            f"**Solo Adventure Complete!**",
            f"Character: {session.character_name}",
            f"Turns: {session.turn_count}",
            f"Location: {session.current_location}",
        ]

        # Add consequences if any
        if session.active_consequences:
            summary_lines.append(
                f"Active Consequences: {', '.join(session.active_consequences[:3])}"
            )

        # Add thread count
        active_threads = [
            t for t in session.active_threads
            if isinstance(t, dict) and t.get("status") == "active"
        ]
        if active_threads:
            thread_names = [t.get("title", "?") for t in active_threads[:3]]
            summary_lines.append(f"Open Threads: {', '.join(thread_names)}")

        summary_text = "\n".join(summary_lines)
        await interaction.channel.send(summary_text)

        # End session
        await self.solo_manager.end_session(interaction.channel.id)

        # Archive thread
        try:
            await interaction.channel.edit(archived=True)
        except discord.HTTPException:
            pass

        # Admin notification
        try:
            await self.bot.send_to_moderator_log(
                f"[Solo] {session.character_name}'s solo adventure ended "
                f"({session.turn_count} turns)"
            )
        except Exception:
            pass

        await interaction.followup.send("Solo adventure archived.", ephemeral=True)

    @app_commands.command(
        name="solo_undo", description="Undo your last solo adventure turn"
    )
    async def solo_undo(self, interaction: discord.Interaction):
        """Rewind the last turn in the current solo adventure (multi-turn, max 5)."""
        if not isinstance(interaction.channel, discord.Thread):
            await interaction.response.send_message(
                "This command must be used in a solo adventure thread.",
                ephemeral=True,
            )
            return

        session = self.solo_manager.get_session(interaction.channel.id)
        if not session:
            await interaction.response.send_message(
                "This isn't an active solo adventure thread.",
                ephemeral=True,
            )
            return

        if session.discord_user_id != interaction.user.id:
            await interaction.response.send_message(
                "Only the adventurer can undo their actions.",
                ephemeral=True,
            )
            return

        if not session.snapshot_stack:
            await interaction.response.send_message(
                "Nothing to undo! No snapshots remain in the undo stack.",
                ephemeral=True,
            )
            return

        # Acquire processing lock to prevent undo during pipeline run
        processing_lock = self.solo_manager.get_processing_lock(interaction.channel.id)
        if processing_lock and processing_lock.locked():
            await interaction.response.send_message(
                "Can't undo while an action is being processed. Wait a moment!",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        snapshot = session.pop_snapshot()
        turn_num = snapshot.turn_number

        # Restore per-session history from snapshot (Phase 0.1)
        session_history = self.solo_manager.get_history(interaction.channel.id)
        if session_history:
            from tools.context_assembler import MemoryEntry
            session_history.entries.clear()
            for entry_data in snapshot.history_snapshot:
                session_history.entries.append(
                    MemoryEntry(
                        text=entry_data["text"],
                        impact=entry_data["base_impact"],
                        turns_ago=entry_data["turns_ago"],
                        timestamp=entry_data.get("timestamp", 0.0),
                        character=entry_data.get("character"),
                        location=entry_data.get("location"),
                    )
                )

        # Restore location
        session.current_location = snapshot.location_before

        # Note: Solo events are NOT written to the global memory checkpoint (fixed in
        # chronicler_node.py), so undo doesn't need to touch it. Solo uses per-session
        # history only, which was already restored above.

        # Mark turn as undone in solo log
        vault = self.bot.vault
        vault.append_to_solo_log(
            character_name=session.character_name,
            session_number=session.session_number,
            turn_number=turn_num,
            player_input=snapshot.player_input,
            narrative="(undone by player)",
            undone=True,
            log_path=session.solo_log_path,
        )

        remaining = len(session.snapshot_stack)
        await interaction.followup.send(
            f"Rewound to before turn {turn_num}. Try a different approach! "
            f"({remaining} undo{'s' if remaining != 1 else ''} remaining)"
        )

    def _build_session_recap(self, character_name: str, session_number: int) -> str:
        """Build a recap from previous solo logs and character knowledge (Phase 1.1).

        Returns a short recap string, or empty string if no previous data.
        """
        try:
            vault = self.bot.vault
            recap_parts = []

            # Try to read the most recent solo log
            recap_text = self._get_latest_solo_log_recap(vault, character_name)
            if recap_text:
                recap_parts.append(recap_text)

            # Pull character knowledge snippet
            knowledge_path = f"08 - Character Knowledge/{character_name}.md"
            result = vault.read_file(knowledge_path)
            if result:
                _, body = result
                if body and body.strip():
                    # Take last few observations
                    lines = [l.strip() for l in body.strip().split('\n') if l.strip()]
                    recent = lines[-3:] if len(lines) > 3 else lines
                    recap_parts.append("Recent insights: " + "; ".join(recent))

            return " ".join(recap_parts) if recap_parts else ""

        except Exception as e:
            logger.warning(f"Session recap failed: {e}")
            return ""

    def _get_latest_solo_log_recap(self, vault, character_name: str) -> str:
        """Find the most recent solo log and extract the last few turns."""
        import os

        solo_dir = os.path.join(vault.vault_path, vault.SOLO_LOG)
        if not os.path.isdir(solo_dir):
            return ""

        # Find matching solo logs for this character
        prefix = f"{character_name}_Solo_S"
        matching = [
            f for f in os.listdir(solo_dir)
            if f.startswith(prefix) and f.endswith(".md") and "_merge" not in f
        ]
        if not matching:
            return ""

        matching.sort(reverse=True)  # Most recent first
        latest_path = os.path.join(solo_dir, matching[0])

        try:
            with open(latest_path, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract the last 3 turn blocks
            turns = content.split("### Turn ")
            recent_turns = turns[-3:] if len(turns) > 3 else turns[1:]  # Skip header

            if not recent_turns:
                return ""

            # Build recap from DM narratives
            recap_lines = []
            for turn in recent_turns:
                lines = turn.strip().split('\n')
                for line in lines:
                    if line.startswith("**DM:**"):
                        narrative = line[7:].strip()
                        if "(undone by player)" not in narrative:
                            # Truncate long narratives
                            if len(narrative) > 150:
                                narrative = narrative[:150] + "..."
                            recap_lines.append(narrative)

            if recap_lines:
                return f"Previously: {' '.join(recap_lines[-2:])}"
            return ""

        except (OSError, UnicodeDecodeError):
            return ""

    def _build_character_brief(self, character_name: str) -> dict:
        """Pull character sheet data into a brief for the welcome embed and opening prompt."""
        vault = self.bot.vault
        brief = {}

        # Read character sheet
        for fpath in vault.list_files(vault.PARTY):
            result = vault.read_file(fpath)
            if not result:
                continue
            fm, body = result
            if fm.get("name", "").lower() != character_name.lower():
                continue

            # Basic stats
            brief["level"] = fm.get("level", "?")
            brief["hp"] = f"{fm.get('hp_current', '?')}/{fm.get('hp_max', '?')}"
            brief["ac"] = fm.get("ac", "?")
            race = fm.get("race", "")
            cls = fm.get("class", "")
            brief["tagline"] = f"Level {brief['level']} {race} {cls}".strip()
            brief["class"] = cls
            brief["race"] = race
            brief["pronouns"] = fm.get("pronouns", "")

            # Spell slots
            slots_max = fm.get("spell_slots_max", 0)
            slots_used = fm.get("spell_slots_used", 0)
            if slots_max:
                brief["spell_slots"] = f"{slots_max - slots_used}/{slots_max}"

            # Abilities & Spells
            abilities = []
            spells = []
            in_abilities = False
            in_spells = False
            in_inventory = False
            in_personality = False
            inventory_items = []
            personality_lines = []

            for line in body.split("\n"):
                stripped = line.strip()
                if stripped.startswith("## Abilities"):
                    in_abilities = True
                    in_spells = in_inventory = in_personality = False
                    continue
                elif stripped.startswith("## Prepared Spells"):
                    in_spells = True
                    in_abilities = in_inventory = in_personality = False
                    continue
                elif stripped.startswith("## Inventory"):
                    in_inventory = True
                    in_abilities = in_spells = in_personality = False
                    continue
                elif stripped.startswith("## Personality"):
                    in_personality = True
                    in_abilities = in_spells = in_inventory = False
                    continue
                elif stripped.startswith("## "):
                    in_abilities = in_spells = in_inventory = in_personality = False
                    continue

                if in_abilities and stripped.startswith("- "):
                    abilities.append(stripped[2:])
                elif in_spells and stripped.startswith("- ") and "Choose from" not in stripped:
                    spells.append(stripped[2:])
                elif in_inventory and stripped.startswith("- "):
                    inventory_items.append(stripped[2:])
                elif in_personality and stripped:
                    personality_lines.append(stripped)

            # Build capabilities string
            caps = []
            if abilities:
                caps.append("**Abilities:** " + ", ".join(abilities[:6]))
            if spells:
                slot_info = f" ({brief.get('spell_slots', '?')} slots)" if brief.get("spell_slots") else ""
                caps.append(f"**Spells{slot_info}:** " + ", ".join(spells[:6]))
            elif slots_max:
                # Has spell slots but spells not chosen yet
                caps.append(f"**Spell Slots:** {brief.get('spell_slots', '?')} available")
            brief["capabilities"] = "\n".join(caps) if caps else ""

            # Gear highlights (skip generic items, keep interesting ones)
            boring = {"common clothes", "belt pouch", "vestments", "a component pouch"}
            interesting = [
                i for i in inventory_items
                if not any(b in i.lower() for b in boring)
            ][:5]
            brief["gear_highlights"] = ", ".join(interesting) if interesting else ""

            # Personality hook — trait + flaw combo
            hooks = []
            for pl in personality_lines:
                clean = pl.strip("_").strip()
                if clean.startswith("**Trait:**"):
                    hooks.append(clean)
                elif clean.startswith("**Bond:**"):
                    hooks.append(clean)
                elif clean.startswith("**Flaw:**"):
                    hooks.append(clean)
            brief["personality_hook"] = "\n".join(hooks[:2]) if hooks else ""
            brief["personality_full"] = "\n".join(personality_lines) if personality_lines else ""

            break  # Found our character

        return brief

    def _build_opening_prompt(
        self, character_name: str, location: str, recap_text: str, char_brief: dict
    ) -> str:
        """Build a rich opening prompt for the storyteller pipeline."""
        parts = []

        # Character identity block
        tagline = char_brief.get("tagline", "Adventurer")
        pronouns = char_brief.get("pronouns", "")
        pronoun_note = f" [{pronouns}]" if pronouns else ""
        parts.append(
            f"[CHARACTER: {character_name}{pronoun_note}, {tagline}. "
            f"HP: {char_brief.get('hp', '?')}, AC: {char_brief.get('ac', '?')}]"
        )

        # Personality context
        personality = char_brief.get("personality_full", "")
        if personality:
            parts.append(f"[PERSONALITY: {personality}]")

        # Capabilities summary for the storyteller
        caps = char_brief.get("capabilities", "")
        if caps:
            parts.append(f"[CAPABILITIES: {caps}]")

        # Recap from previous solo session
        if recap_text:
            parts.append(f"[RECAP: {recap_text}]")

        # The actual scene-setting instruction
        parts.append(
            f"[{character_name}]: *{character_name} begins a solo adventure "
            f"at {location}.*\n\n"
            f"Generate a rich opening scene for this solo adventure. You MUST include:\n"
            f"1. A 'Previously on...' paragraph if there is a RECAP above — remind the "
            f"player where they left off and what was happening.\n"
            f"2. A vivid scene description of {location} — sights, sounds, smells. "
            f"What is {character_name} doing right now? What catches their attention?\n"
            f"3. Two or three clear hooks or opportunities the player can pursue — "
            f"things to investigate, people to talk to, places to explore, or trouble "
            f"brewing nearby. Present these naturally within the narrative, not as a list.\n"
            f"4. End with a moment that invites action — something that demands a response."
        )

        return "\n\n".join(parts)


async def setup(bot: commands.Bot):
    await bot.add_cog(SoloCog(bot))
