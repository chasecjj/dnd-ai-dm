import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from pipeline.nodes.mood_node import mood_node
from models.mood_assessment import MoodAssessment


class TestMoodNode:
    @pytest.mark.asyncio
    async def test_mood_node_sets_both_fields(self):
        mock_agent = MagicMock()
        mock_agent.assess = AsyncMock(return_value=MoodAssessment(
            primary_mood="combat",
            intensity=7,
            environmental_tone="steel and fog",
            typography_hint="combat",
            breath_timing="urgent",
        ))

        state = {
            "player_input": "I attack",
            "message_type": "game_action",
            "current_location": "Alley",
            "is_solo": True,
        }

        result = await mood_node(state, mood_agent=mock_agent)

        assert result["mood"] == "combat"
        assert result["mood_assessment"]["primary_mood"] == "combat"
        assert result["mood_assessment"]["intensity"] == 7
        assert result["mood_assessment"]["breath_timing"] == "urgent"

    @pytest.mark.asyncio
    async def test_mood_node_handles_missing_fields(self):
        mock_agent = MagicMock()
        mock_agent.assess = AsyncMock(return_value=MoodAssessment(
            primary_mood="neutral",
            intensity=5,
            environmental_tone="calm",
        ))

        state = {"player_input": "look around", "message_type": "game_action"}

        result = await mood_node(state, mood_agent=mock_agent)

        assert result["mood"] == "neutral"
        assert result["mood_assessment"]["intensity"] == 5
