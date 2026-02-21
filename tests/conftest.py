"""
Shared pytest fixtures for the D&D AI Dungeon Master test suite.

Consolidates duplicate mock helpers from individual test files.
Existing unittest-based tests keep their own inline mocks for backward compat;
new pytest-style tests should use these fixtures.
"""

import pytest
from unittest.mock import AsyncMock, MagicMock


# ---------------------------------------------------------------------------
# Gemini Mock Helpers (reusable classes)
# ---------------------------------------------------------------------------

class MockGeminiResponse:
    """Simulates a Gemini response with .text property."""

    def __init__(self, text: str):
        self.text = text


class MockGeminiClient:
    """Mock Gemini client that returns canned text responses.

    Usage:
        client = MockGeminiClient(["response1", "response2"])
        resp = await client.aio.models.generate_content(model=..., contents=...)
        assert resp.text == "response1"
    """

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
            resp = '{"error": "no more canned responses"}'
        self._call_count += 1
        if isinstance(resp, str):
            return MockGeminiResponse(resp)
        # Allow passing pre-built response objects
        return resp


# ---------------------------------------------------------------------------
# Pytest fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def mock_vault():
    """MagicMock VaultManager with common method stubs."""
    vault = MagicMock()
    vault.list_files.return_value = []
    vault.read_file.return_value = None
    vault.write_file.return_value = None
    vault.get_party_state.return_value = []
    vault.get_active_quests.return_value = []
    vault.read_world_clock.return_value = {
        "current_date": "1 Mirtul 1492 DR",
        "time_of_day": "Morning",
        "current_location": "The Yawning Portal",
    }
    return vault


@pytest.fixture
def mock_foundry():
    """MagicMock FoundryClient with common method stubs."""
    foundry = MagicMock()
    foundry.is_connected = True
    foundry.roll_dice = AsyncMock(return_value={
        "total": 15,
        "formula": "1d20+5",
        "dice": [{"faces": 20, "results": [{"result": 10, "active": True}]}],
        "isCritical": False,
        "isFumble": False,
    })
    foundry.search_actors = AsyncMock(return_value=[])
    foundry.search_scenes = AsyncMock(return_value=[])
    foundry.get_active_scene = AsyncMock(return_value=None)
    return foundry


@pytest.fixture
def mock_context_assembler():
    """MagicMock ContextAssembler with common method stubs."""
    ctx = MagicMock()
    ctx.build_rules_lawyer_context.return_value = "No party data."
    ctx.build_storyteller_context.return_value = "No recent context."
    ctx.history = MagicMock()
    ctx.history.add = MagicMock()
    ctx.history.advance_turn = MagicMock()
    ctx.history.clear = MagicMock()
    return ctx


@pytest.fixture
def mock_gemini_limiter():
    """AsyncMock for the rate limiter — patches acquire() as a no-op."""
    limiter = MagicMock()
    limiter.acquire = AsyncMock()
    return limiter
