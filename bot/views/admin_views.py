"""
Admin Views — Persistent Discord UI components for the DM Admin Console.

Contains:
  - AdminConsoleView: Main button panel (Resolve, Analyze, Roll, DM Event, etc.)
  - InlineRollView: Button for DM to roll dice from the console thread
  - DMEventModal: Modal for DM-injected narrative events
  - AnnotateModal: Modal for adding private DM context to an action
  - RollRequestModal: Modal for manually specifying a roll request
  - ActionSelectView: Dynamic select for choosing which queued action to operate on
"""

import logging
import discord
from discord import ButtonStyle, TextStyle

logger = logging.getLogger("AdminViews")


# ======================================================================
# Modals
# ======================================================================

class DMEventModal(discord.ui.Modal, title="Add DM Event"):
    """Modal for injecting a DM narrative event into the queue."""

    event_text = discord.ui.TextInput(
        label="What happens?",
        style=TextStyle.paragraph,
        placeholder="A hooded figure enters the tavern and sits in the corner...",
        max_length=500,
    )
    annotation = discord.ui.TextInput(
        label="DM notes (private, not shown to players)",
        style=TextStyle.paragraph,
        required=False,
        placeholder="This is the BBEG in disguise. Storyteller should build tension.",
        max_length=300,
    )

    def __init__(self, admin_cog):
        super().__init__()
        self.admin_cog = admin_cog

    async def on_submit(self, interaction: discord.Interaction):
        await self.admin_cog.queue.add_dm_event(
            text=self.event_text.value,
            annotation=self.annotation.value or None,
        )
        await self.admin_cog.refresh_console()
        await interaction.response.send_message(
            f"DM event added: _{self.event_text.value[:80]}_", ephemeral=True
        )


class AnnotateModal(discord.ui.Modal, title="Annotate Action"):
    """Modal for adding private DM context to a queued action."""

    note = discord.ui.TextInput(
        label="DM annotation (private)",
        style=TextStyle.paragraph,
        placeholder="The guard is actually a polymorphed dragon. Set DC high.",
        max_length=300,
    )

    def __init__(self, admin_cog, action_id: str):
        super().__init__()
        self.admin_cog = admin_cog
        self.action_id = action_id

    async def on_submit(self, interaction: discord.Interaction):
        success = await self.admin_cog.queue.set_dm_annotation(
            self.action_id, self.note.value
        )
        if success:
            await self.admin_cog.refresh_console()
            await interaction.response.send_message("Annotation added.", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Action not found in queue.", ephemeral=True
            )


class RollRequestModal(discord.ui.Modal, title="Request Dice Roll"):
    """Modal for manually specifying a roll request for a queued action."""

    roll_type = discord.ui.TextInput(
        label="Roll type",
        placeholder="Perception, Attack, Dexterity Save...",
        max_length=50,
    )
    formula = discord.ui.TextInput(
        label="Formula",
        placeholder="1d20+5",
        max_length=30,
    )
    dc = discord.ui.TextInput(
        label="DC (leave blank for attacks)",
        placeholder="15",
        required=False,
        max_length=5,
    )

    def __init__(self, admin_cog, action_id: str):
        super().__init__()
        self.admin_cog = admin_cog
        self.action_id = action_id

    async def on_submit(self, interaction: discord.Interaction):
        dc_val = None
        if self.dc.value:
            try:
                dc_val = int(self.dc.value)
            except ValueError:
                await interaction.response.send_message(
                    "DC must be a number.", ephemeral=True
                )
                return

        success = await self.admin_cog.queue.request_roll(
            self.action_id, self.roll_type.value, self.formula.value, dc_val
        )
        if not success:
            await interaction.response.send_message(
                "Action not found in queue.", ephemeral=True
            )
            return

        # Route the roll prompt to the right place
        action = await self.admin_cog.queue.get_by_id(self.action_id)
        if action:
            if self.admin_cog.is_dm_character(action):
                # DM's own character — inline roll in console
                await self.admin_cog.send_dm_roll_prompt(
                    action, self.roll_type.value, self.formula.value, dc_val,
                )
            else:
                game_table = self.admin_cog.get_game_table_channel()
                if game_table and action.character_name:
                    await game_table.send(
                        f"**{action.character_name}**, roll {self.roll_type.value}: "
                        f"`!roll {self.formula.value}`"
                    )

        await self.admin_cog.refresh_console()
        await interaction.response.send_message(
            f"Roll requested: {self.roll_type.value} `{self.formula.value}`"
            + (f" DC {dc_val}" if dc_val else ""),
            ephemeral=True,
        )


# ======================================================================
# Post to Table — DM narration bypass (no pipeline)
# ======================================================================

class PostToTableModal(discord.ui.Modal, title="Post to Game Table"):
    """Modal for posting direct DM narration to the Game Table, bypassing the pipeline."""

    narration = discord.ui.TextInput(
        label="Narration (posted as-is to Game Table)",
        style=TextStyle.paragraph,
        placeholder="You hear the distant rumble of thunder...\nThe tavern door creaks open...",
        max_length=1900,
    )

    def __init__(self, admin_cog):
        super().__init__()
        self.admin_cog = admin_cog

    async def on_submit(self, interaction: discord.Interaction):
        game_table = self.admin_cog.get_game_table_channel()
        if not game_table:
            await interaction.response.send_message(
                "Game table channel not found.", ephemeral=True
            )
            return
        await game_table.send(self.narration.value)
        await interaction.response.send_message(
            f"Posted to Game Table: _{self.narration.value[:60]}..._", ephemeral=True
        )


# ======================================================================
# Monster Roll Modal — DM rolls for monsters/NPCs from the console
# ======================================================================

class MonsterRollModal(discord.ui.Modal, title="Monster / NPC Roll"):
    """Modal for rolling dice for a monster or NPC. Fires Foundry dice immediately."""

    monster_name = discord.ui.TextInput(
        label="Monster / NPC name",
        placeholder="Goblin Archer, Durnan, Young Dragon...",
        max_length=50,
    )
    roll_type = discord.ui.TextInput(
        label="Roll type",
        placeholder="Attack, Damage, Initiative, Dex Save...",
        max_length=50,
    )
    formula = discord.ui.TextInput(
        label="Formula",
        placeholder="1d20+4, 2d6+2, 1d20+1...",
        max_length=30,
    )
    target = discord.ui.TextInput(
        label="Target (optional)",
        placeholder="Frognar, Kallisar...",
        required=False,
        max_length=50,
    )

    def __init__(self, admin_cog):
        super().__init__()
        self.admin_cog = admin_cog

    async def on_submit(self, interaction: discord.Interaction):
        # Create the monster roll entry
        roll = await self.admin_cog.queue.add_monster_roll(
            monster_name=self.monster_name.value,
            roll_type=self.roll_type.value,
            formula=self.formula.value,
            target=self.target.value or None,
        )

        # Fire the dice via Foundry
        if self.admin_cog.foundry.is_connected:
            await interaction.response.defer(ephemeral=True)
            try:
                result = await self.admin_cog.foundry.roll_dice(self.formula.value)
                total = result["total"]
                is_crit = result.get("isCritical", False)
                is_fumble = result.get("isFumble", False)

                dice_details = []
                for die_group in result.get("dice", []):
                    faces = die_group.get("faces", "?")
                    rolls = [r.get("result", "?") for r in die_group.get("results", [])]
                    dice_details.append(f"d{faces}: [{', '.join(str(r) for r in rolls)}]")
                detail_str = f"{self.formula.value}: {' '.join(dice_details)} = {total}"

                await self.admin_cog.queue.resolve_monster_roll(roll.id, total, detail_str)

                # Post result to console thread
                target_str = f" vs **{self.target.value}**" if self.target.value else ""
                crit_str = " **NAT 20!**" if is_crit else (" **NAT 1!**" if is_fumble else "")
                thread = self.admin_cog.get_console_thread()
                if thread:
                    await thread.send(
                        f"\U0001f9cc **{self.monster_name.value}** rolls "
                        f"{self.roll_type.value}{target_str}: "
                        f"`{self.formula.value}` = **{total}**{crit_str} "
                        f"{' '.join(dice_details)}"
                    )
                await self.admin_cog.refresh_console()
                await interaction.followup.send(
                    f"Monster roll: {self.monster_name.value} {self.roll_type.value} = {total}",
                    ephemeral=True,
                )
            except Exception as e:
                logger.error(f"Monster roll error: {e}", exc_info=True)
                await interaction.followup.send(f"Roll failed: {e}", ephemeral=True)
        else:
            await interaction.response.send_message(
                "Foundry not connected. Enter result manually with `!roll` in Game Table.",
                ephemeral=True,
            )


# ======================================================================
# Inline Roll — DM rolls for their own character from the console thread
# ======================================================================

class InlineRollView(discord.ui.View):
    """Button that lets the DM roll dice directly from the admin console.

    Used when the DM's own player character needs a roll. Instead of
    switching to Game Table to !roll, the DM clicks this button and
    Foundry's dice engine fires immediately.
    """

    def __init__(self, admin_cog, action_id: str, formula: str, timeout: float = 300):
        super().__init__(timeout=timeout)
        self.admin_cog = admin_cog
        self.action_id = action_id
        self.formula = formula

        # Dynamically set the button label to show the formula
        self.roll_button.label = f"Roll {formula}"

    @discord.ui.button(
        label="Roll",  # Overridden in __init__
        style=ButtonStyle.success,
        emoji="\U0001f3b2",
    )
    async def roll_button(self, interaction: discord.Interaction, button):
        """Fire the dice roll via Foundry and capture the result."""
        if not self.admin_cog.foundry.is_connected:
            await interaction.response.send_message(
                "Foundry not connected — roll manually with `!roll` in Game Table.",
                ephemeral=True,
            )
            return

        await interaction.response.defer()

        try:
            result = await self.admin_cog.foundry.roll_dice(self.formula)
            total = result["total"]
            is_crit = result.get("isCritical", False)
            is_fumble = result.get("isFumble", False)

            # Format dice detail
            dice_details = []
            for die_group in result.get("dice", []):
                faces = die_group.get("faces", "?")
                rolls = [r.get("result", "?") for r in die_group.get("results", [])]
                dice_details.append(f"d{faces}: [{', '.join(str(r) for r in rolls)}]")
            detail_str = f"{self.formula}: {' '.join(dice_details)} = {total}"

            # Update the queue — returns (action, next_roll)
            action, next_roll = await self.admin_cog.queue.update_roll_result(
                user_id=self.admin_cog._dm_user_id,
                result=total,
                detail=detail_str,
            )

            # Format response
            if is_crit:
                roll_msg = f"**NAT 20!** `{self.formula}`: **{total}** {' '.join(dice_details)}"
            elif is_fumble:
                roll_msg = f"**NAT 1!** `{self.formula}`: **{total}** {' '.join(dice_details)}"
            else:
                roll_msg = f"`{self.formula}`: **{total}** {' '.join(dice_details)}"

            # Disable the button after rolling
            button.disabled = True
            button.label = f"Rolled: {total}"
            button.style = ButtonStyle.secondary
            await interaction.edit_original_response(view=self)

            await interaction.followup.send(roll_msg)

            # If there's another roll in the sequence, prompt for it
            if action and next_roll:
                await self.admin_cog.send_dm_roll_prompt(
                    action, next_roll.roll_type, next_roll.formula, next_roll.dc,
                )

            await self.admin_cog.refresh_console()

        except Exception as e:
            logger.error(f"Inline roll error: {e}", exc_info=True)
            await interaction.followup.send(f"Roll failed: {e}")
        finally:
            self.stop()


# ======================================================================
# Action Select — used by Annotate, Skip, and Roll buttons
# ======================================================================

class ActionSelectView(discord.ui.View):
    """Dynamic select menu for choosing which queued action to operate on."""

    def __init__(self, admin_cog, operation: str, timeout: float = 60):
        super().__init__(timeout=timeout)
        self.admin_cog = admin_cog
        self.operation = operation  # "annotate", "skip", "roll"
        self.select_menu = None
        self._build_select()

    def _build_select(self):
        actions = self.admin_cog.queue.actions_snapshot
        if not actions:
            return

        select = discord.ui.Select(
            placeholder=f"Select an action to {self.operation}...",
            min_values=1,
            max_values=1,
        )
        for action in actions[:25]:  # Discord max 25 options
            name_tag = action.character_name or "DM"
            secret_tag = " [SECRET]" if action.is_secret else ""
            select.add_option(
                label=f"[{name_tag}] {action.player_input[:50]}{secret_tag}",
                value=action.id,
                description=f"Status: {action.status}",
            )
        select.callback = self._on_select
        self.select_menu = select
        self.add_item(select)

    async def _on_select(self, interaction: discord.Interaction):
        action_id = self.select_menu.values[0]

        if self.operation == "annotate":
            await interaction.response.send_modal(
                AnnotateModal(self.admin_cog, action_id)
            )
        elif self.operation == "skip":
            removed = await self.admin_cog.queue.remove(action_id)
            if removed:
                await self.admin_cog.refresh_console()
                await interaction.response.send_message(
                    f"Skipped: {removed.player_input[:60]}", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    "Action not found.", ephemeral=True
                )
        elif self.operation == "roll":
            await interaction.response.send_modal(
                RollRequestModal(self.admin_cog, action_id)
            )
        elif self.operation == "secret":
            action = await self.admin_cog.queue.get_by_id(action_id)
            if action:
                new_state = not action.is_secret
                await self.admin_cog.queue.update_action(
                    action_id, is_secret=new_state
                )
                # If marking secret and the player has a private thread, link it
                if new_state and not action.private_thread_id:
                    thread_id = self.admin_cog.queue.get_player_thread(action.discord_user_id)
                    if thread_id:
                        await self.admin_cog.queue.update_action(
                            action_id, private_thread_id=thread_id
                        )
                await self.admin_cog.refresh_console()
                label = "SECRET" if new_state else "PUBLIC"
                await interaction.response.send_message(
                    f"Action marked as **{label}**: {action.player_input[:60]}",
                    ephemeral=True,
                )
            else:
                await interaction.response.send_message(
                    "Action not found.", ephemeral=True
                )
        self.stop()


# ======================================================================
# Main Admin Console View — Persistent Buttons
# ======================================================================

class AdminConsoleView(discord.ui.View):
    """Persistent button panel for the DM Admin Console.

    Uses explicit custom_id on every button so the view survives bot restarts.
    timeout=None makes it persistent.
    """

    def __init__(self, admin_cog):
        super().__init__(timeout=None)
        self.admin_cog = admin_cog

    # --- Row 1: Core Actions ---

    @discord.ui.button(
        label="Resolve Turn",
        custom_id="admin:resolve",
        style=ButtonStyle.success,
        emoji="\u25b6",
        row=0,
    )
    async def resolve_turn(self, interaction: discord.Interaction, button):
        """Flush the queue and run the pipeline on the curated batch."""
        actions = await self.admin_cog.queue.flush_ready()
        if not actions:
            await interaction.response.send_message(
                "No ready actions to resolve.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        from bot.client import handle_batch_resolve

        game_table = self.admin_cog.get_game_table_channel()
        if not game_table:
            await interaction.followup.send("Game table channel not found.", ephemeral=True)
            return

        await handle_batch_resolve(actions, game_table)
        await self.admin_cog.refresh_console()
        await interaction.followup.send(
            f"Resolved {len(actions)} action(s).", ephemeral=True
        )

    @discord.ui.button(
        label="Analyze",
        custom_id="admin:analyze",
        style=ButtonStyle.primary,
        emoji="\U0001f50d",
        row=0,
    )
    async def analyze_actions(self, interaction: discord.Interaction, button):
        """Run Rules Lawyer pre-analysis on all pending actions."""
        from tools.rate_limiter import gemini_limiter

        actions = await self.admin_cog.queue.get_all()
        pending = [a for a in actions if a.status == "pending"]
        if not pending:
            await interaction.response.send_message(
                "No pending actions to analyze.", ephemeral=True
            )
            return

        await interaction.response.defer(ephemeral=True)

        analyzed = 0
        game_table = self.admin_cog.get_game_table_channel()

        for action in pending:
            await self.admin_cog.queue.update_action(action.id, status="analyzing")
            await gemini_limiter.acquire()
            result = await self.admin_cog.rules_lawyer.pre_analyze(
                action.player_input, action.character_name
            )
            await self.admin_cog.queue.update_action(
                action.id, rules_pre_analysis=result
            )

            if result.get("needs_roll") and result.get("rolls"):
                # Add all identified rolls to the action's sequence
                await self.admin_cog.queue.request_rolls(
                    action.id, result["rolls"]
                )
                # Prompt for the first roll only — subsequent rolls prompted after each resolves
                first_roll = result["rolls"][0]
                formula = first_roll.get("formula", "1d20")
                roll_type = first_roll.get("roll_type", "Check")
                dc = first_roll.get("dc")

                if self.admin_cog.is_dm_character(action):
                    await self.admin_cog.send_dm_roll_prompt(
                        action, roll_type, formula, dc,
                    )
                elif game_table and action.character_name:
                    await game_table.send(
                        f"**{action.character_name}**, roll {roll_type}: "
                        f"`!roll {formula}`"
                    )
            elif result.get("needs_roll"):
                # Legacy single-roll fallback (if LLM returns old format)
                formula = result.get("formula", "1d20")
                roll_type = result.get("roll_type", "Check")
                dc = result.get("dc")
                await self.admin_cog.queue.request_roll(
                    action.id, roll_type, formula, dc,
                )
                if self.admin_cog.is_dm_character(action):
                    await self.admin_cog.send_dm_roll_prompt(
                        action, roll_type, formula, dc,
                    )
                elif game_table and action.character_name:
                    await game_table.send(
                        f"**{action.character_name}**, roll {roll_type}: "
                        f"`!roll {formula}`"
                    )
            else:
                await self.admin_cog.queue.update_action(action.id, status="ready")
            analyzed += 1

        await self.admin_cog.refresh_console()
        await interaction.followup.send(
            f"Analyzed {analyzed} action(s).", ephemeral=True
        )

    @discord.ui.button(
        label="Request Roll",
        custom_id="admin:roll",
        style=ButtonStyle.primary,
        emoji="\U0001f3b2",
        row=0,
    )
    async def request_roll(self, interaction: discord.Interaction, button):
        """Manually request a dice roll for a specific action."""
        actions = await self.admin_cog.queue.get_all()
        if not actions:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
            return
        view = ActionSelectView(self.admin_cog, "roll")
        await interaction.response.send_message(
            "Select an action to request a roll for:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="DM Event",
        custom_id="admin:dm_event",
        style=ButtonStyle.secondary,
        emoji="\u2795",
        row=0,
    )
    async def add_dm_event(self, interaction: discord.Interaction, button):
        """Open modal to inject a DM narrative event."""
        await interaction.response.send_modal(DMEventModal(self.admin_cog))

    # --- Row 2: Queue Management ---

    @discord.ui.button(
        label="Monster Roll",
        custom_id="admin:monster_roll",
        style=ButtonStyle.primary,
        emoji="\U0001f9cc",
        row=1,
    )
    async def monster_roll(self, interaction: discord.Interaction, button):
        """Roll dice for a monster or NPC."""
        await interaction.response.send_modal(MonsterRollModal(self.admin_cog))

    @discord.ui.button(
        label="Annotate",
        custom_id="admin:annotate",
        style=ButtonStyle.secondary,
        emoji="\U0001f4dd",
        row=1,
    )
    async def annotate_action(self, interaction: discord.Interaction, button):
        """Add a private DM note to a queued action."""
        actions = await self.admin_cog.queue.get_all()
        if not actions:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
            return
        view = ActionSelectView(self.admin_cog, "annotate")
        await interaction.response.send_message(
            "Select an action to annotate:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Skip Action",
        custom_id="admin:skip",
        style=ButtonStyle.danger,
        emoji="\u23ed",
        row=1,
    )
    async def skip_action(self, interaction: discord.Interaction, button):
        """Remove an action from the queue without resolving it."""
        actions = await self.admin_cog.queue.get_all()
        if not actions:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
            return
        view = ActionSelectView(self.admin_cog, "skip")
        await interaction.response.send_message(
            "Select an action to skip:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Secret Toggle",
        custom_id="admin:secret",
        style=ButtonStyle.secondary,
        emoji="\U0001f910",
        row=1,
    )
    async def toggle_secret(self, interaction: discord.Interaction, button):
        """Toggle an action between public and secret."""
        actions = await self.admin_cog.queue.get_all()
        if not actions:
            await interaction.response.send_message("Queue is empty.", ephemeral=True)
            return
        view = ActionSelectView(self.admin_cog, "secret")
        await interaction.response.send_message(
            "Select an action to toggle secret/public:",
            view=view,
            ephemeral=True,
        )

    @discord.ui.button(
        label="Post to Table",
        custom_id="admin:post_table",
        style=ButtonStyle.secondary,
        emoji="\U0001f4e2",
        row=1,
    )
    async def post_to_table(self, interaction: discord.Interaction, button):
        """Post direct DM narration to Game Table, bypassing the pipeline."""
        await interaction.response.send_modal(PostToTableModal(self.admin_cog))

    # --- Row 3: Session Lifecycle + Utility ---

    @discord.ui.button(
        label="Refresh",
        custom_id="admin:refresh",
        style=ButtonStyle.secondary,
        emoji="\U0001f504",
        row=2,
    )
    async def refresh(self, interaction: discord.Interaction, button):
        """Refresh the console embed."""
        await self.admin_cog.refresh_console()
        await interaction.response.send_message("Refreshed.", ephemeral=True)

    @discord.ui.button(
        label="Start Session",
        custom_id="admin:start_session",
        style=ButtonStyle.success,
        emoji="\u25b6",
        row=2,
    )
    async def start_session(self, interaction: discord.Interaction, button):
        """Begin a new session — generates recap + opening scene."""
        await interaction.response.defer(ephemeral=True)

        self.admin_cog.queue.enable_queue_mode()
        game_table = self.admin_cog.get_game_table_channel()
        session_num = self.admin_cog.context_assembler.current_session

        if game_table:
            await game_table.send(f"**--- Session {session_num} Begins ---**")

            # Ensure the session log file exists
            self.admin_cog.vault.append_to_session_log(
                session_num, "| | Session started | 1 | |"
            )

            # Generate a recap from the previous session
            try:
                recap = await self.admin_cog.storyteller.generate_recap(session_num)
                if recap:
                    from bot.client import _send_chunked
                    await _send_chunked(game_table, recap)
            except Exception as e:
                logger.error(f"Recap generation failed: {e}", exc_info=True)
                await game_table.send("_The story continues from where we left off..._")

        await self.admin_cog.refresh_console()
        await interaction.followup.send(
            f"Session {session_num} started. Queue mode enabled. Recap posted.", ephemeral=True
        )

    @discord.ui.button(
        label="End Session",
        custom_id="admin:end_session",
        style=ButtonStyle.danger,
        emoji="\u23f9",
        row=2,
    )
    async def end_session(self, interaction: discord.Interaction, button):
        """End the current session — generates summary, disables queue mode."""
        await interaction.response.defer(ephemeral=True)

        session_num = self.admin_cog.context_assembler.current_session
        game_table = self.admin_cog.get_game_table_channel()

        # Generate and store session summary
        summary_text = None
        try:
            summary_text = await self.admin_cog.storyteller.generate_summary(session_num)
            if summary_text:
                self.admin_cog.vault.update_session_summary(session_num, summary_text)
        except Exception as e:
            logger.error(f"Summary generation failed: {e}", exc_info=True)

        # Post closing message
        if game_table:
            closing = f"**--- Session {session_num} Ends ---**\n"
            if summary_text:
                closing += f"\n{summary_text}"
            else:
                closing += "_The story pauses here... for now._"
            from bot.client import _send_chunked
            await _send_chunked(game_table, closing)

        # Increment session number and update context
        self.admin_cog.queue.disable_queue_mode()
        new_session = self.admin_cog.vault.increment_session()
        self.admin_cog.context_assembler.set_session(new_session)

        # Save memory checkpoint
        self.admin_cog.context_assembler.save_checkpoint()

        await self.admin_cog.refresh_console()
        await interaction.followup.send(
            f"Session {session_num} ended. Summary saved. "
            f"Next session: {new_session}. Queue mode disabled.",
            ephemeral=True,
        )

    @discord.ui.button(
        label="Auto Mode",
        custom_id="admin:toggle_mode",
        style=ButtonStyle.secondary,
        emoji="\u26a1",
        row=2,
    )
    async def toggle_mode(self, interaction: discord.Interaction, button):
        """Toggle between queue mode and auto mode."""
        new_state = self.admin_cog.queue.toggle_queue_mode()
        mode_str = "Queue Mode" if new_state else "Auto Mode"
        await self.admin_cog.refresh_console()
        await interaction.response.send_message(
            f"Switched to **{mode_str}**.", ephemeral=True
        )
