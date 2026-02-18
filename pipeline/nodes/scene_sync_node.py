"""
Scene Sync Node — Detects board changes from narrative and updates Foundry VTT.

Runs after the Storyteller. Non-blocking — errors here never affect gameplay.
"""

import logging
from pipeline.state import GameState
from tools.rate_limiter import gemini_limiter

logger = logging.getLogger("pipeline.scene_sync")


async def scene_sync_node(
    state: GameState,
    *,
    storyteller,
    gemini_client,
    model_id,
    **_kwargs,
) -> dict:
    """Classify scene changes from the narrative.

    Note: Foundry dispatch (token placement, scene switching) is handled
    by bot/client.py AFTER the pipeline returns. This node only classifies.

    Args:
        state: Current GameState.
        storyteller: For reading current location.
        gemini_client: Gemini API client.
        model_id: Gemini model ID.
    """
    narrative = state.get("narrative", "")
    if not narrative:
        return {"scene_changes": None}

    try:
        from tools.scene_classifier import classify_scene_changes

        await gemini_limiter.acquire()
        changes = await classify_scene_changes(
            narrative=narrative,
            rules_json=state.get("rules_ruling"),
            current_location=storyteller._current_location,
            client=gemini_client,
            model_id=model_id,
        )

        # Update location tracking
        if changes.get("location_changed") and changes.get("new_location"):
            old_loc = storyteller._current_location
            storyteller.set_location(changes["new_location"])
            logger.info(f"Location updated: {old_loc} -> {changes['new_location']}")

        return {"scene_changes": changes, "current_location": storyteller._current_location}

    except Exception as e:
        # Scene sync errors are NEVER blocking
        logger.warning(f"Scene sync node error (non-blocking): {e}", exc_info=True)
        return {"scene_changes": None}
