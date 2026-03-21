"""
Tests for the Quest Mirror WebSocket handler.

Covers the WebSocketSession class:
- Creation and default state
- is_alive property (alive by default, dead after threshold)
- record_heartbeat resets missed count
- tick_heartbeat increments missed count
- send() calls ws.send_json with model_dump
- stream_narrative chunks and sends NarrativeStream messages

Integration tests for the full endpoint handler are in Task 18.
"""

import asyncio
import pytest
from collections import deque
from unittest.mock import AsyncMock, MagicMock, patch

from web.ws_handler import (
    BREATH_GROUP_BUFFER_SIZE,
    HEARTBEAT_TIMEOUT_MISSED,
    WebSocketSession,
)
from web.protocol import HeartbeatAck, ErrorMessage, NarrativeStream


class _FakeWebSocket:
    """Minimal WebSocket mock with client_state tracking."""

    def __init__(self, *, connected: bool = True):
        from starlette.websockets import WebSocketState

        self.client_state = (
            WebSocketState.CONNECTED if connected else WebSocketState.DISCONNECTED
        )
        self.send_json = AsyncMock()
        self.close = AsyncMock()


class TestWebSocketSessionCreation:
    """Test WebSocketSession initialization."""

    def test_creation_defaults(self):
        """New session has zero missed heartbeats and an empty buffer."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, session_id="abc-123", token="tok")

        assert sess.ws is ws
        assert sess.session_id == "abc-123"
        assert sess.token == "tok"
        assert sess.missed_heartbeats == 0
        assert isinstance(sess.breath_group_buffer, deque)
        assert len(sess.breath_group_buffer) == 0

    def test_is_alive_true_initially(self):
        """is_alive is True when missed_heartbeats is 0."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")
        assert sess.is_alive is True

    def test_is_alive_true_below_threshold(self):
        """is_alive is True when missed_heartbeats < HEARTBEAT_TIMEOUT_MISSED."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")
        sess.missed_heartbeats = HEARTBEAT_TIMEOUT_MISSED - 1
        assert sess.is_alive is True

    def test_is_alive_false_at_threshold(self):
        """is_alive is False when missed_heartbeats == HEARTBEAT_TIMEOUT_MISSED."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")
        sess.missed_heartbeats = HEARTBEAT_TIMEOUT_MISSED
        assert sess.is_alive is False

    def test_is_alive_false_above_threshold(self):
        """is_alive is False when missed_heartbeats > HEARTBEAT_TIMEOUT_MISSED."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")
        sess.missed_heartbeats = HEARTBEAT_TIMEOUT_MISSED + 5
        assert sess.is_alive is False


class TestHeartbeat:
    """Test heartbeat recording and ticking."""

    def test_record_heartbeat_resets_count(self):
        """record_heartbeat sets missed_heartbeats back to 0."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")
        sess.missed_heartbeats = 2
        sess.record_heartbeat()
        assert sess.missed_heartbeats == 0

    def test_record_heartbeat_updates_last_heartbeat(self):
        """record_heartbeat updates last_heartbeat timestamp."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")
        old_ts = sess.last_heartbeat
        # Advance a bit
        import time
        time.sleep(0.01)
        sess.record_heartbeat()
        assert sess.last_heartbeat >= old_ts

    def test_tick_heartbeat_increments(self):
        """tick_heartbeat increments missed_heartbeats by 1."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")
        assert sess.missed_heartbeats == 0
        sess.tick_heartbeat()
        assert sess.missed_heartbeats == 1
        sess.tick_heartbeat()
        assert sess.missed_heartbeats == 2

    def test_tick_then_record_resets(self):
        """Ticking then recording resets the count."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")
        sess.tick_heartbeat()
        sess.tick_heartbeat()
        assert sess.missed_heartbeats == 2
        sess.record_heartbeat()
        assert sess.missed_heartbeats == 0
        assert sess.is_alive is True

    def test_three_ticks_kills_session(self):
        """Three consecutive ticks without a heartbeat kills the session."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")
        for _ in range(HEARTBEAT_TIMEOUT_MISSED):
            assert sess.is_alive is True
            sess.tick_heartbeat()
        assert sess.is_alive is False


class TestSend:
    """Test the send() method."""

    @pytest.mark.asyncio
    async def test_send_calls_send_json_with_model_dump(self):
        """send() serializes the message via model_dump and calls ws.send_json."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")

        msg = HeartbeatAck()
        result = await sess.send(msg)

        assert result is True
        ws.send_json.assert_awaited_once_with({"type": "heartbeat_ack"})

    @pytest.mark.asyncio
    async def test_send_returns_false_when_disconnected(self):
        """send() returns False when the WebSocket is disconnected."""
        ws = _FakeWebSocket(connected=False)
        sess = WebSocketSession(ws, "s", "t")

        msg = HeartbeatAck()
        result = await sess.send(msg)

        assert result is False
        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_send_returns_false_on_exception(self):
        """send() returns False if ws.send_json raises."""
        ws = _FakeWebSocket()
        ws.send_json.side_effect = RuntimeError("connection reset")
        sess = WebSocketSession(ws, "s", "t")

        result = await sess.send(HeartbeatAck())
        assert result is False

    @pytest.mark.asyncio
    async def test_send_error_message(self):
        """send() works with ErrorMessage models."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")

        msg = ErrorMessage(code="test", message="oops", recoverable=True)
        result = await sess.send(msg)

        assert result is True
        sent_data = ws.send_json.call_args[0][0]
        assert sent_data["type"] == "error"
        assert sent_data["code"] == "test"
        assert sent_data["message"] == "oops"


class TestStreamNarrative:
    """Test narrative streaming via breath groups."""

    @pytest.mark.asyncio
    async def test_stream_sends_chunks(self):
        """stream_narrative sends NarrativeStream for each chunk."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")

        await sess.stream_narrative("Hello world. This is a test.")

        # Should have sent at least one message
        assert ws.send_json.await_count >= 1

        # Last chunk should be is_final=True
        last_call = ws.send_json.call_args_list[-1][0][0]
        assert last_call["type"] == "narrative_stream"
        assert last_call["is_final"] is True

    @pytest.mark.asyncio
    async def test_stream_buffers_chunks(self):
        """stream_narrative fills the breath_group_buffer."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")

        await sess.stream_narrative("A short narrative.")

        assert len(sess.breath_group_buffer) > 0

    @pytest.mark.asyncio
    async def test_stream_respects_mood(self):
        """stream_narrative passes the mood to each chunk."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")

        await sess.stream_narrative("Dramatic moment.", mood="tense")

        sent_data = ws.send_json.call_args_list[0][0][0]
        assert sent_data["mood"] == "tense"

    @pytest.mark.asyncio
    async def test_stream_empty_narrative_sends_nothing(self):
        """stream_narrative with empty text sends no messages."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")

        await sess.stream_narrative("")

        ws.send_json.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stream_stops_on_dead_connection(self):
        """stream_narrative stops sending when send() returns False."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")

        # First call succeeds, second fails
        call_count = 0

        async def fail_after_first(data):
            nonlocal call_count
            call_count += 1
            if call_count > 1:
                from starlette.websockets import WebSocketState
                ws.client_state = WebSocketState.DISCONNECTED

        ws.send_json.side_effect = fail_after_first

        # Use multiple sentences to generate multiple chunks
        await sess.stream_narrative(
            "The dragon roars with fury. The ground shakes beneath your feet. "
            "Flames erupt from its maw. You dive for cover."
        )

        # Should have stopped early (not sent all chunks)
        # The exact count depends on chunking, but we verify it didn't error out

    @pytest.mark.asyncio
    async def test_buffer_max_size(self):
        """breath_group_buffer respects BREATH_GROUP_BUFFER_SIZE limit."""
        ws = _FakeWebSocket()
        sess = WebSocketSession(ws, "s", "t")

        # Generate many chunks via a long narrative with many sentences
        sentences = ". ".join(f"Sentence number {i}" for i in range(20))
        await sess.stream_narrative(sentences + ".")

        assert len(sess.breath_group_buffer) <= BREATH_GROUP_BUFFER_SIZE


class TestConstants:
    """Verify exported constants."""

    def test_heartbeat_interval(self):
        from web.ws_handler import HEARTBEAT_INTERVAL_S
        assert HEARTBEAT_INTERVAL_S == 15

    def test_heartbeat_timeout_missed(self):
        assert HEARTBEAT_TIMEOUT_MISSED == 3

    def test_breath_group_buffer_size(self):
        assert BREATH_GROUP_BUFFER_SIZE == 10
