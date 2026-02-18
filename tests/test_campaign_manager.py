import os
import shutil
import tempfile
import unittest
from pathlib import Path
from tools.campaign_manager import CampaignManager

class TestCampaignManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.cm = CampaignManager(root_dir=self.test_dir)

    def tearDown(self):
        try:
            # Junctions can be tricky to delete in Python 3.7-, but shutil.rmtree might fail on them
            # if not handled correctly.
            # Best effort cleanup
            if self.cm.vault_link.exists():
                if self.cm._is_junction(self.cm.vault_link):
                    self.cm.vault_link.rmdir() 
            shutil.rmtree(self.test_dir)
        except Exception as e:
            print(f"Cleanup failed: {e}")

    def test_create_and_switch(self):
        # 1. Ensure Migration (should create Default)
        self.cm.ensure_migration()
        self.assertTrue((self.cm.campaigns_dir / "Default").exists())
        self.assertTrue(self.cm.vault_link.exists())
        self.assertEqual(self.cm.get_active_campaign(), "Default")

        # 2. Create New Campaign
        success = self.cm.create_campaign("Strahd")
        self.assertTrue(success)
        self.assertTrue((self.cm.campaigns_dir / "Strahd").exists())
        self.assertTrue((self.cm.campaigns_dir / "Strahd" / "00 - Session Log").exists())

        # 3. Switch to New Campaign
        success = self.cm.set_campaign("Strahd")
        self.assertTrue(success)
        self.assertEqual(self.cm.get_active_campaign(), "Strahd")
        
        # Verify junction points to Strahd
        # Note: os.readlink returns the absolute path payload
        target = os.readlink(str(self.cm.vault_link))
        self.assertTrue(str(self.cm.campaigns_dir / "Strahd") in target or "Strahd" in target)

    def test_list_campaigns(self):
        self.cm.ensure_migration()
        self.cm.create_campaign("CampaignA")
        self.cm.create_campaign("CampaignB")
        
        campaigns = self.cm.list_campaigns()
        self.assertIn("Default", campaigns)
        self.assertIn("CampaignA", campaigns)
        self.assertIn("CampaignB", campaigns)

if __name__ == "__main__":
    unittest.main()
