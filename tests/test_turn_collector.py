"""
Tests for tools/turn_collector.py — Time-windowed message batching.

Uses short windows (0.1-0.2s) for fast tests. All tests are async.
"""

import asyncio

from tools.turn_collector import TurnCollector, PendingMessage


class TestTurnCollectorBasics:
    """Test basic collection mechanics."""

    def test_initial_state(self):
        tc = TurnCollector(window_seconds=10)
        assert tc.enabled is True
        assert tc.is_collecting is False
        assert tc.pending_count == 0

    def test_enabled_toggle(self):
        tc = TurnCollector()
        tc.enabled = False
        assert tc.enabled is False
        tc.enabled = True
        assert tc.enabled is True


class TestCollect:
    """Test the collect() method."""

    def test_first_collect_returns_true(self):
        """First message in a window should return True (window just opened)."""
        tc = TurnCollector(window_seconds=5)

        async def run():
            result = await tc.collect("msg1", "Hadrian", "I attack!")
            assert result is True
            assert tc.is_collecting is True
            assert tc.pending_count == 1
            await tc.cancel()

        asyncio.run(run())

    def test_second_collect_returns_false(self):
        """Subsequent messages should return False (added to existing window)."""
        tc = TurnCollector(window_seconds=5)

        async def run():
            await tc.collect("msg1", "Hadrian", "I attack!")
            result = await tc.collect("msg2", "Kallisar", "I cast fireball!")
            assert result is False
            assert tc.pending_count == 2
            await tc.cancel()

        asyncio.run(run())

    def test_multiple_accumulates(self):
        """Multiple collects within a window accumulate messages."""
        tc = TurnCollector(window_seconds=5)

        async def run():
            await tc.collect("msg1", "Hadrian", "I attack!")
            await tc.collect("msg2", "Kallisar", "I dodge!")
            await tc.collect("msg3", None, "I look around")
            assert tc.pending_count == 3
            await tc.cancel()

        asyncio.run(run())


class TestWindowExpiry:
    """Test that window expiry triggers resolution."""

    def test_window_expires_triggers_resolve(self):
        """After window_seconds, the callback fires with all messages."""
        resolved = []

        async def callback(messages):
            resolved.extend(messages)

        tc = TurnCollector(window_seconds=0.1, on_resolve=callback)

        async def run():
            await tc.collect("msg1", "Hadrian", "I attack!")
            await tc.collect("msg2", "Kallisar", "I dodge!")
            # Wait for window to expire
            await asyncio.sleep(0.3)
            assert len(resolved) == 2
            assert resolved[0].character_name == "Hadrian"
            assert resolved[1].character_name == "Kallisar"
            assert not tc.is_collecting
            assert tc.pending_count == 0

        asyncio.run(run())

    def test_single_message_still_resolves(self):
        """Even 1 message triggers the callback after the window."""
        resolved = []

        async def callback(messages):
            resolved.extend(messages)

        tc = TurnCollector(window_seconds=0.1, on_resolve=callback)

        async def run():
            await tc.collect("msg1", "Hadrian", "I open the door")
            await asyncio.sleep(0.3)
            assert len(resolved) == 1
            assert resolved[0].user_input == "I open the door"

        asyncio.run(run())


class TestCancel:
    """Test cancel() behavior."""

    def test_cancel_clears_pending(self):
        """cancel() should clear pending messages without firing callback."""
        resolved = []

        async def callback(messages):
            resolved.extend(messages)

        tc = TurnCollector(window_seconds=5, on_resolve=callback)

        async def run():
            await tc.collect("msg1", "Hadrian", "I attack!")
            await tc.collect("msg2", "Kallisar", "I dodge!")
            assert tc.pending_count == 2
            await tc.cancel()
            assert tc.pending_count == 0
            assert not tc.is_collecting
            assert len(resolved) == 0

        asyncio.run(run())

    def test_cancel_when_not_collecting_is_safe(self):
        tc = TurnCollector(window_seconds=5)

        async def run():
            await tc.cancel()  # Should not raise
            assert tc.pending_count == 0

        asyncio.run(run())


class TestForceResolve:
    """Test force_resolve() behavior."""

    def test_force_resolve_immediate(self):
        """force_resolve() fires callback immediately without waiting."""
        resolved = []

        async def callback(messages):
            resolved.extend(messages)

        tc = TurnCollector(window_seconds=60, on_resolve=callback)

        async def run():
            await tc.collect("msg1", "Hadrian", "I attack!")
            await tc.collect("msg2", "Kallisar", "I dodge!")
            # Force-resolve before the 60s window expires
            await tc.force_resolve()
            assert len(resolved) == 2
            assert not tc.is_collecting

        asyncio.run(run())


class TestPendingMessage:
    """Test the PendingMessage dataclass."""

    def test_fields(self):
        pm = PendingMessage(
            message="discord_msg",
            character_name="Hadrian",
            user_input="I swing my axe!",
        )
        assert pm.message == "discord_msg"
        assert pm.character_name == "Hadrian"
        assert pm.user_input == "I swing my axe!"
        assert pm.timestamp > 0

    def test_optional_character_name(self):
        pm = PendingMessage(message="msg", character_name=None, user_input="Hello")
        assert pm.character_name is None
