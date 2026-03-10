"""
Tests for the Solo Session system.

Covers:
- SoloSession model validation
- SoloSessionManager lifecycle (start/end/get/is_solo_thread)
- Turn counting
- Concurrent sessions for different users
- Snapshot/undo data model
"""

import asyncio
import pytest
from tools.solo_session import SoloSession, SoloSessionManager, SoloTurnSnapshot


# ---------------------------------------------------------------------------
# Model Tests
# ---------------------------------------------------------------------------

class TestSoloSessionModel:
    """Test the SoloSession Pydantic model."""

    def test_defaults(self):
        session = SoloSession(
            discord_user_id=123,
            thread_id=456,
            character_name="Victor",
            current_location="The Yawning Portal",
            session_number=3,
        )
        assert session.discord_user_id == 123
        assert session.thread_id == 456
        assert session.character_name == "Victor"
        assert session.turn_count == 0
        assert session.current_location == "The Yawning Portal"
        assert session.session_number == 3
        assert session.last_snapshot is None
        assert session.solo_log_path is None
        assert session.id  # UUID generated

    def test_uuid_unique(self):
        s1 = SoloSession(
            discord_user_id=1, thread_id=2, character_name="A",
            current_location="X", session_number=1,
        )
        s2 = SoloSession(
            discord_user_id=1, thread_id=3, character_name="B",
            current_location="Y", session_number=1,
        )
        assert s1.id != s2.id


class TestSoloTurnSnapshot:
    """Test the SoloTurnSnapshot model."""

    def test_snapshot_fields(self):
        snap = SoloTurnSnapshot(
            turn_number=3,
            history_snapshot=[{"text": "event", "base_impact": 5, "turns_ago": 0}],
            location_before="Tavern",
            player_input="I talk to Durnan",
            narrative="Durnan looks up...",
        )
        assert snap.turn_number == 3
        assert len(snap.history_snapshot) == 1
        assert snap.location_before == "Tavern"
        assert snap.player_input == "I talk to Durnan"
        assert snap.narrative == "Durnan looks up..."

    def test_snapshot_defaults(self):
        snap = SoloTurnSnapshot(
            turn_number=1,
            history_snapshot=[],
            location_before="Market",
            player_input="I look around",
        )
        assert snap.narrative == ""


# ---------------------------------------------------------------------------
# Manager Tests
# ---------------------------------------------------------------------------

class TestSoloSessionManager:
    """Test the SoloSessionManager async operations."""

    @pytest.fixture
    def manager(self):
        return SoloSessionManager()

    @pytest.mark.asyncio
    async def test_start_session(self, manager):
        session = await manager.start_session(
            discord_user_id=100,
            thread_id=200,
            character_name="Victor",
            current_location="Docks",
            session_number=3,
        )
        assert session.character_name == "Victor"
        assert session.thread_id == 200
        assert session.turn_count == 0

    @pytest.mark.asyncio
    async def test_get_session(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        session = manager.get_session(200)
        assert session is not None
        assert session.character_name == "Victor"

    @pytest.mark.asyncio
    async def test_get_session_missing(self, manager):
        assert manager.get_session(999) is None

    @pytest.mark.asyncio
    async def test_get_by_user(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        session = manager.get_by_user(100)
        assert session is not None
        assert session.character_name == "Victor"

    @pytest.mark.asyncio
    async def test_get_by_user_missing(self, manager):
        assert manager.get_by_user(999) is None

    @pytest.mark.asyncio
    async def test_is_solo_thread(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        assert manager.is_solo_thread(200) is True
        assert manager.is_solo_thread(999) is False

    @pytest.mark.asyncio
    async def test_end_session(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        session = await manager.end_session(200)
        assert session is not None
        assert session.character_name == "Victor"
        assert manager.get_session(200) is None
        assert manager.is_solo_thread(200) is False

    @pytest.mark.asyncio
    async def test_end_session_missing(self, manager):
        result = await manager.end_session(999)
        assert result is None

    @pytest.mark.asyncio
    async def test_increment_turn(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        await manager.increment_turn(200)
        await manager.increment_turn(200)
        session = manager.get_session(200)
        assert session.turn_count == 2

    @pytest.mark.asyncio
    async def test_all_active(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        await manager.start_session(101, 201, "Hadrian", "Market", 3)
        active = manager.all_active()
        assert len(active) == 2
        names = {s.character_name for s in active}
        assert names == {"Victor", "Hadrian"}

    @pytest.mark.asyncio
    async def test_concurrent_users(self, manager):
        """Two different users can have concurrent solo sessions."""
        s1 = await manager.start_session(100, 200, "Victor", "Docks", 3)
        s2 = await manager.start_session(101, 201, "Hadrian", "Market", 3)

        assert manager.get_by_user(100).character_name == "Victor"
        assert manager.get_by_user(101).character_name == "Hadrian"
        assert manager.is_solo_thread(200)
        assert manager.is_solo_thread(201)

    @pytest.mark.asyncio
    async def test_end_one_preserves_other(self, manager):
        """Ending one session doesn't affect others."""
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        await manager.start_session(101, 201, "Hadrian", "Market", 3)

        await manager.end_session(200)

        assert manager.get_session(200) is None
        assert manager.get_session(201) is not None
        assert manager.get_by_user(101).character_name == "Hadrian"

    @pytest.mark.asyncio
    async def test_snapshot_lifecycle(self, manager):
        """Verify snapshot can be pushed and popped on a session."""
        session = await manager.start_session(100, 200, "Victor", "Docks", 3)

        # Push snapshot
        session.push_snapshot(SoloTurnSnapshot(
            turn_number=1,
            history_snapshot=[{"text": "test", "base_impact": 5, "turns_ago": 0}],
            location_before="Docks",
            player_input="I look around",
            narrative="The docks stretch before you...",
        ))
        assert session.last_snapshot is not None
        assert session.last_snapshot.turn_number == 1

        # Pop snapshot (simulates undo)
        popped = session.pop_snapshot()
        assert popped is not None
        assert popped.turn_number == 1
        assert session.last_snapshot is None
