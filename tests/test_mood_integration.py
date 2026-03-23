# tests/test_mood_integration.py
"""Integration test: mood node produces valid output consumed by downstream."""
import pytest
from unittest.mock import AsyncMock, MagicMock
from models.mood_assessment import MoodAssessment
from pipeline.nodes.mood_node import mood_node


class TestMoodIntegration:
    @pytest.mark.asyncio
    async def test_mood_output_compatible_with_ws_handler(self):
        """Verify mood node output can be consumed by WebSocket handler logic."""
        mock_agent = MagicMock()
        mock_agent.assess = AsyncMock(return_value=MoodAssessment(
            primary_mood="horror",
            intensity=8,
            secondary_mood="tension",
            npc_emotional_states={"Shadow": "hungry, patient"},
            environmental_tone="wet stone, distant scratching",
            typography_hint="horror",
            breath_timing="slow",
        ))

        state = {
            "player_input": "I peek around the corner",
            "message_type": "game_action",
            "current_location": "The Undercrypt",
        }

        result = await mood_node(state, mood_agent=mock_agent)

        # WebSocket handler reads these
        mood = result.get("mood", "neutral")
        mood_assessment = result.get("mood_assessment", {})
        breath_timing = mood_assessment.get("breath_timing", "neutral")

        assert mood == "horror"
        assert breath_timing == "slow"
        assert mood_assessment["npc_emotional_states"]["Shadow"] == "hungry, patient"

    @pytest.mark.asyncio
    async def test_mood_output_keys_compatible_with_gamestate(self):
        """Verify mood node returns only valid GameState keys."""
        mock_agent = MagicMock()
        mock_agent.assess = AsyncMock(return_value=MoodAssessment(
            primary_mood="warmth",
            intensity=4,
            environmental_tone="hearth fire",
        ))

        state = {"player_input": "sit down", "message_type": "game_action"}
        result = await mood_node(state, mood_agent=mock_agent)

        # Only GameState-compatible keys
        assert set(result.keys()) == {"mood", "mood_assessment"}
        assert isinstance(result["mood"], str)
        assert isinstance(result["mood_assessment"], dict)
