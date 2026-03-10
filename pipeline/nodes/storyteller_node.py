"""
Storyteller Node — Generates immersive narrative prose.

Wraps the existing StorytellerAgent. Only runs if needs_storyteller is True.

Solo guardrails include:
- Death alternatives (Phase 1.2) — capture, injury, debt instead of death
- Combat scaling (Phase 1.4) — max 2-3 weak enemies, escape routes
- Outcome grade narration (Phase 1.3) — oracle-style graduated outcomes
"""

import logging
from pipeline.state import GameState
from tools.rate_limiter import gemini_limiter

logger = logging.getLogger("pipeline.storyteller")


async def storyteller_node(state: GameState, *, storyteller, **_kwargs) -> dict:
    """Generate narrative prose from the mechanical ruling.

    Args:
        state: Current GameState.
        storyteller: The existing StorytellerAgent instance.
    """
    if not state.get("needs_storyteller"):
        return {"narrative": ""}

    try:
        await gemini_limiter.acquire()
        rules_ruling = state.get("rules_ruling")

        # Enrich the player input with DM context and batch framing
        player_input = state["player_input"]
        if state.get("is_batched"):
            player_input = (
                "[MULTI-CHARACTER ROUND — narrate all actions in a cohesive scene]\n"
                + player_input
            )
        if state.get("dm_context"):
            player_input += f"\n\n[DM Context (private, weave naturally): {state['dm_context']}]"

        # Solo session guardrails (enriched with death alternatives + combat scaling)
        if state.get("is_solo"):
            player_input += """

[SOLO SESSION -- follow these strictly]:
- Only ONE character is present. This is a personal adventure between group sessions.
- Keep stakes PERSONAL -- character development, NPC relationships, exploration, intrigue.
- Do NOT advance major campaign plot arcs or introduce campaign-altering events.
- Do NOT kill named NPCs from the main campaign.
- Do NOT grant XP, level-ups, or major magical items (minor consumables OK).
- TIME IS FROZEN -- do not reference specific dates or times advancing. Use relative
  phrases like "Later that evening...", "As the night wears on...", "Some time passes..."
  The world clock does not move during solo play.
- Pace is slower -- favor conversation, exploration, and character moments over combat.
- End each response with a natural prompt for what the character might do next.

[SOLO COMBAT SCALING]:
- Solo encounters: max 2-3 weak enemies OR 1 strong enemy. Never outnumber the PC by more than 3:1.
- Reduce enemy HP to ~60% of standard. Enemies make tactical mistakes -- miss obvious flanks,
  hesitate, argue with each other, or underestimate the PC.
- If the PC is clearly overwhelmed (3+ rounds of losing HP), introduce an escape route,
  environmental advantage, or NPC intervention.
- Prefer encounters where combat is optional -- negotiation, stealth, and retreat should
  always be viable alternatives.

[SOLO DEATH ALTERNATIVES]:
- When the solo PC reaches 0 HP, do NOT kill them. Instead apply one of:
  * Captured by enemies (creates rescue/escape scenario)
  * Debilitating injury (mechanical consequence, e.g. disadvantage on STR checks until healed)
  * Debt or obligation to an NPC rescuer (narrative hook, future cost)
  * A curse or mark from the encounter (ongoing story thread)
  * Divine or patron intervention with a steep cost
- The consequence MUST have lasting narrative weight -- reference it in future turns.
- Frame it dramatically: the PC was defeated, not just paused. Consequences matter.
"""

        # Oracle grade injection (Phase 1.3) — after rules node resolves the check
        if state.get("is_solo") and rules_ruling and isinstance(rules_ruling, dict):
            player_input = _inject_oracle_grade(state, rules_ruling, player_input)

        # Normalize rules_ruling: batched rounds return a list, solo returns a dict
        if isinstance(rules_ruling, list):
            # Check if ANY ruling in the batch is invalid
            invalid = [r for r in rules_ruling if r.get("valid") is False]
            if invalid:
                reasons = "; ".join(r.get("result", "Unknown") for r in invalid)
                enforcement_note = (
                    "\n\n[ENFORCEMENT: The Rules Lawyer ruled some actions INVALID. "
                    f"Reasons: {reasons}. "
                    "Narrate those CHARACTER ATTEMPTS but do NOT grant the desired outcomes. "
                    "Redirect to proper mechanics. Stay immersive — never break character.]"
                )
                player_input += enforcement_note
        elif rules_ruling and rules_ruling.get("valid") is False:
            enforcement_note = (
                "\n\n[ENFORCEMENT: The Rules Lawyer ruled this action INVALID. "
                f"Reason: {rules_ruling.get('result', 'Unknown')}. "
                "Narrate the CHARACTER'S ATTEMPT but do NOT grant the desired outcome. "
                "Redirect to proper mechanics (e.g., 'Roll to see if it works!'). "
                "Stay immersive — never break character. "
                "If a roll is needed, prompt the player to roll.]"
            )
            player_input += enforcement_note

        # Solo mode: pass character name + per-session history + directives
        solo_char = state.get("character_name") if state.get("is_solo") else None
        solo_kwargs = {}
        if solo_char:
            solo_kwargs = _build_solo_kwargs(state)

        if rules_ruling is not None:
            narrative = await storyteller.process_request(
                player_input, rules_ruling, solo_character=solo_char, **solo_kwargs
            )
        else:
            narrative = await storyteller.process_request(
                player_input,
                {"valid": True, "mechanic_used": "None", "result": state.get("board_context", "")},
                solo_character=solo_char, **solo_kwargs
            )

        logger.info(f"Generated narrative (len={len(narrative)})")
        return {"narrative": narrative}

    except Exception as e:
        logger.error(f"Storyteller node error: {e}", exc_info=True)
        return {"narrative": "", "error": f"Storyteller failed: {e}"}


def _build_solo_kwargs(state: GameState) -> dict:
    """Build keyword arguments for storyteller.process_request() in solo mode.

    Gathers per-session history, narrative directives (chaos, threads, NPCs,
    factions), and passes them through to the storyteller agent so they reach
    build_solo_storyteller_context().
    """
    kwargs = {}

    try:
        # Per-session history (Phase 0.1)
        from tools.solo_session import SoloSessionManager
        from bot.client import solo_manager

        thread_id = state.get("_solo_thread_id")
        if thread_id:
            history = solo_manager.get_history(thread_id)
            if history:
                kwargs["solo_history"] = history

            session = solo_manager.get_session(thread_id)
            if session:
                # Build narrative directives from session state
                directives = _build_solo_directives(session)
                if directives:
                    kwargs["solo_directives"] = directives
    except Exception as e:
        logger.warning(f"Failed to build solo kwargs: {e}")

    return kwargs


def _build_solo_directives(session) -> list:
    """Build narrative directive strings from solo session state."""
    directives = []

    try:
        from tools.solo_engine import (
            ChaosTracker, build_chaos_directive,
            NarrativeDirective, DirectivePriority, coordinate_directives,
        )
        from tools.solo_world import (
            ThreadTracker, SoloNPCRegistry, FactionTracker,
            build_thread_directive, build_npc_activity_directive,
            build_faction_directive,
        )

        turn = session.turn_count
        all_directives = []

        # Chaos directive
        chaos = ChaosTracker(factor=session.chaos_factor)
        event_type = chaos.check_random_event()
        alteration = chaos.check_scene_alteration()
        chaos_text = build_chaos_directive(chaos.factor, alteration, event_type)
        if chaos_text:
            all_directives.append(NarrativeDirective(DirectivePriority.CHAOS_EVENT, chaos_text))

        # Thread directives
        threads = ThreadTracker.from_list(session.active_threads)
        threads.check_dormancy(turn)
        dormant = threads.get_dormant()
        if dormant:
            thread_text = build_thread_directive(threads.get_active(), dormant, turn)
            if thread_text:
                all_directives.append(NarrativeDirective(DirectivePriority.DORMANT_THREAD, thread_text))

        # NPC activity directives
        npcs = SoloNPCRegistry.from_list(session.encountered_npcs)
        active_agents = npcs.get_active_agents(turn)
        if active_agents:
            npc_text = build_npc_activity_directive(active_agents, turn)
            if npc_text:
                all_directives.append(NarrativeDirective(DirectivePriority.NPC_ACTIVITY, npc_text))

        # Faction directives
        factions = FactionTracker.from_list(session.factions)
        faction_hints = factions.tick(turn)
        if faction_hints:
            faction_text = build_faction_directive(faction_hints)
            if faction_text:
                all_directives.append(NarrativeDirective(DirectivePriority.FACTION_EVENT, faction_text))

        # Include any queued directives from previous turn
        for qd in session.queued_directives:
            try:
                prio = DirectivePriority[qd.get("priority", "NPC_ACTIVITY")]
                all_directives.append(NarrativeDirective(prio, qd["text"]))
            except (KeyError, ValueError):
                pass

        # Coordinate: max 2 active per turn
        if all_directives:
            active_texts, queued = coordinate_directives(all_directives, max_active=2)
            directives = active_texts
            # Store queued for next turn
            session.queued_directives = [
                {"priority": d.priority.name, "text": d.text} for d in queued
            ]
        else:
            session.queued_directives = []

    except Exception as e:
        logger.warning(f"Failed to build solo directives: {e}")

    return directives


def _inject_oracle_grade(state: GameState, rules_ruling: dict, player_input: str) -> str:
    """Inject oracle grade into player_input if dice were rolled.

    Reads dice_results from state, grades the outcome, and appends
    the oracle directive to player_input.

    Returns the modified player_input (also modifies in place via reference,
    but caller should use the return value).
    """
    dice_results = state.get("dice_results")
    if not dice_results:
        return player_input

    try:
        from tools.solo_engine import grade_outcome, build_oracle_directive

        # Extract roll info from dice_results
        # dice_results is Dict[str, Dict[str, Any]] keyed by character name
        for char_name, roll_data in dice_results.items():
            if not isinstance(roll_data, dict):
                continue

            total = roll_data.get("total")
            dc = roll_data.get("dc") or rules_ruling.get("dc")
            if total is None or dc is None:
                continue

            is_nat_1 = roll_data.get("natural") == 1
            is_nat_20 = roll_data.get("natural") == 20

            grade = grade_outcome(total, dc, is_nat_1=is_nat_1, is_nat_20=is_nat_20)
            oracle_text = build_oracle_directive(grade)
            player_input += f"\n\n{oracle_text}"
            logger.debug(f"Oracle grade: {grade.value} (roll={total}, dc={dc})")
            break  # Solo has one character

    except Exception as e:
        logger.warning(f"Oracle grading failed (non-blocking): {e}")

    return player_input
