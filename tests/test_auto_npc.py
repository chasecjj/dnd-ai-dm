"""Tests for auto-NPC creation and vault normalization features."""

import os
import tempfile
import unittest

from tools.models import NPC
from models.characters import NPCModel
from models.chronicler_output import NewNPC, NPCUpdate, ChroniclerOutput
from tools.vault_manager import VaultManager, parse_frontmatter, build_frontmatter


class TestNPCModelUpdates(unittest.TestCase):
    """Phase 1: Verify model changes."""

    def test_npc_status_validation(self):
        """NPC status field accepts valid values and rejects invalid."""
        npc = NPC(name="Test", status="alive")
        self.assertEqual(npc.status, "alive")

        npc = NPC(name="Test", status="Dead")
        self.assertEqual(npc.status, "dead")  # Lowercased

        npc = NPC(name="Test", status="missing")
        self.assertEqual(npc.status, "missing")

        npc = NPC(name="Test", status="INVALID")
        self.assertEqual(npc.status, "alive")  # Falls back to alive

    def test_npc_no_alive_field(self):
        """NPC model no longer has an 'alive' boolean field."""
        npc = NPC(name="Test")
        self.assertFalse(hasattr(npc, "alive") and "alive" in npc.model_fields)

    def test_npc_new_fields(self):
        """NPC model has first_seen_session and auto_generated."""
        npc = NPC(name="Test")
        self.assertIsNone(npc.first_seen_session)
        self.assertFalse(npc.auto_generated)

        npc = NPC(name="Test", first_seen_session=3, auto_generated=True)
        self.assertEqual(npc.first_seen_session, 3)
        self.assertTrue(npc.auto_generated)

    def test_npc_role_no_alias(self):
        """NPC role field works without 'class' alias."""
        npc = NPC(name="Test", role="Blacksmith")
        self.assertEqual(npc.role, "Blacksmith")

    def test_npcmodel_status_validation(self):
        """NPCModel (MongoDB) status field validates correctly."""
        npc = NPCModel(name="Test", status="dead")
        self.assertEqual(npc.status, "dead")

        npc = NPCModel(name="Test", status="GARBAGE")
        self.assertEqual(npc.status, "alive")

    def test_npcmodel_new_fields(self):
        """NPCModel has first_seen_session, auto_generated, status."""
        npc = NPCModel(name="Test")
        self.assertEqual(npc.status, "alive")
        self.assertIsNone(npc.first_seen_session)
        self.assertFalse(npc.auto_generated)


class TestNewNPCModel(unittest.TestCase):
    """Phase 1: Verify NewNPC model for auto-creation."""

    def test_new_npc_defaults(self):
        """NewNPC has sensible defaults."""
        npc = NewNPC(name="Bartender Bob")
        self.assertEqual(npc.race, "Unknown")
        self.assertEqual(npc.role, "Commoner")
        self.assertEqual(npc.disposition, "neutral")
        self.assertEqual(npc.description, "")
        self.assertEqual(npc.personality, "")

    def test_new_npc_disposition_validation(self):
        """NewNPC disposition is validated."""
        npc = NewNPC(name="Test", disposition="HOSTILE")
        self.assertEqual(npc.disposition, "hostile")

        npc = NewNPC(name="Test", disposition="invalid_value")
        self.assertEqual(npc.disposition, "neutral")

    def test_new_npc_in_chronicler_output(self):
        """ChroniclerOutput accepts new_npcs field."""
        output = ChroniclerOutput(
            new_npcs=[
                NewNPC(
                    name="Mysterious Stranger",
                    race="Elf",
                    role="Merchant",
                    location="Yawning Portal",
                    description="Tall, hooded figure.",
                    personality="Cryptic and cautious.",
                )
            ]
        )
        self.assertEqual(len(output.new_npcs), 1)
        self.assertEqual(output.new_npcs[0].name, "Mysterious Stranger")

    def test_chronicler_output_empty_new_npcs(self):
        """ChroniclerOutput works with empty new_npcs (default)."""
        output = ChroniclerOutput()
        self.assertEqual(output.new_npcs, [])

    def test_chronicler_output_json_roundtrip(self):
        """ChroniclerOutput with new_npcs survives JSON roundtrip."""
        data = {
            "events": [],
            "new_npcs": [
                {"name": "Bob", "race": "Human", "role": "Guard"}
            ],
        }
        import json
        output = ChroniclerOutput.model_validate_json(json.dumps(data))
        self.assertEqual(len(output.new_npcs), 1)
        self.assertEqual(output.new_npcs[0].name, "Bob")


class TestNPCUpdateStatus(unittest.TestCase):
    """Phase 1: NPCUpdate uses status instead of alive."""

    def test_npc_update_status_field(self):
        """NPCUpdate has status string, not alive bool."""
        update = NPCUpdate(name="Durnan", status="dead")
        self.assertEqual(update.status, "dead")

    def test_npc_update_status_validation(self):
        """NPCUpdate status is validated."""
        update = NPCUpdate(name="Durnan", status="MISSING")
        self.assertEqual(update.status, "missing")

        update = NPCUpdate(name="Durnan", status="garbage")
        self.assertEqual(update.status, "alive")

    def test_npc_update_status_none_allowed(self):
        """NPCUpdate status can be None (not changed)."""
        update = NPCUpdate(name="Durnan")
        self.assertIsNone(update.status)


class TestCreateNPCFile(unittest.TestCase):
    """Phase 2: Verify VaultManager.create_npc_file()."""

    def setUp(self):
        """Create a temporary vault for testing."""
        self.temp_dir = tempfile.mkdtemp()
        self.vault = VaultManager(self.temp_dir)
        # Create NPC directory
        os.makedirs(os.path.join(self.temp_dir, "02 - NPCs"))

    def tearDown(self):
        """Clean up temp directory."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_create_npc_basic(self):
        """Create an NPC file with basic data."""
        npc_data = {
            "name": "Tavern Bob",
            "race": "Human",
            "role": "Barkeeper",
            "location": "Yawning Portal",
            "description": "A stout man with a thick mustache.",
            "personality": "Jovial but shrewd.",
        }
        result = self.vault.create_npc_file(npc_data, session_number=3)
        self.assertTrue(result)

        # Verify file was created
        filepath = os.path.join(self.temp_dir, "02 - NPCs", "Tavern Bob.md")
        self.assertTrue(os.path.exists(filepath))

        # Verify content
        fm, body = self.vault.read_file("02 - NPCs/Tavern Bob.md")
        self.assertEqual(fm["name"], "Tavern Bob")
        self.assertEqual(fm["type"], "npc")
        self.assertEqual(fm["role"], "Barkeeper")
        self.assertEqual(fm["status"], "alive")
        self.assertTrue(fm["auto_generated"])
        self.assertEqual(fm["first_seen_session"], 3)
        self.assertEqual(fm["last_seen_session"], 3)
        self.assertIn("# Tavern Bob", body)
        self.assertIn("A stout man with a thick mustache.", body)

    def test_create_npc_deduplication(self):
        """Creating an NPC that already exists returns False."""
        npc_data = {"name": "Existing NPC", "race": "Elf"}
        # Create first
        self.vault.create_npc_file(npc_data, session_number=1)
        # Try to create again
        result = self.vault.create_npc_file(npc_data, session_number=2)
        self.assertFalse(result)

    def test_create_npc_empty_name_rejected(self):
        """NPC with empty name is rejected."""
        result = self.vault.create_npc_file({"name": ""}, session_number=1)
        self.assertFalse(result)

        result = self.vault.create_npc_file({"name": "   "}, session_number=1)
        self.assertFalse(result)

    def test_create_npc_canonical_sections(self):
        """Created NPC has all canonical body sections."""
        self.vault.create_npc_file({"name": "Section Test"}, session_number=1)
        fm, body = self.vault.read_file("02 - NPCs/Section Test.md")

        expected_sections = [
            "# Section Test",
            "## Description",
            "## Personality",
            "## Background",
            "## Secret",
            "## Connections",
            "## Party Relationship",
            "## Plot Hooks",
            "## DM Notes",
        ]
        for section in expected_sections:
            self.assertIn(section, body, f"Missing section: {section}")

    def test_create_npc_disposition_validated(self):
        """Invalid disposition is normalized to 'neutral'."""
        self.vault.create_npc_file(
            {"name": "Bad Disposition", "disposition": "angry"},
            session_number=1,
        )
        fm, _ = self.vault.read_file("02 - NPCs/Bad Disposition.md")
        self.assertEqual(fm["disposition"], "neutral")


class TestSessionUpdateConsolidation(unittest.TestCase):
    """Phase 5: Verify duplicate session heading merging."""

    def test_merge_duplicate_session_updates(self):
        """Duplicate ### Session N Update headings are merged."""
        from scripts.normalize_vault import _merge_duplicate_session_updates

        body = """## DM Notes
Some notes.

### Session 0 Update
First observation.

### Session 0 Update
Second observation.

### Session 0 Update
Third observation.

### Session 2 Update
Later note."""

        new_body, changes = _merge_duplicate_session_updates(body)

        # Should have merged Session 0 duplicates
        self.assertEqual(new_body.count("### Session 0 Update"), 1)
        self.assertEqual(new_body.count("### Session 2 Update"), 1)

        # All content preserved as bullets
        self.assertIn("- First observation.", new_body)
        self.assertIn("- Second observation.", new_body)
        self.assertIn("- Third observation.", new_body)
        self.assertIn("- Later note.", new_body)

        # Changes logged
        self.assertTrue(any("Merged duplicate" in c for c in changes))


if __name__ == "__main__":
    unittest.main()
