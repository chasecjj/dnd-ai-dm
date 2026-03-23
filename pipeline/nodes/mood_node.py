"""Pipeline node that runs the Mood Agent to assess emotional tone."""

import logging

from pipeline.state import GameState

logger = logging.getLogger("pipeline.mood")


async def mood_node(state: GameState, *, mood_agent, **_kwargs) -> dict:
    """Assess the emotional tone of the current game moment.

    Args:
        state: Current GameState.
        mood_agent: The MoodAgent instance (bound via functools.partial).

    Returns:
        dict with ``mood`` (str) and ``mood_assessment`` (dict).
    """
    # Extract context from state with safe defaults
    player_input = state.get("player_input", "")
    message_type = state.get("message_type", "game_action")
    location = state.get("current_location", "Unknown")
    is_solo = state.get("is_solo", False)

    # Time of day from world clock if available
    time_of_day = "unknown"
    # Scene state from board context or scene changes
    scene_state = state.get("board_context", "")
    # Chaos factor from solo session context (not directly in GameState — default 5)
    chaos_factor = 5
    # Recent narrative for context
    recent_narrative = state.get("narrative", "")
    # HP and conditions — not directly in base GameState, default healthy
    hp_percent = 1.0
    conditions: list[str] = []

    # If rules_ruling exists, extract HP info
    ruling = state.get("rules_ruling")
    if ruling and isinstance(ruling, dict):
        state_changes = ruling.get("state_changes", {})
        if state_changes and state_changes.get("hp_current") is not None:
            # Rough estimate — we don't have max HP in GameState
            hp_current = state_changes["hp_current"]
            hp_percent = max(0.0, min(1.0, hp_current / 50.0))  # Rough estimate
        conds_add = state_changes.get("conditions_add", []) if state_changes else []
        if conds_add:
            conditions = conds_add

    assessment = await mood_agent.assess(
        player_input=player_input,
        message_type=message_type,
        location=location,
        time_of_day=time_of_day,
        scene_state=scene_state,
        chaos_factor=chaos_factor,
        recent_narrative=recent_narrative,
        hp_percent=hp_percent,
        conditions=conditions,
    )

    logger.info(
        f"Mood: {assessment.primary_mood} (intensity {assessment.intensity})"
        f"{f', secondary: {assessment.secondary_mood}' if assessment.secondary_mood else ''}"
    )

    return {
        "mood": assessment.primary_mood,
        "mood_assessment": assessment.model_dump(),
    }
