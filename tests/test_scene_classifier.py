"""
Smoke tests for the Scene Change Classifier (tools/scene_classifier.py).

Tests use mock AI clients -- no live Gemini connection needed.
"""

import asyncio
import json

from tools.scene_classifier import classify_scene_changes, _parse_lighting, CLASSIFIER_PROMPT


# ---------------------------------------------------------------------------
# Mock Helpers
# ---------------------------------------------------------------------------

class _MockResponse:
    def __init__(self, text):
        self.text = text


class _MockModels:
    def __init__(self, response_json):
        self._response = response_json

    async def generate_content(self, **kwargs):
        return _MockResponse(json.dumps(self._response))


class _MockAio:
    def __init__(self, response_json):
        self.models = _MockModels(response_json)


def _make_mock_client(response_dict):
    """Build a mock Gemini client that returns the given dict as JSON."""
    client = type("MockClient", (), {"aio": _MockAio(response_dict)})()
    return client


# ---------------------------------------------------------------------------
# Test 1: Module imports
# ---------------------------------------------------------------------------

def test_classify_scene_changes_is_callable():
    assert callable(classify_scene_changes)


def test_parse_lighting_is_callable():
    assert callable(_parse_lighting)


def test_classifier_prompt_exists():
    assert len(CLASSIFIER_PROMPT) > 50


# ---------------------------------------------------------------------------
# Test 2: _parse_lighting edge cases
# ---------------------------------------------------------------------------

def test_parse_lighting_none():
    assert _parse_lighting(None) is None


def test_parse_lighting_float():
    assert _parse_lighting(0.5) == 0.5


def test_parse_lighting_string():
    assert _parse_lighting("0.7") == 0.7


def test_parse_lighting_clamp_high():
    assert _parse_lighting(1.5) == 1.0


def test_parse_lighting_clamp_low():
    assert _parse_lighting(-0.3) == 0.0


def test_parse_lighting_invalid_string():
    assert _parse_lighting("invalid") is None


def test_parse_lighting_zero():
    assert _parse_lighting(0) == 0.0


def test_parse_lighting_one():
    assert _parse_lighting(1) == 1.0


# ---------------------------------------------------------------------------
# Test 3: Empty narrative returns no-changes
# ---------------------------------------------------------------------------

def test_empty_narrative_returns_defaults():
    result = asyncio.run(classify_scene_changes(
        narrative="",
        rules_json=None,
        current_location="The Yawning Portal",
        client=None,
        model_id="gemini-2.0-flash",
    ))
    assert isinstance(result, dict)
    assert result.get("location_changed") is False
    assert result.get("combat_started") is False
    assert result.get("combat_ended") is False
    assert result.get("monsters_introduced") == []
    assert result.get("lighting_change") is None
    assert result.get("foundry_actions_needed") is False
    assert result.get("new_location") is None


# ---------------------------------------------------------------------------
# Test 4: No client returns no-changes
# ---------------------------------------------------------------------------

def test_no_client_returns_defaults():
    result = asyncio.run(classify_scene_changes(
        narrative="The party marches into the dark forest.",
        rules_json=None,
        current_location="Town Square",
        client=None,
        model_id="gemini-2.0-flash",
    ))
    assert isinstance(result, dict)
    assert result.get("foundry_actions_needed") is False


# ---------------------------------------------------------------------------
# Test 5: Mock AI client -- location change
# ---------------------------------------------------------------------------

def test_location_change_detected():
    mock_response = {
        "location_changed": True,
        "new_location": "The Dark Forest",
        "combat_started": False,
        "combat_ended": False,
        "monsters_introduced": [],
        "lighting_change": 0.6,
        "foundry_actions_needed": True,
    }
    client = _make_mock_client(mock_response)

    result = asyncio.run(classify_scene_changes(
        narrative="You push through the tavern door and march into the dark forest.",
        rules_json=None,
        current_location="The Yawning Portal",
        client=client,
        model_id="gemini-2.0-flash",
    ))

    assert result["location_changed"] is True
    assert result["new_location"] == "The Dark Forest"
    assert result["combat_started"] is False
    assert result["lighting_change"] == 0.6
    assert result["foundry_actions_needed"] is True


# ---------------------------------------------------------------------------
# Test 6: Mock AI client -- combat start
# ---------------------------------------------------------------------------

def test_combat_start_detected():
    mock_response = {
        "location_changed": False,
        "new_location": None,
        "combat_started": True,
        "combat_ended": False,
        "monsters_introduced": ["Goblin", "Hobgoblin Captain"],
        "lighting_change": None,
        "foundry_actions_needed": True,
    }
    client = _make_mock_client(mock_response)

    result = asyncio.run(classify_scene_changes(
        narrative="From the treeline, a band of goblins bursts forth!",
        rules_json={"mechanic_used": "initiative"},
        current_location="Forest Path",
        client=client,
        model_id="gemini-2.0-flash",
    ))

    assert result["combat_started"] is True
    assert len(result["monsters_introduced"]) == 2
    assert "Goblin" in result["monsters_introduced"]
    assert "Hobgoblin Captain" in result["monsters_introduced"]
    assert result["foundry_actions_needed"] is True
    assert result["location_changed"] is False


# ---------------------------------------------------------------------------
# Test 7: Mock AI client -- no changes (dialogue)
# ---------------------------------------------------------------------------

def test_dialogue_no_changes():
    mock_response = {
        "location_changed": False,
        "new_location": None,
        "combat_started": False,
        "combat_ended": False,
        "monsters_introduced": [],
        "lighting_change": None,
        "foundry_actions_needed": False,
    }
    client = _make_mock_client(mock_response)

    result = asyncio.run(classify_scene_changes(
        narrative="The bartender leans across the counter and whispers.",
        rules_json=None,
        current_location="The Yawning Portal",
        client=client,
        model_id="gemini-2.0-flash",
    ))

    assert result["location_changed"] is False
    assert result["combat_started"] is False
    assert result["foundry_actions_needed"] is False
    assert result["new_location"] is None


# ---------------------------------------------------------------------------
# Test 8: _build_architect_request logic
# ---------------------------------------------------------------------------

def _build_architect_request(scene_changes, narrative):
    """Local copy of the request-building logic for isolated testing."""
    parts = []
    if scene_changes.get("combat_started"):
        monsters = scene_changes.get("monsters_introduced", [])
        if monsters:
            parts.append(f"Start a combat encounter with: {', '.join(monsters)}")
        else:
            parts.append("Start a combat encounter with the enemies described")
    if scene_changes.get("location_changed") and scene_changes.get("new_location"):
        parts.append(f"Scene change to: {scene_changes['new_location']}")
    if scene_changes.get("lighting_change") is not None:
        parts.append(f"Set scene darkness level to {scene_changes['lighting_change']}")
    if scene_changes.get("combat_ended"):
        parts.append("End the current combat encounter")
    if not parts:
        return ""
    request = ". ".join(parts)
    request += f"\n\nNarrative context: {narrative[:500]}"
    return request


def test_architect_request_combat_and_location():
    req = _build_architect_request(
        {"combat_started": True, "monsters_introduced": ["Goblin", "Wolf"],
         "location_changed": True, "new_location": "Forest Clearing",
         "lighting_change": None, "combat_ended": False},
        "A goblin and its wolf burst from the trees!"
    )
    assert "Start a combat encounter with: Goblin, Wolf" in req
    assert "Scene change to: Forest Clearing" in req
    assert "Narrative context:" in req


def test_architect_request_lighting_only():
    req = _build_architect_request(
        {"combat_started": False, "location_changed": False,
         "lighting_change": 0.8, "combat_ended": False,
         "monsters_introduced": []},
        "The last torch flickers and dies."
    )
    assert "Set scene darkness level to 0.8" in req


def test_architect_request_no_changes():
    req = _build_architect_request(
        {"combat_started": False, "location_changed": False,
         "lighting_change": None, "combat_ended": False,
         "monsters_introduced": []},
        "The bartender nods."
    )
    assert req == ""


def test_architect_request_combat_end():
    req = _build_architect_request(
        {"combat_started": False, "location_changed": False,
         "lighting_change": None, "combat_ended": True,
         "monsters_introduced": []},
        "The last goblin falls."
    )
    assert "End the current combat encounter" in req


# ---------------------------------------------------------------------------
# Test 9: Invalid JSON from AI handled gracefully
# ---------------------------------------------------------------------------

def test_invalid_json_returns_defaults():
    class _BadMockModels:
        async def generate_content(self, **kwargs):
            return _MockResponse("This is not valid JSON at all")

    class _BadMockAio:
        def __init__(self):
            self.models = _BadMockModels()

    client = type("BadMockClient", (), {"aio": _BadMockAio()})()

    result = asyncio.run(classify_scene_changes(
        narrative="The party enters the cave.",
        rules_json=None,
        current_location="Mountain Pass",
        client=client,
        model_id="gemini-2.0-flash",
    ))

    assert isinstance(result, dict)
    assert result.get("foundry_actions_needed") is False
