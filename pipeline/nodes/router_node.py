"""
Router Node — Classifies the incoming message and sets pipeline routing flags.

Wraps the existing MessageRouterAgent. Returns partial GameState with
routing flags so conditional edges can decide what comes next.
"""

import logging
from pipeline.state import GameState
from tools.rate_limiter import gemini_limiter

logger = logging.getLogger("pipeline.router")


async def router_node(state: GameState, *, message_router, **_kwargs) -> dict:
    """Classify the player message and set routing flags.

    Args:
        state: Current GameState.
        message_router: The existing MessageRouterAgent instance.

    Returns:
        Partial state dict with routing flags set.
    """
    user_input = state["player_input"]

    # Fast path: DM-curated batch skips classification entirely
    if state.get("is_batched"):
        logger.info("Batched resolve — skipping router classification, enabling full pipeline")
        return {
            "message_type": "game_action",
            "direct_response": False,
            "needs_board_monitor": True,
            "needs_rules_lawyer": True,
            "needs_storyteller": True,
        }

    try:
        await gemini_limiter.acquire()
        route = await message_router.route(user_input)
        logger.info(f"Router classified as: {route}")

        from agents.message_router import MessageType

        # Casual chat → immediate stop
        if route.message_type == MessageType.CASUAL_CHAT:
            return {
                "message_type": "casual_chat",
                "direct_response": False,
                "needs_board_monitor": False,
                "needs_rules_lawyer": False,
                "needs_storyteller": False,
            }

        # Direct response (out-of-game question)
        if route.direct_response:
            await gemini_limiter.acquire()
            reply = await message_router.generate_direct_response(user_input)
            return {
                "message_type": "out_of_game",
                "direct_response": True,
                "direct_reply": reply,
                "needs_board_monitor": False,
                "needs_rules_lawyer": False,
                "needs_storyteller": False,
            }

        # Full pipeline
        return {
            "message_type": route.message_type.value if hasattr(route.message_type, "value") else str(route.message_type),
            "direct_response": False,
            "needs_board_monitor": route.needs_board_monitor,
            "needs_rules_lawyer": route.needs_rules_lawyer,
            "needs_storyteller": route.needs_storyteller,
        }

    except Exception as e:
        logger.error(f"Router node error: {e}", exc_info=True)
        return {"error": f"Router failed: {e}"}
