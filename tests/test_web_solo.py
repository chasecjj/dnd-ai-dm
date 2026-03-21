"""
Tests for web session support in SoloSessionManager (Quest Mirror).

Covers:
- start_web_session creates a session with correct character name and negative thread_id
- get_by_session_id finds the session by UUID
- get_by_session_id returns None for nonexistent UUID
- end_web_session removes the session
- Web session has a ConversationHistory
- Web session has a processing lock (asyncio.Lock)
- Web sessions appear in all_active()
- start_web_session returns None if character already has an active session (duplicate check)
- Multiple web sessions get different negative keys
"""

import asyncio
import pytest
from tools.solo_session import SoloSession, SoloSessionManager


class TestWebSessionLifecycle:
    """Test web session creation, lookup, and teardown."""

    @pytest.fixture
    def manager(self):
        return SoloSessionManager()

    @pytest.mark.asyncio
    async def test_start_web_session_creates_session(self, manager):
        """start_web_session creates a session with correct character name and negative thread_id."""
        session = await manager.start_web_session(
            character_name="Kael",
            current_location="Waterdeep Market",
            session_number=5,
        )
        assert session is not None
        assert session.character_name == "Kael"
        assert session.current_location == "Waterdeep Market"
        assert session.session_number == 5
        assert session.thread_id < 0  # Negative key
        assert session.discord_user_id == 0  # Web sessions use 0
        assert session.turn_count == 0

    @pytest.mark.asyncio
    async def test_get_by_session_id_finds_session(self, manager):
        """get_by_session_id finds the session by its UUID."""
        session = await manager.start_web_session("Kael", "Waterdeep", 5)
        found = manager.get_by_session_id(session.id)
        assert found is not None
        assert found.character_name == "Kael"
        assert found.id == session.id

    @pytest.mark.asyncio
    async def test_get_by_session_id_returns_none_for_nonexistent(self, manager):
        """get_by_session_id returns None for a UUID that doesn't exist."""
        assert manager.get_by_session_id("nonexistent-uuid") is None

    @pytest.mark.asyncio
    async def test_end_web_session_removes_session(self, manager):
        """end_web_session removes the session from all dicts."""
        session = await manager.start_web_session("Kael", "Waterdeep", 5)
        session_id = session.id
        web_key = manager.get_web_thread_key(session_id)

        ended = await manager.end_web_session(session_id)
        assert ended is not None
        assert ended.character_name == "Kael"

        # Session should be gone from all lookups
        assert manager.get_by_session_id(session_id) is None
        assert manager.get_session(web_key) is None
        assert manager.get_web_history(session_id) is None
        assert manager.get_web_processing_lock(session_id) is None
        assert manager.get_web_thread_key(session_id) is None

    @pytest.mark.asyncio
    async def test_end_web_session_returns_none_for_nonexistent(self, manager):
        """end_web_session returns None if session doesn't exist."""
        result = await manager.end_web_session("nonexistent-uuid")
        assert result is None

    @pytest.mark.asyncio
    async def test_web_session_has_conversation_history(self, manager):
        """Web session has a ConversationHistory instance."""
        session = await manager.start_web_session("Kael", "Waterdeep", 5)
        history = manager.get_web_history(session.id)
        assert history is not None
        # ConversationHistory has an entries attribute
        assert hasattr(history, "entries")

    @pytest.mark.asyncio
    async def test_web_session_has_processing_lock(self, manager):
        """Web session has an asyncio.Lock for processing."""
        session = await manager.start_web_session("Kael", "Waterdeep", 5)
        lock = manager.get_web_processing_lock(session.id)
        assert lock is not None
        assert isinstance(lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_web_sessions_appear_in_all_active(self, manager):
        """Web sessions appear in the all_active() list alongside Discord sessions."""
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        await manager.start_web_session("Kael", "Waterdeep", 5)

        active = manager.all_active()
        assert len(active) == 2
        names = {s.character_name for s in active}
        assert names == {"Victor", "Kael"}

    @pytest.mark.asyncio
    async def test_duplicate_character_blocked(self, manager):
        """start_web_session returns None if character already has an active session."""
        await manager.start_web_session("Kael", "Waterdeep", 5)
        duplicate = await manager.start_web_session("Kael", "Somewhere Else", 6)
        assert duplicate is None

    @pytest.mark.asyncio
    async def test_duplicate_character_case_insensitive(self, manager):
        """Duplicate check is case-insensitive."""
        await manager.start_web_session("Kael", "Waterdeep", 5)
        duplicate = await manager.start_web_session("kael", "Somewhere Else", 6)
        assert duplicate is None

    @pytest.mark.asyncio
    async def test_duplicate_character_blocks_across_discord_and_web(self, manager):
        """A Discord session blocks a web session for the same character."""
        await manager.start_session(100, 200, "Kael", "Docks", 3)
        duplicate = await manager.start_web_session("Kael", "Waterdeep", 5)
        assert duplicate is None

    @pytest.mark.asyncio
    async def test_multiple_web_sessions_get_different_keys(self, manager):
        """Multiple web sessions get different negative keys."""
        s1 = await manager.start_web_session("Kael", "Waterdeep", 5)
        s2 = await manager.start_web_session("Lyra", "Baldur's Gate", 5)
        s3 = await manager.start_web_session("Theron", "Neverwinter", 5)

        keys = {s1.thread_id, s2.thread_id, s3.thread_id}
        assert len(keys) == 3  # All different
        assert all(k < 0 for k in keys)  # All negative


class TestWebSessionPipelineIntegration:
    """Test that web sessions work with the same lookup paths as Discord sessions."""

    @pytest.fixture
    def manager(self):
        return SoloSessionManager()

    @pytest.mark.asyncio
    async def test_get_session_finds_web_session_by_thread_key(self, manager):
        """Pipeline nodes use get_session(thread_id) — web sessions must be findable this way."""
        session = await manager.start_web_session("Kael", "Waterdeep", 5)
        web_key = manager.get_web_thread_key(session.id)

        # This is how pipeline nodes look up sessions
        found = manager.get_session(web_key)
        assert found is not None
        assert found.character_name == "Kael"

    @pytest.mark.asyncio
    async def test_get_history_finds_web_session_by_thread_key(self, manager):
        """Pipeline nodes use get_history(thread_id) — web sessions must be findable."""
        session = await manager.start_web_session("Kael", "Waterdeep", 5)
        web_key = manager.get_web_thread_key(session.id)

        history = manager.get_history(web_key)
        assert history is not None

    @pytest.mark.asyncio
    async def test_get_processing_lock_finds_web_session_by_thread_key(self, manager):
        """Pipeline nodes use get_processing_lock(thread_id) — web sessions must be findable."""
        session = await manager.start_web_session("Kael", "Waterdeep", 5)
        web_key = manager.get_web_thread_key(session.id)

        lock = manager.get_processing_lock(web_key)
        assert lock is not None
        assert isinstance(lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_is_solo_thread_works_for_web_sessions(self, manager):
        """is_solo_thread recognizes web session keys."""
        session = await manager.start_web_session("Kael", "Waterdeep", 5)
        web_key = manager.get_web_thread_key(session.id)
        assert manager.is_solo_thread(web_key) is True

    @pytest.mark.asyncio
    async def test_get_by_character_finds_web_session(self, manager):
        """get_by_character works for web sessions too."""
        await manager.start_web_session("Kael", "Waterdeep", 5)
        found = manager.get_by_character("Kael")
        assert found is not None
        assert found.character_name == "Kael"

    @pytest.mark.asyncio
    async def test_increment_turn_works_for_web_session(self, manager):
        """increment_turn works with web session negative keys."""
        session = await manager.start_web_session("Kael", "Waterdeep", 5)
        web_key = manager.get_web_thread_key(session.id)

        await manager.increment_turn(web_key)
        await manager.increment_turn(web_key)

        found = manager.get_session(web_key)
        assert found.turn_count == 2

    @pytest.mark.asyncio
    async def test_end_session_works_for_web_key(self, manager):
        """The standard end_session(thread_id) also works with negative web keys."""
        session = await manager.start_web_session("Kael", "Waterdeep", 5)
        web_key = manager.get_web_thread_key(session.id)

        ended = await manager.end_session(web_key)
        assert ended is not None
        assert ended.character_name == "Kael"
        assert manager.get_session(web_key) is None
