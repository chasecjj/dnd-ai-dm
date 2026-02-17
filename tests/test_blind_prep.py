"""
Smoke tests for the blind prep pipeline (tools/blind_prep.py).

Tests use mock AI clients and mock agents — no live Gemini or Foundry connection needed.
"""

import sys
import os
import json
import asyncio
import unittest
from unittest.mock import AsyncMock, MagicMock, patch
from dataclasses import dataclass

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ---------------------------------------------------------------------------
# Mock Helpers
# ---------------------------------------------------------------------------

class MockGeminiResponse:
    """Simulates a Gemini response with .text property."""
    def __init__(self, text: str):
        self.text = text


class MockGeminiClient:
    """Mock Gemini client that returns canned responses."""
    def __init__(self, responses=None):
        self._responses = responses or []
        self._call_count = 0

    @property
    def aio(self):
        return self

    @property
    def models(self):
        return self

    async def generate_content(self, **kwargs):
        if self._call_count < len(self._responses):
            resp = self._responses[self._call_count]
        else:
            resp = '{"scenarios": []}'
        self._call_count += 1
        return MockGeminiResponse(resp)


class MockVault:
    """Mock VaultManager."""
    def __init__(self):
        self._files = {}

    def list_files(self, subfolder):
        return self._files.get(subfolder, [])

    def read_file(self, path):
        return self._files.get(f"_data_{path}", None)

    def write_file(self, path, frontmatter, body):
        self._files[f"_data_{path}"] = (frontmatter, body)
        return True


class MockContextAssembler:
    """Mock context assembler."""
    def build_campaign_planner_context(self):
        return "## Test Campaign Context\nParty is in Waterdeep. Active quest: Find the stolen gem."

    def build_world_architect_context(self):
        return "## Test World Context\nWaterdeep, City of Splendors."


class MockCampaignPlanner:
    """Mock CampaignPlannerAgent."""
    def __init__(self):
        self.context = MockContextAssembler()

    async def plan_session(self, notes):
        return "Session plan: Investigate the warehouse."


class MockWorldArchitect:
    """Mock WorldArchitectAgent."""
    def __init__(self):
        self._created_locations = []
        self._created_npcs = []

    async def create_location(self, description):
        self._created_locations.append(description)
        return f"✅ Location created: {description[:50]}"

    async def create_npc(self, description):
        self._created_npcs.append(description)
        return f"✅ NPC created: {description[:50]}"


class MockFoundryArchitect:
    """Mock FoundryArchitectAgent."""
    def __init__(self):
        self._requests = []

    async def process_request(self, request):
        self._requests.append(request)
        return f"Architect processed: {request[:50]}"


class MockFoundryClient:
    """Mock FoundryClient."""
    def __init__(self, connected=True):
        self._connected = connected

    @property
    def is_connected(self):
        return self._connected

    def search_scenes(self, query):
        return []  # No existing scenes

    def search_actors(self, query):
        return []


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestBlindPrepImports(unittest.TestCase):
    """Test that the blind prep module imports correctly."""

    def test_import_module(self):
        from tools.blind_prep import run_blind_prep, BlindPrepResult
        self.assertTrue(callable(run_blind_prep))

    def test_result_dataclass(self):
        from tools.blind_prep import BlindPrepResult
        result = BlindPrepResult()
        self.assertEqual(result.summary, "")
        self.assertEqual(result.details, "")
        self.assertEqual(result.scenes_created, 0)
        self.assertEqual(result.npcs_created, 0)
        self.assertEqual(result.locations_created, 0)
        self.assertEqual(result.encounters_staged, 0)
        self.assertIsInstance(result.errors, list)

    def test_result_dataclass_custom_values(self):
        from tools.blind_prep import BlindPrepResult
        result = BlindPrepResult(
            summary="Test summary",
            details="Test details",
            scenes_created=2,
            npcs_created=3,
            locations_created=1,
            encounters_staged=1,
            errors=["some error"]
        )
        self.assertEqual(result.summary, "Test summary")
        self.assertEqual(result.scenes_created, 2)
        self.assertEqual(len(result.errors), 1)


class TestBlindPrepHelpers(unittest.TestCase):
    """Test helper functions."""

    def test_get_existing_location_names_empty(self):
        from tools.blind_prep import _get_existing_location_names
        vault = MockVault()
        names = _get_existing_location_names(vault)
        self.assertIsInstance(names, set)
        self.assertEqual(len(names), 0)

    def test_get_existing_npc_names_empty(self):
        from tools.blind_prep import _get_existing_npc_names
        vault = MockVault()
        names = _get_existing_npc_names(vault)
        self.assertIsInstance(names, set)
        self.assertEqual(len(names), 0)

    def test_get_existing_location_names_with_data(self):
        from tools.blind_prep import _get_existing_location_names
        vault = MockVault()
        vault._files["03 - Locations"] = ["Tavern.md", "Forest.md"]
        vault._files["_data_Tavern.md"] = ({"name": "The Yawning Portal"}, "body")
        vault._files["_data_Forest.md"] = ({"name": "Ardeep Forest"}, "body")
        names = _get_existing_location_names(vault)
        self.assertIn("the yawning portal", names)
        self.assertIn("ardeep forest", names)

    def test_get_existing_npc_names_with_data(self):
        from tools.blind_prep import _get_existing_npc_names
        vault = MockVault()
        vault._files["02 - NPCs"] = ["Durnan.md"]
        vault._files["_data_Durnan.md"] = ({"name": "Durnan"}, "body")
        names = _get_existing_npc_names(vault)
        self.assertIn("durnan", names)


class TestBlindPrepPipeline(unittest.TestCase):
    """Test the full blind prep pipeline with mocked agents."""

    def _run(self, coro):
        """Helper to run async tests."""
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch('tools.blind_prep.gemini_limiter')
    def test_pipeline_with_valid_scenarios(self, mock_limiter):
        """Test that the pipeline creates locations, NPCs, and stages encounters."""
        mock_limiter.acquire = AsyncMock()

        from tools.blind_prep import run_blind_prep

        # Mock Gemini client that returns a valid scenario plan
        scenario_json = json.dumps({
            "session_overview": "Investigate the Zhentarim warehouse",
            "scenarios": [
                {
                    "name": "Direct Assault",
                    "likelihood": "high",
                    "locations_needed": [
                        {
                            "name": "Zhentarim Warehouse",
                            "type": "warehouse",
                            "description": "A dimly lit warehouse on the docks",
                            "lighting": "dim",
                            "grid_size": "30x20"
                        }
                    ],
                    "npcs_needed": [
                        {
                            "name": "Dock Guard Captain",
                            "description": "A gruff human guard captain"
                        }
                    ],
                    "monsters_needed": [
                        {"name": "Bandit", "quantity": 3, "cr": "1/8"},
                        {"name": "Bandit Captain", "quantity": 1, "cr": "2"}
                    ],
                    "encounter_description": "Guard patrol at the warehouse entrance"
                }
            ]
        })

        mock_client = MockGeminiClient(responses=[scenario_json])
        mock_planner = MockCampaignPlanner()
        mock_architect_world = MockWorldArchitect()
        mock_architect_foundry = MockFoundryArchitect()
        mock_foundry = MockFoundryClient(connected=True)
        mock_vault = MockVault()

        result = self._run(run_blind_prep(
            description="Investigate the Zhentarim warehouse",
            campaign_planner=mock_planner,
            world_architect=mock_architect_world,
            foundry_architect=mock_architect_foundry,
            cartographer=None,  # No cartographer
            foundry_client=mock_foundry,
            gemini_client=mock_client,
            model_id="gemini-2.0-flash",
            vault=mock_vault,
        ))

        # Verify results
        self.assertIn("Preparation complete", result.summary)
        self.assertGreaterEqual(result.locations_created, 1)
        self.assertGreaterEqual(result.npcs_created, 1)
        self.assertGreaterEqual(result.encounters_staged, 1)
        self.assertIn("BLIND PREP SESSION", result.details)

        # Verify agents were called
        self.assertEqual(len(mock_architect_world._created_locations), 1)
        self.assertEqual(len(mock_architect_world._created_npcs), 1)
        self.assertEqual(len(mock_architect_foundry._requests), 1)

    @patch('tools.blind_prep.gemini_limiter')
    def test_pipeline_with_empty_scenarios(self, mock_limiter):
        """Test graceful handling when no scenarios are generated."""
        mock_limiter.acquire = AsyncMock()

        from tools.blind_prep import run_blind_prep

        mock_client = MockGeminiClient(responses=['{"scenarios": []}'])
        mock_planner = MockCampaignPlanner()

        result = self._run(run_blind_prep(
            description="Something vague",
            campaign_planner=mock_planner,
            world_architect=MockWorldArchitect(),
            foundry_architect=MockFoundryArchitect(),
            cartographer=None,
            foundry_client=MockFoundryClient(),
            gemini_client=mock_client,
            model_id="gemini-2.0-flash",
            vault=MockVault(),
        ))

        # With empty scenarios, should still succeed but with zero assets
        self.assertEqual(result.locations_created, 0)
        self.assertEqual(result.npcs_created, 0)

    @patch('tools.blind_prep.gemini_limiter')
    def test_pipeline_with_invalid_json(self, mock_limiter):
        """Test graceful handling when AI returns invalid JSON."""
        mock_limiter.acquire = AsyncMock()

        from tools.blind_prep import run_blind_prep

        mock_client = MockGeminiClient(responses=['not valid json at all'])
        mock_planner = MockCampaignPlanner()

        result = self._run(run_blind_prep(
            description="Something",
            campaign_planner=mock_planner,
            world_architect=MockWorldArchitect(),
            foundry_architect=MockFoundryArchitect(),
            cartographer=None,
            foundry_client=MockFoundryClient(),
            gemini_client=mock_client,
            model_id="gemini-2.0-flash",
            vault=MockVault(),
        ))

        # Should fail gracefully
        self.assertIn("Could not generate", result.summary)

    @patch('tools.blind_prep.gemini_limiter')
    def test_pipeline_skips_existing_locations(self, mock_limiter):
        """Test that existing vault locations are not re-created."""
        mock_limiter.acquire = AsyncMock()

        from tools.blind_prep import run_blind_prep

        scenario_json = json.dumps({
            "session_overview": "Test",
            "scenarios": [{
                "name": "Test Scenario",
                "likelihood": "high",
                "locations_needed": [
                    {"name": "The Yawning Portal", "type": "tavern",
                     "description": "A tavern", "lighting": "bright", "grid_size": "20x20"}
                ],
                "npcs_needed": [],
                "monsters_needed": [],
                "encounter_description": ""
            }]
        })

        mock_client = MockGeminiClient(responses=[scenario_json])
        mock_vault = MockVault()
        # Pre-populate vault with existing location
        mock_vault._files["03 - Locations"] = ["Tavern.md"]
        mock_vault._files["_data_Tavern.md"] = ({"name": "The Yawning Portal"}, "body")

        mock_architect = MockWorldArchitect()

        result = self._run(run_blind_prep(
            description="Visit the tavern",
            campaign_planner=MockCampaignPlanner(),
            world_architect=mock_architect,
            foundry_architect=MockFoundryArchitect(),
            cartographer=None,
            foundry_client=MockFoundryClient(),
            gemini_client=mock_client,
            model_id="gemini-2.0-flash",
            vault=mock_vault,
        ))

        # Location should NOT be created (already exists)
        self.assertEqual(result.locations_created, 0)
        self.assertEqual(len(mock_architect._created_locations), 0)
        self.assertIn("SKIP", result.details)

    @patch('tools.blind_prep.gemini_limiter')
    def test_pipeline_without_foundry(self, mock_limiter):
        """Test that pipeline works when Foundry is disconnected."""
        mock_limiter.acquire = AsyncMock()

        from tools.blind_prep import run_blind_prep

        scenario_json = json.dumps({
            "session_overview": "Test",
            "scenarios": [{
                "name": "Test",
                "likelihood": "high",
                "locations_needed": [
                    {"name": "New Cave", "type": "cave",
                     "description": "A cave", "lighting": "dark", "grid_size": "20x20"}
                ],
                "npcs_needed": [{"name": "Cave Hermit", "description": "An old hermit"}],
                "monsters_needed": [{"name": "Goblin", "quantity": 2, "cr": "1/4"}],
                "encounter_description": "Goblins in the cave"
            }]
        })

        mock_client = MockGeminiClient(responses=[scenario_json])
        mock_foundry = MockFoundryClient(connected=False)

        result = self._run(run_blind_prep(
            description="Cave adventure",
            campaign_planner=MockCampaignPlanner(),
            world_architect=MockWorldArchitect(),
            foundry_architect=MockFoundryArchitect(),
            cartographer=None,
            foundry_client=mock_foundry,
            gemini_client=mock_client,
            model_id="gemini-2.0-flash",
            vault=MockVault(),
        ))

        # Vault content should still be created
        self.assertGreaterEqual(result.locations_created, 1)
        self.assertGreaterEqual(result.npcs_created, 1)
        # But no encounters staged (Foundry not connected)
        self.assertEqual(result.encounters_staged, 0)
        self.assertIn("Foundry not connected", result.details)

    @patch('tools.blind_prep.gemini_limiter')
    def test_summary_is_spoiler_free(self, mock_limiter):
        """Verify the player-facing summary doesn't contain scenario details."""
        mock_limiter.acquire = AsyncMock()

        from tools.blind_prep import run_blind_prep

        scenario_json = json.dumps({
            "session_overview": "SECRET PLOT TWIST",
            "scenarios": [{
                "name": "The Big Reveal",
                "likelihood": "high",
                "locations_needed": [
                    {"name": "Hidden Lair of Doom", "type": "lair",
                     "description": "A terrifying hidden lair", "lighting": "dark", "grid_size": "30x20"}
                ],
                "npcs_needed": [
                    {"name": "The Betrayer", "description": "An NPC who betrays the party"}
                ],
                "monsters_needed": [],
                "encounter_description": ""
            }]
        })

        mock_client = MockGeminiClient(responses=[scenario_json])

        result = self._run(run_blind_prep(
            description="Next session",
            campaign_planner=MockCampaignPlanner(),
            world_architect=MockWorldArchitect(),
            foundry_architect=MockFoundryArchitect(),
            cartographer=None,
            foundry_client=MockFoundryClient(),
            gemini_client=mock_client,
            model_id="gemini-2.0-flash",
            vault=MockVault(),
        ))

        # Summary should NOT contain spoiler content
        self.assertNotIn("Hidden Lair of Doom", result.summary)
        self.assertNotIn("The Betrayer", result.summary)
        self.assertNotIn("SECRET PLOT TWIST", result.summary)
        self.assertNotIn("Big Reveal", result.summary)

        # Details SHOULD contain spoiler content
        self.assertIn("Hidden Lair of Doom", result.details)
        self.assertIn("The Betrayer", result.details)


class TestBlindPrepDeduplication(unittest.TestCase):
    """Test that duplicate locations/NPCs across scenarios are handled."""

    def _run(self, coro):
        return asyncio.get_event_loop().run_until_complete(coro)

    @patch('tools.blind_prep.gemini_limiter')
    def test_duplicate_locations_across_scenarios(self, mock_limiter):
        """Same location in multiple scenarios should only be created once."""
        mock_limiter.acquire = AsyncMock()

        from tools.blind_prep import run_blind_prep

        scenario_json = json.dumps({
            "session_overview": "Test",
            "scenarios": [
                {
                    "name": "Scenario A",
                    "likelihood": "high",
                    "locations_needed": [
                        {"name": "Town Square", "type": "urban",
                         "description": "A town square", "lighting": "bright", "grid_size": "30x30"}
                    ],
                    "npcs_needed": [],
                    "monsters_needed": [],
                    "encounter_description": ""
                },
                {
                    "name": "Scenario B",
                    "likelihood": "medium",
                    "locations_needed": [
                        {"name": "Town Square", "type": "urban",
                         "description": "The same town square", "lighting": "bright", "grid_size": "30x30"}
                    ],
                    "npcs_needed": [],
                    "monsters_needed": [],
                    "encounter_description": ""
                }
            ]
        })

        mock_client = MockGeminiClient(responses=[scenario_json])
        mock_architect = MockWorldArchitect()

        result = self._run(run_blind_prep(
            description="Town adventure",
            campaign_planner=MockCampaignPlanner(),
            world_architect=mock_architect,
            foundry_architect=MockFoundryArchitect(),
            cartographer=None,
            foundry_client=MockFoundryClient(),
            gemini_client=mock_client,
            model_id="gemini-2.0-flash",
            vault=MockVault(),
        ))

        # Should only create the location once
        self.assertEqual(result.locations_created, 1)
        self.assertEqual(len(mock_architect._created_locations), 1)


if __name__ == '__main__':
    unittest.main()
