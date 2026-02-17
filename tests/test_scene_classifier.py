"""
Smoke tests for the Scene Change Classifier.

Tests:
1. Module import and function signature
2. Empty/missing narrative returns no-changes
3. _parse_lighting edge cases
4. _build_architect_request formatting
5. Full classify_scene_changes with mock AI client
"""

import sys
import asyncio
import json

sys.path.insert(0, '.')

passed = 0
failed = 0


def test(name, condition, detail=""):
    global passed, failed
    if condition:
        print(f"  ✅ {name}")
        passed += 1
    else:
        print(f"  ❌ {name} — {detail}")
        failed += 1


# ── Test 1: Import ────────────────────────────────────────────────
print("=" * 60)
print("TEST 1: Module imports and function availability")
print("=" * 60)
try:
    from tools.scene_classifier import classify_scene_changes, _parse_lighting, CLASSIFIER_PROMPT
    test("classify_scene_changes imported", callable(classify_scene_changes))
    test("_parse_lighting imported", callable(_parse_lighting))
    test("CLASSIFIER_PROMPT exists", len(CLASSIFIER_PROMPT) > 50)
except Exception as e:
    test("Import", False, str(e))

# ── Test 2: _parse_lighting edge cases ────────────────────────────
print("\n" + "=" * 60)
print("TEST 2: _parse_lighting edge cases")
print("=" * 60)
try:
    test("None returns None", _parse_lighting(None) is None)
    test("0.5 returns 0.5", _parse_lighting(0.5) == 0.5)
    test("'0.7' string returns 0.7", _parse_lighting("0.7") == 0.7)
    test("1.5 clamps to 1.0", _parse_lighting(1.5) == 1.0)
    test("-0.3 clamps to 0.0", _parse_lighting(-0.3) == 0.0)
    test("'invalid' returns None", _parse_lighting("invalid") is None)
    test("0 returns 0.0", _parse_lighting(0) == 0.0)
    test("1 returns 1.0", _parse_lighting(1) == 1.0)
except Exception as e:
    test("_parse_lighting", False, str(e))

# ── Test 3: Empty narrative returns no-changes ────────────────────
print("\n" + "=" * 60)
print("TEST 3: Empty narrative returns no-changes default")
print("=" * 60)
try:
    result = asyncio.run(classify_scene_changes(
        narrative="",
        rules_json=None,
        current_location="The Yawning Portal",
        client=None,
        model_id="gemini-2.0-flash",
    ))
    test("Returns dict", isinstance(result, dict))
    test("location_changed is False", result.get("location_changed") is False)
    test("combat_started is False", result.get("combat_started") is False)
    test("combat_ended is False", result.get("combat_ended") is False)
    test("monsters_introduced is empty", result.get("monsters_introduced") == [])
    test("lighting_change is None", result.get("lighting_change") is None)
    test("foundry_actions_needed is False", result.get("foundry_actions_needed") is False)
    test("new_location is None", result.get("new_location") is None)
except Exception as e:
    test("Empty narrative", False, str(e))

# ── Test 4: No client returns no-changes ──────────────────────────
print("\n" + "=" * 60)
print("TEST 4: No AI client returns no-changes gracefully")
print("=" * 60)
try:
    result = asyncio.run(classify_scene_changes(
        narrative="The party marches into the dark forest.",
        rules_json=None,
        current_location="Town Square",
        client=None,
        model_id="gemini-2.0-flash",
    ))
    test("Returns dict", isinstance(result, dict))
    test("foundry_actions_needed is False", result.get("foundry_actions_needed") is False)
except Exception as e:
    test("No client", False, str(e))


# ── Test 5: Mock AI client — location change ──────────────────────
print("\n" + "=" * 60)
print("TEST 5: Mock AI client — location change detection")
print("=" * 60)


class MockResponse:
    def __init__(self, text):
        self.text = text


class MockModels:
    def __init__(self, response_json):
        self._response = response_json

    async def generate_content(self, **kwargs):
        return MockResponse(json.dumps(self._response))


class MockAio:
    def __init__(self, response_json):
        self.models = MockModels(response_json)


class MockClient:
    def __init__(self, response_json):
        self.aio = MockAio(response_json)


try:
    # Simulate a location change response
    mock_response = {
        "location_changed": True,
        "new_location": "The Dark Forest",
        "combat_started": False,
        "combat_ended": False,
        "monsters_introduced": [],
        "lighting_change": 0.6,
        "foundry_actions_needed": True,
    }
    mock_client = MockClient(mock_response)

    result = asyncio.run(classify_scene_changes(
        narrative="You push through the tavern door and march into the dark forest. The canopy above blocks most of the moonlight.",
        rules_json=None,
        current_location="The Yawning Portal",
        client=mock_client,
        model_id="gemini-2.0-flash",
    ))

    test("location_changed is True", result["location_changed"] is True)
    test("new_location is 'The Dark Forest'", result["new_location"] == "The Dark Forest")
    test("combat_started is False", result["combat_started"] is False)
    test("lighting_change is 0.6", result["lighting_change"] == 0.6)
    test("foundry_actions_needed is True", result["foundry_actions_needed"] is True)
except Exception as e:
    test("Mock location change", False, str(e))


# ── Test 6: Mock AI client — combat start ─────────────────────────
print("\n" + "=" * 60)
print("TEST 6: Mock AI client — combat start detection")
print("=" * 60)
try:
    mock_response = {
        "location_changed": False,
        "new_location": None,
        "combat_started": True,
        "combat_ended": False,
        "monsters_introduced": ["Goblin", "Hobgoblin Captain"],
        "lighting_change": None,
        "foundry_actions_needed": True,
    }
    mock_client = MockClient(mock_response)

    result = asyncio.run(classify_scene_changes(
        narrative="From the treeline, a band of goblins bursts forth! A hobgoblin captain barks orders as they charge.",
        rules_json={"mechanic_used": "initiative"},
        current_location="Forest Path",
        client=mock_client,
        model_id="gemini-2.0-flash",
    ))

    test("combat_started is True", result["combat_started"] is True)
    test("monsters_introduced has 2", len(result["monsters_introduced"]) == 2)
    test("'Goblin' in monsters", "Goblin" in result["monsters_introduced"])
    test("'Hobgoblin Captain' in monsters", "Hobgoblin Captain" in result["monsters_introduced"])
    test("foundry_actions_needed is True", result["foundry_actions_needed"] is True)
    test("location_changed is False", result["location_changed"] is False)
except Exception as e:
    test("Mock combat start", False, str(e))


# ── Test 7: Mock AI client — no changes ───────────────────────────
print("\n" + "=" * 60)
print("TEST 7: Mock AI client — dialogue scene (no changes)")
print("=" * 60)
try:
    mock_response = {
        "location_changed": False,
        "new_location": None,
        "combat_started": False,
        "combat_ended": False,
        "monsters_introduced": [],
        "lighting_change": None,
        "foundry_actions_needed": False,
    }
    mock_client = MockClient(mock_response)

    result = asyncio.run(classify_scene_changes(
        narrative="The bartender leans across the counter and whispers about strange happenings in the woods.",
        rules_json=None,
        current_location="The Yawning Portal",
        client=mock_client,
        model_id="gemini-2.0-flash",
    ))

    test("location_changed is False", result["location_changed"] is False)
    test("combat_started is False", result["combat_started"] is False)
    test("foundry_actions_needed is False", result["foundry_actions_needed"] is False)
    test("new_location is None", result["new_location"] is None)
except Exception as e:
    test("Mock no changes", False, str(e))


# ── Test 8: _build_architect_request ──────────────────────────────
print("\n" + "=" * 60)
print("TEST 8: _build_architect_request formatting")
print("=" * 60)
try:
    # We need to import from bot.py which has Discord dependencies,
    # so let's test the logic directly instead
    def build_architect_request(scene_changes, narrative):
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

    # Test combat + location
    req = build_architect_request(
        {"combat_started": True, "monsters_introduced": ["Goblin", "Wolf"],
         "location_changed": True, "new_location": "Forest Clearing",
         "lighting_change": None, "combat_ended": False},
        "A goblin and its wolf burst from the trees in the forest clearing!"
    )
    test("Contains combat start", "Start a combat encounter with: Goblin, Wolf" in req)
    test("Contains scene change", "Scene change to: Forest Clearing" in req)
    test("Contains narrative context", "Narrative context:" in req)

    # Test lighting only
    req2 = build_architect_request(
        {"combat_started": False, "location_changed": False,
         "lighting_change": 0.8, "combat_ended": False,
         "monsters_introduced": []},
        "The last torch flickers and dies."
    )
    test("Contains darkness level", "Set scene darkness level to 0.8" in req2)

    # Test empty — no actions needed
    req3 = build_architect_request(
        {"combat_started": False, "location_changed": False,
         "lighting_change": None, "combat_ended": False,
         "monsters_introduced": []},
        "The bartender nods."
    )
    test("Empty request for no changes", req3 == "")

    # Test combat end
    req4 = build_architect_request(
        {"combat_started": False, "location_changed": False,
         "lighting_change": None, "combat_ended": True,
         "monsters_introduced": []},
        "The last goblin falls."
    )
    test("Contains combat end", "End the current combat encounter" in req4)

except Exception as e:
    test("_build_architect_request", False, str(e))


# ── Test 9: Invalid JSON from AI handled gracefully ───────────────
print("\n" + "=" * 60)
print("TEST 9: Invalid JSON from AI returns no-changes")
print("=" * 60)
try:
    class BadMockModels:
        async def generate_content(self, **kwargs):
            return MockResponse("This is not valid JSON at all")

    class BadMockAio:
        def __init__(self):
            self.models = BadMockModels()

    class BadMockClient:
        def __init__(self):
            self.aio = BadMockAio()

    result = asyncio.run(classify_scene_changes(
        narrative="The party enters the cave.",
        rules_json=None,
        current_location="Mountain Pass",
        client=BadMockClient(),
        model_id="gemini-2.0-flash",
    ))

    test("Returns dict on bad JSON", isinstance(result, dict))
    test("foundry_actions_needed is False", result.get("foundry_actions_needed") is False)
except Exception as e:
    test("Invalid JSON handling", False, str(e))


# ── Summary ───────────────────────────────────────────────────────
print("\n" + "=" * 60)
total = passed + failed
print(f"RESULTS: {passed}/{total} passed, {failed} failed")
if failed == 0:
    print("🎉 ALL TESTS PASSED!")
else:
    print(f"⚠️  {failed} test(s) failed")
print("=" * 60)
