"""
Scene Change Classifier — Lightweight post-Storyteller analysis.

Analyzes the Storyteller's narrative output to detect whether the
virtual tabletop needs updating (location change, combat start/end,
lighting shift, new monsters).

This runs AFTER the player has already received their narrative,
so latency here doesn't block gameplay.
"""

import json
import logging
from typing import Dict, Any, Optional
from google import genai

logger = logging.getLogger('SceneClassifier')


CLASSIFIER_PROMPT = """You are a scene-change detector for a D&D virtual tabletop.

Analyze the narrative below and determine if ANY of these happened:

1. **Location Change** — Did the party move to a NEW location? (entering a building, leaving town, going to a different room, etc.)
2. **Combat Started** — Did a fight begin? (enemies appeared, initiative implied, hostile action started)
3. **Combat Ended** — Did a fight end? (enemies defeated, fled, surrendered, combat resolved)
4. **New Monsters** — Were specific enemy creatures introduced by name/type?
5. **Lighting Change** — Did the environment's light level change? (entering a dark cave, sunset, torches extinguished, dawn breaking)

Current known location: {current_location}

IMPORTANT RULES:
- Only flag location_changed if the party actually MOVED to a different place, not just looked at or talked about one.
- If location_changed is true, you MUST provide new_location as a short place name (e.g. "Market District", "Dark Forest", "Goblin Cave").
- Only flag combat_started if combat actually BEGAN in this narrative, not if it was already ongoing.
- For lighting_change, use a 0.0-1.0 scale: 0.0 = bright daylight, 0.3 = overcast/dim, 0.5 = twilight/torchlight, 0.7 = dark cave, 1.0 = pitch black. Use null if no change.
- monsters_introduced must be a list of creature names (strings), NOT a boolean.
- Set foundry_actions_needed to true if ANY change was detected.

You MUST respond with ONLY this exact JSON structure:
{{
    "location_changed": true/false,
    "new_location": "Place Name" or null,
    "combat_started": true/false,
    "combat_ended": true/false,
    "monsters_introduced": ["Creature Name"] or [],
    "lighting_change": 0.0-1.0 or null,
    "foundry_actions_needed": true/false
}}"""


async def classify_scene_changes(
    narrative: str,
    rules_json: Optional[Dict[str, Any]],
    current_location: Optional[str],
    client,
    model_id: str = "gemini-2.0-flash",
) -> Dict[str, Any]:
    """
    Classify whether a Storyteller narrative implies Foundry board changes.

    Args:
        narrative: The Storyteller's prose output.
        rules_json: The Rules Lawyer's mechanical ruling (for combat context).
        current_location: The party's current known location.
        client: The Gemini client instance.
        model_id: Model to use for classification.

    Returns:
        Dict with keys:
            location_changed (bool)
            new_location (str or None)
            combat_started (bool)
            combat_ended (bool)
            monsters_introduced (list of str)
            lighting_change (float or None)
            foundry_actions_needed (bool)
    """
    # Default "no changes" response
    no_changes = {
        "location_changed": False,
        "new_location": None,
        "combat_started": False,
        "combat_ended": False,
        "monsters_introduced": [],
        "lighting_change": None,
        "foundry_actions_needed": False,
    }

    if not narrative or not narrative.strip():
        return no_changes

    if not client:
        logger.warning("No AI client available for scene classification.")
        return no_changes

    # Build the classification prompt
    loc_str = current_location or "Unknown"
    system_prompt = CLASSIFIER_PROMPT.format(current_location=loc_str)

    # Include rules context if available (helps detect combat)
    rules_context = ""
    if rules_json and isinstance(rules_json, dict):
        mechanic = rules_json.get("mechanic_used", "")
        if mechanic:
            rules_context = f"\n\nRules Lawyer mechanic used: {mechanic}"

    user_prompt = f"""## Narrative to Analyze
{narrative}
{rules_context}

Classify the scene changes as JSON."""

    try:
        response = await client.aio.models.generate_content(
            model=model_id,
            contents=user_prompt,
            config=genai.types.GenerateContentConfig(
                system_instruction=system_prompt,
                temperature=0.1,  # Low temp for reliable classification
                response_mime_type="application/json",
            )
        )

        result = json.loads(response.text)
        logger.info(f"Scene classification: {result}")

        # Validate and normalize the response (handle AI key variations)
        monsters = result.get("monsters_introduced") or result.get("new_monsters_npcs") or result.get("monsters") or []
        if isinstance(monsters, bool):
            monsters = []  # AI sometimes returns True/False instead of a list

        return {
            "location_changed": bool(result.get("location_changed", False)),
            "new_location": result.get("new_location") or result.get("location") or None,
            "combat_started": bool(result.get("combat_started", False)),
            "combat_ended": bool(result.get("combat_ended", False)),
            "monsters_introduced": monsters if isinstance(monsters, list) else [],
            "lighting_change": _parse_lighting(result.get("lighting_change")),
            "foundry_actions_needed": bool(result.get("foundry_actions_needed", False)),
        }

    except json.JSONDecodeError as e:
        logger.warning(f"Scene classifier returned invalid JSON: {e}")
        return no_changes
    except Exception as e:
        logger.error(f"Scene classifier failed: {e}", exc_info=True)
        return no_changes


def _parse_lighting(value) -> Optional[float]:
    """Safely parse a lighting value to a float in [0.0, 1.0] or None."""
    if value is None:
        return None
    try:
        val = float(value)
        return max(0.0, min(1.0, val))
    except (TypeError, ValueError):
        return None
