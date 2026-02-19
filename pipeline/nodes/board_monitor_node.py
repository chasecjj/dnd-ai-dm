"""
Board Monitor Node — Pulls live Foundry VTT spatial context.

Wraps the existing BoardMonitorAgent. Only runs if needs_board_monitor is True.
"""

import logging
from pipeline.state import GameState

logger = logging.getLogger("pipeline.board_monitor")


async def board_monitor_node(state: GameState, *, board_monitor, **_kwargs) -> dict:
    """Pull spatial context from Foundry VTT.

    Args:
        state: Current GameState.
        board_monitor: The existing BoardMonitorAgent instance.
    """
    if not state.get("needs_board_monitor"):
        return {"board_context": ""}

    try:
        context = await board_monitor.process_request(state["player_input"])
        if context == "No specific board state queried.":
            context = ""
        logger.info(f"Board context: {context[:100]}...")
        return {"board_context": context}

    except Exception as e:
        logger.error(f"Board monitor node error: {e}", exc_info=True)
        return {"board_context": ""}
