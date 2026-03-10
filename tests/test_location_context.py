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
