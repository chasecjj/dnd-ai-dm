"""
Tests for tools/character_sync.py — field mapping, body generation, sync roundtrip.

Uses unittest with AsyncMock for async Foundry/vault interactions.
"""

import unittest
from unittest.mock import AsyncMock, MagicMock, patch

from tools.character_sync import (
    build_frontmatter_from_stat_block,
    build_vault_body_from_stat_block,
    _extract_conditions_from_foundry,
    _extract_class_info,
    _extract_level,
    _ordinal,
    register_character,
    sync_foundry_to_local,
    push_changes_to_foundry,
)


# ---------------------------------------------------------------------------
# Sample data
# ---------------------------------------------------------------------------

SAMPLE_STAT_BLOCK = {
    "name": "Frognar Emberheart",
    "type": "character",
    "img": "tokens/frognar.png",
    "uuid": "Actor.abc123def456",
    "abilities": {
        "str": {"value": 16, "mod": 3},
        "dex": {"value": 12, "mod": 1},
        "con": {"value": 14, "mod": 2},
        "int": {"value": 10, "mod": 0},
        "wis": {"value": 8, "mod": -1},
        "cha": {"value": 14, "mod": 2},
    },
    "hp": {"current": 28, "max": 28, "formula": "3d10+6"},
    "ac": 16,
    "movement": {"walk": 25},
    "senses": {"darkvision": 60},
    "details": {"level": 3, "race": "Dwarf"},
    "spells": [
        {"name": "Searing Smite", "level": 1},
        {"name": "Heroism", "level": 1},
    ],
    "features": ["Divine Sense", "Lay on Hands"],
    "equipment": ["Chain Mail", "Shield", "Longsword"],
    "cr": 3,
}

SAMPLE_RAW_ENTITY = {
    "data": {
        "name": "Frognar Emberheart",
        "system": {
            "attributes": {
                "hp": {"value": 25, "max": 28},
            },
        },
        "effects": [
            {"name": "Poisoned", "disabled": False},
            {"name": "Blessed", "disabled": True},  # Disabled — should be excluded
        ],
    }
}

SAMPLE_RAW_ENTITY_NO_CONDITIONS = {
    "data": {
        "name": "Kallisar",
        "system": {
            "attributes": {
                "hp": {"value": 18, "max": 18},
            },
        },
        "effects": [],
    }
}


# ---------------------------------------------------------------------------
# Unit tests
# ---------------------------------------------------------------------------

class TestFieldMapping(unittest.TestCase):
    """Test build_frontmatter_from_stat_block()."""

    def test_basic_mapping(self):
        fm = build_frontmatter_from_stat_block(SAMPLE_STAT_BLOCK, [], "ember0100")
        self.assertEqual(fm["name"], "Frognar Emberheart")
        self.assertEqual(fm["hp_current"], 28)
        self.assertEqual(fm["hp_max"], 28)
        self.assertEqual(fm["ac"], 16)
        self.assertEqual(fm["level"], 3)
        self.assertEqual(fm["foundry_uuid"], "Actor.abc123def456")
        self.assertEqual(fm["player"], "ember0100")
        self.assertEqual(fm["type"], "party_member")
        self.assertIn("party", fm["tags"])

    def test_conditions_included(self):
        fm = build_frontmatter_from_stat_block(
            SAMPLE_STAT_BLOCK, ["Poisoned", "Stunned"], None
        )
        self.assertEqual(fm["conditions"], ["Poisoned", "Stunned"])
        self.assertNotIn("player", fm)  # No player when None

    def test_spell_slot_count(self):
        fm = build_frontmatter_from_stat_block(SAMPLE_STAT_BLOCK, [], None)
        # 2 non-cantrip spells
        self.assertEqual(fm["spell_slots_max"], 2)


class TestBodyGeneration(unittest.TestCase):
    """Test build_vault_body_from_stat_block()."""

    def test_produces_markdown(self):
        body = build_vault_body_from_stat_block(SAMPLE_STAT_BLOCK)
        self.assertIn("# Frognar Emberheart", body)
        self.assertIn("## Stats", body)
        self.assertIn("| STR", body)
        self.assertIn("## Abilities & Features", body)
        self.assertIn("Divine Sense", body)
        self.assertIn("## Prepared Spells", body)
        self.assertIn("Searing Smite", body)
        self.assertIn("## Inventory", body)
        self.assertIn("Chain Mail", body)
        self.assertIn("## Personality", body)
        self.assertIn("## Bonds & Hooks", body)

    def test_empty_lists(self):
        minimal = {
            "name": "Empty",
            "abilities": {},
            "spells": [],
            "features": [],
            "equipment": [],
        }
        body = build_vault_body_from_stat_block(minimal)
        self.assertIn("# Empty", body)
        # Should NOT have feature/spell/equipment sections
        self.assertNotIn("## Abilities & Features", body)
        self.assertNotIn("## Prepared Spells", body)
        self.assertNotIn("## Inventory", body)


class TestConditionExtraction(unittest.TestCase):
    """Test _extract_conditions_from_foundry()."""

    def test_extracts_active_conditions(self):
        conditions = _extract_conditions_from_foundry(SAMPLE_RAW_ENTITY)
        self.assertEqual(conditions, ["Poisoned"])  # Blessed is disabled

    def test_no_conditions(self):
        conditions = _extract_conditions_from_foundry(SAMPLE_RAW_ENTITY_NO_CONDITIONS)
        self.assertEqual(conditions, [])

    def test_empty_entity(self):
        conditions = _extract_conditions_from_foundry({})
        self.assertEqual(conditions, [])

    def test_multiple_active(self):
        entity = {
            "data": {
                "effects": [
                    {"name": "Stunned", "disabled": False},
                    {"name": "Poisoned", "disabled": False},
                ]
            }
        }
        conditions = _extract_conditions_from_foundry(entity)
        self.assertEqual(conditions, ["Poisoned", "Stunned"])  # Sorted


class TestHelpers(unittest.TestCase):
    """Test misc helper functions."""

    def test_extract_class_info_character(self):
        stat = {"type": "character", "details": {}, "cr": "?"}
        self.assertEqual(_extract_class_info(stat), "Adventurer")

    def test_extract_class_info_npc(self):
        stat = {"type": "npc", "details": {}, "cr": 5}
        self.assertEqual(_extract_class_info(stat), "CR 5")

    def test_extract_level_from_details(self):
        stat = {"details": {"level": 5}, "cr": 1}
        self.assertEqual(_extract_level(stat), 5)

    def test_extract_level_fallback_cr(self):
        stat = {"details": {}, "cr": 7}
        self.assertEqual(_extract_level(stat), 7)

    def test_ordinal(self):
        self.assertEqual(_ordinal(1), "1st")
        self.assertEqual(_ordinal(2), "2nd")
        self.assertEqual(_ordinal(3), "3rd")
        self.assertEqual(_ordinal(4), "4th")
        self.assertEqual(_ordinal(11), "11th")
        self.assertEqual(_ordinal(21), "21st")


# ---------------------------------------------------------------------------
# Async integration tests (with mocks)
# ---------------------------------------------------------------------------

class TestRegisterCharacter(unittest.IsolatedAsyncioTestCase):
    """Test register_character() with mocked Foundry/vault."""

    async def test_successful_registration(self):
        foundry = AsyncMock()
        foundry.search_actors.return_value = [
            {"name": "Frognar Emberheart", "uuid": "Actor.abc123"}
        ]
        foundry.get_actor_stat_block.return_value = SAMPLE_STAT_BLOCK
        foundry.get_entity.return_value = SAMPLE_RAW_ENTITY

        vault = MagicMock()
        vault.write_file.return_value = True

        state_mgr = AsyncMock()
        state_mgr.upsert_character.return_value = True

        result = await register_character(
            "Frognar Emberheart", foundry, vault, state_mgr, "ember0100"
        )

        self.assertTrue(result["success"])
        self.assertEqual(result["data"]["name"], "Frognar Emberheart")
        self.assertEqual(result["data"]["hp_current"], 28)
        vault.write_file.assert_called_once()
        state_mgr.upsert_character.assert_called_once()

    async def test_no_actor_found(self):
        foundry = AsyncMock()
        foundry.search_actors.return_value = []

        result = await register_character("Nobody", foundry, MagicMock())
        self.assertFalse(result["success"])
        self.assertIn("No actor found", result["message"])

    async def test_no_state_manager(self):
        """Registration works without MongoDB."""
        foundry = AsyncMock()
        foundry.search_actors.return_value = [
            {"name": "Test", "uuid": "Actor.xyz"}
        ]
        foundry.get_actor_stat_block.return_value = SAMPLE_STAT_BLOCK
        foundry.get_entity.return_value = SAMPLE_RAW_ENTITY_NO_CONDITIONS

        vault = MagicMock()
        vault.write_file.return_value = True

        result = await register_character("Test", foundry, vault, None)
        self.assertTrue(result["success"])


class TestSyncFoundryToLocal(unittest.IsolatedAsyncioTestCase):
    """Test sync_foundry_to_local() with mocked data."""

    async def test_detects_hp_change(self):
        foundry = AsyncMock()
        foundry.get_entity.return_value = SAMPLE_RAW_ENTITY  # HP=25

        vault = MagicMock()
        vault.get_party_state.return_value = [
            {
                "frontmatter": {
                    "name": "Frognar Emberheart",
                    "foundry_uuid": "Actor.abc123",
                    "hp_current": 28,  # Vault has 28, Foundry has 25
                    "conditions": [],
                },
                "file": "01 - Party/Frognar Emberheart.md",
                "summary": "",
            }
        ]
        vault.update_party_member.return_value = True

        changes = await sync_foundry_to_local(foundry, vault)

        self.assertEqual(len(changes), 2)  # HP + conditions (Poisoned added)
        hp_change = next(c for c in changes if c["field"] == "hp_current")
        self.assertEqual(hp_change["old"], 28)
        self.assertEqual(hp_change["new"], 25)

    async def test_no_changes_when_in_sync(self):
        foundry = AsyncMock()
        foundry.get_entity.return_value = SAMPLE_RAW_ENTITY_NO_CONDITIONS  # HP=18

        vault = MagicMock()
        vault.get_party_state.return_value = [
            {
                "frontmatter": {
                    "name": "Kallisar",
                    "foundry_uuid": "Actor.xyz",
                    "hp_current": 18,
                    "conditions": [],
                },
                "file": "01 - Party/Kallisar.md",
                "summary": "",
            }
        ]

        changes = await sync_foundry_to_local(foundry, vault)
        self.assertEqual(len(changes), 0)

    async def test_skips_unlinked_characters(self):
        foundry = AsyncMock()
        vault = MagicMock()
        vault.get_party_state.return_value = [
            {
                "frontmatter": {
                    "name": "Unlinked",
                    "hp_current": 10,
                    "conditions": [],
                    # No foundry_uuid
                },
                "file": "01 - Party/Unlinked.md",
                "summary": "",
            }
        ]

        changes = await sync_foundry_to_local(foundry, vault)
        self.assertEqual(len(changes), 0)
        foundry.get_entity.assert_not_called()


class TestPushChangesToFoundry(unittest.IsolatedAsyncioTestCase):
    """Test push_changes_to_foundry() with mocked Foundry."""

    async def test_pushes_hp_delta(self):
        foundry = AsyncMock()
        # Current Foundry HP is 28, we want to push 20 (delta = -8)
        foundry.get_entity.return_value = {
            "data": {"system": {"attributes": {"hp": {"value": 28}}}}
        }
        foundry.modify_hp.return_value = {"success": True}

        vault = MagicMock()
        vault.get_party_state.return_value = [
            {
                "frontmatter": {
                    "name": "Frognar Emberheart",
                    "foundry_uuid": "Actor.abc123",
                },
                "file": "01 - Party/Frognar.md",
                "summary": "",
            }
        ]

        results = await push_changes_to_foundry(
            [{"name": "Frognar Emberheart", "hp_current": 20}],
            vault, foundry,
        )

        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["pushed"])
        foundry.modify_hp.assert_called_once_with("Actor.abc123", 8, increase=False)

    async def test_no_push_when_hp_matches(self):
        foundry = AsyncMock()
        foundry.get_entity.return_value = {
            "data": {"system": {"attributes": {"hp": {"value": 20}}}}
        }

        vault = MagicMock()
        vault.get_party_state.return_value = [
            {
                "frontmatter": {
                    "name": "Test",
                    "foundry_uuid": "Actor.xyz",
                },
                "file": "01 - Party/Test.md",
                "summary": "",
            }
        ]

        results = await push_changes_to_foundry(
            [{"name": "Test", "hp_current": 20}],
            vault, foundry,
        )
        self.assertEqual(len(results), 0)
        foundry.modify_hp.assert_not_called()

    async def test_error_returns_dict_not_raises(self):
        foundry = AsyncMock()
        foundry.get_entity.side_effect = Exception("Connection lost")

        vault = MagicMock()
        vault.get_party_state.return_value = [
            {
                "frontmatter": {
                    "name": "Frognar",
                    "foundry_uuid": "Actor.abc",
                },
                "file": "01 - Party/Frognar.md",
                "summary": "",
            }
        ]

        # Should NOT raise — returns error dict
        results = await push_changes_to_foundry(
            [{"name": "Frognar", "hp_current": 10}],
            vault, foundry,
        )
        self.assertEqual(len(results), 1)
        self.assertIn("error", results[0])

    async def test_skips_unlinked_characters(self):
        foundry = AsyncMock()
        vault = MagicMock()
        vault.get_party_state.return_value = [
            {
                "frontmatter": {"name": "Unlinked"},
                "file": "01 - Party/Unlinked.md",
                "summary": "",
            }
        ]

        results = await push_changes_to_foundry(
            [{"name": "Unlinked", "hp_current": 5}],
            vault, foundry,
        )
        self.assertEqual(len(results), 0)


if __name__ == "__main__":
    unittest.main()
