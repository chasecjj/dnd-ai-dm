"""
Rules Lawyer Node — Validates game mechanics and produces a structured ruling.

Wraps the existing RulesLawyerAgent. Only runs if needs_rules_lawyer is True.
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
        context_assembler.set_query(state["player_input"])
        await gemini_limiter.acquire()
        ruling = await rules_lawyer.process_request(
            state["player_input"],
            state.get("board_context", ""),
        )
        logger.info(f"Rules ruling: {ruling}")
        return {"rules_ruling": ruling}

    except Exception as e:
        logger.error(f"Rules node error: {e}", exc_info=True)
        return {"rules_ruling": None, "error": f"Rules Lawyer failed: {e}"}
