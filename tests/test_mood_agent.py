import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from agents.mood_agent import MoodAgent, MOOD_AGENT_IDENTITY


class TestMoodAgentInit:
    def test_constructor(self):
        client = MagicMock()
        ctx = MagicMock()
        agent = MoodAgent(client, ctx)
        assert agent.client is client
        assert agent.context is ctx
        assert agent.model_id == "gemini-2.0-flash"

    def test_custom_model(self):
        agent = MoodAgent(MagicMock(), MagicMock(), model_id="gemini-1.5-pro")
        assert agent.model_id == "gemini-1.5-pro"

    def test_system_prompt_exists(self):
        assert len(MOOD_AGENT_IDENTITY) > 100
        assert "mood" in MOOD_AGENT_IDENTITY.lower()


class TestMoodAgentAssess:
    @pytest.fixture
    def agent(self):
        client = MagicMock()
        ctx = MagicMock()
        return MoodAgent(client, ctx)

    @pytest.mark.asyncio
    async def test_assess_returns_mood_assessment(self, agent):
        json_response = '''{
            "primary_mood": "combat",
            "intensity": 7,
            "secondary_mood": "tension",
            "npc_emotional_states": {"Grigor": "panicked"},
            "environmental_tone": "foggy alley, steel clashing",
            "typography_hint": "combat",
            "breath_timing": "urgent"
        }'''
        mock_response = MagicMock()
        mock_response.text = json_response
        agent.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("agents.mood_agent.gemini_limiter") as mock_limiter:
            mock_limiter.acquire = AsyncMock()
            result = await agent.assess(
                player_input="I draw my sword and charge",
                message_type="game_action",
                location="The Gloomdeep Passage",
                time_of_day="night",
                scene_state="Grigor the bugbear blocks the path",
                chaos_factor=6,
                recent_narrative="The fog thickens around you.",
                hp_percent=0.8,
                conditions=[],
            )

        assert result.primary_mood == "combat"
        assert result.intensity == 7
        assert result.breath_timing == "urgent"
        mock_limiter.acquire.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_assess_fallback_on_error(self, agent):
        agent.client.aio.models.generate_content = AsyncMock(
            side_effect=Exception("Gemini API error")
        )

        with patch("agents.mood_agent.gemini_limiter") as mock_limiter:
            mock_limiter.acquire = AsyncMock()
            result = await agent.assess(
                player_input="hello",
                message_type="game_action",
                location="Tavern",
                time_of_day="evening",
                scene_state="",
                chaos_factor=3,
                recent_narrative="",
                hp_percent=1.0,
                conditions=[],
            )

        assert result.primary_mood == "neutral"
        assert result.intensity == 5
        assert result.breath_timing == "neutral"

    @pytest.mark.asyncio
    async def test_assess_fallback_on_invalid_json(self, agent):
        mock_response = MagicMock()
        mock_response.text = "not valid json at all"
        agent.client.aio.models.generate_content = AsyncMock(return_value=mock_response)

        with patch("agents.mood_agent.gemini_limiter") as mock_limiter:
            mock_limiter.acquire = AsyncMock()
            result = await agent.assess(
                player_input="look around",
                message_type="game_action",
                location="Forest",
                time_of_day="dawn",
                scene_state="",
                chaos_factor=2,
                recent_narrative="",
                hp_percent=1.0,
                conditions=[],
            )

        assert result.primary_mood == "neutral"
