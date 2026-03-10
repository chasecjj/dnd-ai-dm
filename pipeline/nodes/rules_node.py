"""
Rules Lawyer Node — Validates game mechanics and produces a structured ruling.

Wraps the existing RulesLawyerAgent. Only runs if needs_rules_lawyer is True.

Solo guardrails include death alternatives (Phase 1.2) — when a solo PC
reaches 0 HP, the rules lawyer should recommend alternatives to death.
"""

import logging
from pipeline.state import GameState
from tools.rate_limiter import gemini_limiter

logger = logging.getLogger("pipeline.rules")


async def rules_node(state: GameState, *, rules_lawyer, context_assembler, **_kwargs) -> dict:
    """Produce a mechanical ruling for the player action.

    Args:
        state: Current GameState.
        rules_lawyer: The existing RulesLawyerAgent instance.
        context_assembler: For setting the query context.
    """
    if not state.get("needs_rules_lawyer"):
        return {"rules_ruling": None}

    try:
        action_input = state["player_input"]
        if state.get("is_solo"):
            action_input += (
                "\n[SOLO SESSION: No XP/leveling, no spending shared party "
                "resources, no killing named campaign NPCs. Minor items/gold OK."
                "\nDEATH ALTERNATIVE: If this action would reduce the PC to 0 HP, "
                "do NOT declare them dead. Instead recommend one of: capture, "
                "debilitating injury, debt to a rescuer, a curse/mark, or divine "
                "intervention with cost. Include the alternative in your ruling.]"
            )

        context_assembler.set_query(action_input)
        await gemini_limiter.acquire()
        ruling = await rules_lawyer.process_request(
            action_input,
            state.get("board_context", ""),
            dice_results=state.get("dice_results"),
        )
        logger.info(f"Rules ruling: {ruling}")
        return {"rules_ruling": ruling}

    except Exception as e:
        logger.error(f"Rules node error: {e}", exc_info=True)
        return {"rules_ruling": None, "error": f"Rules Lawyer failed: {e}"}
