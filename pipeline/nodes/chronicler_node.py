"""
Chronicler Node — Silent record-keeper that updates the vault after each exchange.

Wraps the existing ChroniclerAgent. Runs last. Never speaks to players.
Errors here never affect gameplay.
"""

import logging
from pipeline.state import GameState
from tools.rate_limiter import gemini_limiter

logger = logging.getLogger("pipeline.chronicler")


async def chronicler_node(
    state: GameState,
    *,
    chronicler,
    context_assembler,
    storyteller,
    **_kwargs,
) -> dict:
    """Process the exchange and update the vault.

    Args:
        state: Current GameState.
        chronicler: The existing ChroniclerAgent instance.
        context_assembler: For saving checkpoints.
        storyteller: For current location.
    """
    # Only chronicle if we ran the rules lawyer or storyteller
    if not state.get("needs_rules_lawyer") and not state.get("needs_storyteller"):
        return {"chronicler_done": False}

    try:
        rules_text = str(state.get("rules_ruling")) if state.get("rules_ruling") else "N/A"
        await gemini_limiter.acquire()
        await chronicler.process_exchange(
            player_action=state["player_input"],
            rules_response=rules_text,
            story_response=state.get("narrative", ""),
            session_number=state.get("session", 0),
            current_location=storyteller._current_location,
        )
        context_assembler.save_checkpoint()
        return {"chronicler_done": True}

    except Exception as e:
        # Chronicler errors are NEVER blocking
        logger.error(f"Chronicler node error (non-blocking): {e}", exc_info=True)
        return {"chronicler_done": False}
