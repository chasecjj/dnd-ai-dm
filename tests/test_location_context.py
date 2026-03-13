"""
Tests for the Storyteller location re-description fix.

Validates that:
  - First turn always gets full location descriptions
  - Same location on subsequent turns gets brief context
  - Moving to a new location triggers full description again
  - Returning to a previously-described location triggers full again
  - Split-party scenarios produce a mix of full and brief
  - reset_location_tracking() restores first-turn behavior
  - _build_brief_location_section() has the expected format
  - build_storyteller_context() with new_locations=None is backward-compatible
  - Monster turns (new_locations=set()) always get brief context
"""

import pytest
from unittest.mock import MagicMock
from tools.context_assembler import ContextAssembler
from agents.storyteller import StorytellerAgent


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def vault():
    """Minimal mock VaultManager for location context tests."""
    v = MagicMock()
    v.vault_path = "/fake/vault"
    v.read_world_clock.return_value = {
        "current_date": "1 Mirtul 1492 DR",
        "time_of_day": "Morning",
        "session": 1,
    }
    v.get_party_state.return_value = []
    v.get_active_quests.return_value = []
    v.get_due_consequences.return_value = []
    v.list_files.return_value = []

    def get_location(name):
        locations = {
            "The Yawning Portal": (
                {"name": "The Yawning Portal", "type": "tavern"},
                "## Description\nA famous tavern in Waterdeep.\n## Current State\nBustling with adventurers.\n## Notable Features\nThe gaping pit in the center.",
            ),
            "Zhentarim Hideout": (
                {"name": "Zhentarim Hideout", "type": "hideout"},
                "## Description\nA dark basement beneath a warehouse.\n## Current State\nQuiet and tense.\n## Notable Features\nCrates of contraband.",
            ),
        }
        return locations.get(name)

    def get_npcs(name):
        npcs = {
            "The Yawning Portal": [
                {"frontmatter": {"name": "Durnan", "role": "Barkeep", "disposition": "gruff", "status": "alive"}},
            ],
            "Zhentarim Hideout": [
                {"frontmatter": {"name": "Davil Starsong", "role": "Agent", "disposition": "charming", "status": "alive"}},
            ],
        }
        return npcs.get(name, [])

    v.get_location.side_effect = get_location
    v.get_npcs_at_location.side_effect = get_npcs
    return v


@pytest.fixture
def assembler(vault):
    return ContextAssembler(vault)


@pytest.fixture
def storyteller(assembler):
    client = MagicMock()
    return StorytellerAgent(client, assembler)


# ---------------------------------------------------------------------------
# StorytellerAgent location tracking
# ---------------------------------------------------------------------------

class TestLocationTracking:
    """Tests for _compute_new_locations / _mark_locations_described."""

    def test_first_turn_all_locations_new(self, storyteller):
        storyteller.set_location("The Yawning Portal")
        new = storyteller._compute_new_locations()
        assert "The Yawning Portal" in new

    def test_same_location_not_new_after_mark(self, storyteller):
        storyteller.set_location("The Yawning Portal")
        storyteller._mark_locations_described()
        storyteller._first_turn = False
        new = storyteller._compute_new_locations()
        assert "The Yawning Portal" not in new

    def test_new_location_detected(self, storyteller):
        storyteller.set_location("The Yawning Portal")
        storyteller._mark_locations_described()
        storyteller._first_turn = False
        # Move to a new location
        storyteller.set_location("Zhentarim Hideout")
        new = storyteller._compute_new_locations()
        assert "Zhentarim Hideout" in new

    def test_return_to_previous_location_is_new(self, storyteller):
        storyteller.set_location("The Yawning Portal")
        storyteller._mark_locations_described()
        storyteller._first_turn = False
        # Move away
        storyteller.set_location("Zhentarim Hideout")
        storyteller._mark_locations_described()
        # Move back
        storyteller.set_location("The Yawning Portal")
        new = storyteller._compute_new_locations()
        assert "The Yawning Portal" in new

    def test_split_party_mixed(self, storyteller):
        storyteller.set_character_location("Victor", "The Yawning Portal")
        storyteller.set_character_location("Hadrian", "Zhentarim Hideout")
        # Mark both as described
        storyteller._mark_locations_described()
        storyteller._first_turn = False
        # Only Victor moves
        storyteller.set_character_location("Victor", "Zhentarim Hideout")
        new = storyteller._compute_new_locations()
        # Zhentarim is new for Victor (was at YP), but Hadrian's location unchanged
        assert "Zhentarim Hideout" in new
        assert "The Yawning Portal" not in new

    def test_reset_location_tracking(self, storyteller):
        storyteller.set_location("The Yawning Portal")
        storyteller._mark_locations_described()
        storyteller._first_turn = False
        # After reset, everything should be treated as first turn again
        storyteller.reset_location_tracking()
        assert storyteller._first_turn is True
        assert storyteller._described_locations == {}
        new = storyteller._compute_new_locations()
        assert "The Yawning Portal" in new


# ---------------------------------------------------------------------------
# ContextAssembler brief section
# ---------------------------------------------------------------------------

class TestBriefLocationSection:
    """Tests for _build_brief_location_section format."""

    def test_brief_section_has_same_location_marker(self, assembler):
        section = assembler._build_brief_location_section("The Yawning Portal")
        assert "[SAME LOCATION" in section
        assert "The Yawning Portal" in section

    def test_brief_section_includes_npcs(self, assembler):
        section = assembler._build_brief_location_section("The Yawning Portal")
        assert "Durnan" in section
        assert "NPCs Present" in section

    def test_brief_section_excludes_prose(self, assembler):
        section = assembler._build_brief_location_section("The Yawning Portal")
        assert "famous tavern" not in section
        assert "Bustling with adventurers" not in section
        assert "gaping pit" not in section


# ---------------------------------------------------------------------------
# build_storyteller_context integration
# ---------------------------------------------------------------------------

class TestBuildContextWithNewLocations:
    """Tests for new_locations parameter on build_storyteller_context."""

    def test_none_means_full_everywhere(self, assembler):
        """new_locations=None is backward-compatible — always full descriptions."""
        ctx = assembler.build_storyteller_context("The Yawning Portal", new_locations=None)
        assert "famous tavern" in ctx
        assert "[SAME LOCATION" not in ctx

    def test_empty_set_means_all_brief(self, assembler):
        """new_locations=set() makes all locations brief (monster turn case)."""
        ctx = assembler.build_storyteller_context("The Yawning Portal", new_locations=set())
        assert "[SAME LOCATION" in ctx
        assert "famous tavern" not in ctx
        # NPCs should still be present
        assert "Durnan" in ctx

    def test_location_in_set_gets_full(self, assembler):
        """Location explicitly in new_locations gets full description."""
        ctx = assembler.build_storyteller_context(
            "The Yawning Portal",
            new_locations={"The Yawning Portal"},
        )
        assert "famous tavern" in ctx
        assert "[SAME LOCATION" not in ctx


# ---------------------------------------------------------------------------
# _format_npc_entry
# ---------------------------------------------------------------------------

class TestFormatNpcEntry:
    """Tests for NPC entry formatting with description and personality extraction."""

    def test_format_npc_entry_with_description(self, assembler):
        npc = {
            "frontmatter": {"name": "Durnan", "role": "Barkeep", "disposition": "gruff", "status": "alive"},
            "body": "## Description\nA burly man with a scarred face and thick arms.\n## Personality\nGruff but fair.",
        }
        result = assembler._format_npc_entry(npc)
        assert "Appearance:" in result
        assert "A burly man" in result
        # Description should be truncated to 200 chars max
        assert len(result.split("Appearance: ")[1].split("\n")[0]) <= 200

    def test_format_npc_entry_with_personality(self, assembler):
        npc = {
            "frontmatter": {"name": "Durnan", "role": "Barkeep", "disposition": "gruff", "status": "alive"},
            "body": "## Description\nA burly man.\n## Personality\nGruff but fair, with a heart of gold buried under years of hardship.",
        }
        result = assembler._format_npc_entry(npc)
        assert "Personality:" in result
        # Personality should be capped at 150 chars
        pers_line = [l for l in result.split("\n") if "Personality:" in l][0]
        pers_text = pers_line.split("Personality: ")[1]
        assert len(pers_text) <= 150

    def test_format_npc_entry_empty_body(self, assembler):
        npc = {
            "frontmatter": {"name": "Durnan", "role": "Barkeep", "disposition": "gruff", "status": "alive"},
            "body": "",
        }
        result = assembler._format_npc_entry(npc)
        assert result == "- **Durnan** (Barkeep) — gruff"
        assert "Appearance:" not in result
        assert "Personality:" not in result

    def test_format_npc_entry_skips_placeholders(self, assembler):
        npc = {
            "frontmatter": {"name": "Durnan", "role": "Barkeep", "disposition": "gruff", "status": "alive"},
            "body": "## Description\n_Physical appearance, mannerisms, voice._\n## Personality\n_Key traits._",
        }
        result = assembler._format_npc_entry(npc)
        assert "Appearance:" not in result
        assert "Personality:" not in result


# ---------------------------------------------------------------------------
# _build_narrative_window
# ---------------------------------------------------------------------------

class TestBuildNarrativeWindow:
    """Tests for the narrative sliding window builder."""

    def test_build_narrative_window_last_three(self):
        entries = [
            {"turn": i, "player_input": f"action {i}", "narrative": f"narration {i}"}
            for i in range(1, 6)
        ]
        result = ContextAssembler._build_narrative_window(entries)
        assert result is not None
        # Only last 3 turns (3, 4, 5) should appear
        assert "Turn 3" in result
        assert "Turn 4" in result
        assert "Turn 5" in result
        assert "Turn 1" not in result
        assert "Turn 2" not in result

    def test_build_narrative_window_truncation(self):
        long_input = "x" * 200
        long_narrative = "y" * 1000
        entries = [{"turn": 1, "player_input": long_input, "narrative": long_narrative}]
        result = ContextAssembler._build_narrative_window(entries)
        assert result is not None
        # Player input truncated to 150 chars
        assert "x" * 150 in result
        assert "x" * 151 not in result
        # Narrative truncated to 800 chars
        assert "y" * 800 in result
        assert "y" * 801 not in result

    def test_build_narrative_window_empty(self):
        result = ContextAssembler._build_narrative_window([])
        assert result is None


# ---------------------------------------------------------------------------
# _build_scene_state_section
# ---------------------------------------------------------------------------

class TestBuildSceneStateSection:
    """Tests for the scene state ground-truth section builder."""

    def test_build_scene_state_entities(self):
        scene_state = {
            "entities_present": [
                {
                    "name": "Durnan",
                    "physical_description": "A burly man",
                    "current_demeanor": "watchful",
                    "holding_items": ["mug", "towel"],
                },
                {
                    "name": "Yagra",
                    "physical_description": "A half-orc bruiser",
                    "current_demeanor": "aggressive",
                    "holding_items": [],
                },
            ],
        }
        result = ContextAssembler._build_scene_state_section(scene_state)
        assert result is not None
        assert "**Durnan**" in result
        assert "**Yagra**" in result
        assert "### Present" in result

    def test_build_scene_state_objects(self):
        scene_state = {
            "objects_in_play": [
                {"name": "Ale Mug", "holder": "Durnan", "description": "A frothy pint"},
                {"name": "Longsword", "holder": "", "description": "Leaning against the wall"},
            ],
        }
        result = ContextAssembler._build_scene_state_section(scene_state)
        assert result is not None
        assert "**Ale Mug**" in result
        assert "held by Durnan" in result
        assert "**Longsword**" in result
        assert "on ground/table" in result
        assert "### Objects in Play" in result

    def test_build_scene_state_empty(self):
        result = ContextAssembler._build_scene_state_section({})
        assert result is None

    def test_build_scene_state_spatial(self):
        scene_state = {
            "spatial_notes": "The bar runs along the north wall. The pit is in the center.",
        }
        result = ContextAssembler._build_scene_state_section(scene_state)
        assert result is not None
        assert "### Layout" in result
        assert "bar runs along the north wall" in result
