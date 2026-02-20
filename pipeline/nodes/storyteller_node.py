"""
Storyteller Node — Generates immersive narrative prose.

Wraps the existing StorytellerAgent. Only runs if needs_storyteller is True.
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

        if rules_ruling is not None:
            narrative = await storyteller.process_request(player_input, rules_ruling)
        else:
            narrative = await storyteller.process_request(
                player_input,
                {"valid": True, "mechanic_used": "None", "result": state.get("board_context", "")},
            )

        logger.info(f"Generated narrative (len={len(narrative)})")
        return {"narrative": narrative}

    except Exception as e:
        logger.error(f"Storyteller node error: {e}", exc_info=True)
        return {"narrative": "", "error": f"Storyteller failed: {e}"}
