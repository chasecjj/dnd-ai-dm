import unittest
from tools.models import PartyMember, NPC, Quest

class TestVaultModels(unittest.TestCase):
    def test_party_member_validation(self):
        # Valid data
        data = {
            "name": "TestChar",
            "hp_current": 10,
            "hp_max": 20,
            "ac": 15,
            "class": "Fighter",
            "level": 3
        }
        pm = PartyMember(**data)
        self.assertEqual(pm.name, "TestChar")
        self.assertEqual(pm.hp_current, 10)
        
        # Invalid data (missing required field)
        with self.assertRaises(ValueError):
            PartyMember(name="Incomplete")

        # Extra fields allowed
        data["extra_stuff"] = "cool"
        pm = PartyMember(**data)
        self.assertEqual(pm.extra_stuff, "cool")

    def test_npc_validation(self):
        # Disposition normalization
        npc = NPC(name="Bob", disposition="FRIENDLY")
        self.assertEqual(npc.disposition, "friendly")
        
        npc = NPC(name="Bob", disposition="Angry") # Invalid -> neutral
        self.assertEqual(npc.disposition, "neutral")

if __name__ == "__main__":
    unittest.main()
