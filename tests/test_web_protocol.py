"""
Tests for web/protocol.py — WebSocket message models for Quest Mirror.

Covers roundtrip serialization, all client/server message types,
unknown type handling, default values, and factory dispatch.
"""

import pytest

from web.protocol import (
    # Client → Server
    PlayerInput,
    DiceResult,
    SessionEnd,
    Undo,
    Heartbeat,
    ClientMessage,
    # Server → Client
    NarrativeStream,
    RollRequest,
    StateUpdate,
    EnvironmentChange,
    ChaosUpdate,
    SessionEvent,
    StateSync,
    ErrorMessage,
    HeartbeatAck,
)


# ── Client → Server ─────────────────────────────────────────────


class TestPlayerInput:
    def test_basic_construction(self):
        msg = PlayerInput(text="I open the door")
        assert msg.type == "player_input"
        assert msg.text == "I open the door"
        assert msg.input_type == "action"

    def test_custom_input_type(self):
        msg = PlayerInput(text="Is there a trap?", input_type="question")
        assert msg.input_type == "question"

    def test_text_max_length(self):
        long_text = "a" * 2001
        with pytest.raises(Exception):  # ValidationError
            PlayerInput(text=long_text)

    def test_text_at_max_length(self):
        text = "a" * 2000
        msg = PlayerInput(text=text)
        assert len(msg.text) == 2000

    def test_roundtrip(self):
        msg = PlayerInput(text="I attack the goblin", input_type="action")
        data = msg.model_dump()
        restored = ClientMessage.parse(data)
        assert isinstance(restored, PlayerInput)
        assert restored.text == "I attack the goblin"
        assert restored.input_type == "action"


class TestDiceResult:
    def test_basic_construction(self):
        msg = DiceResult(request_id="roll-001", result=15, natural=12)
        assert msg.type == "dice_result"
        assert msg.request_id == "roll-001"
        assert msg.result == 15
        assert msg.natural == 12

    def test_roundtrip(self):
        msg = DiceResult(request_id="roll-42", result=20, natural=20)
        data = msg.model_dump()
        restored = ClientMessage.parse(data)
        assert isinstance(restored, DiceResult)
        assert restored.request_id == "roll-42"
        assert restored.result == 20
        assert restored.natural == 20


class TestSessionEnd:
    def test_construction(self):
        msg = SessionEnd()
        assert msg.type == "session_end"

    def test_roundtrip(self):
        data = SessionEnd().model_dump()
        restored = ClientMessage.parse(data)
        assert isinstance(restored, SessionEnd)


class TestUndo:
    def test_construction(self):
        msg = Undo()
        assert msg.type == "undo"

    def test_roundtrip(self):
        data = Undo().model_dump()
        restored = ClientMessage.parse(data)
        assert isinstance(restored, Undo)


class TestHeartbeat:
    def test_construction(self):
        msg = Heartbeat()
        assert msg.type == "heartbeat"

    def test_roundtrip(self):
        data = Heartbeat().model_dump()
        restored = ClientMessage.parse(data)
        assert isinstance(restored, Heartbeat)


class TestClientMessageParse:
    def test_unknown_type_raises(self):
        with pytest.raises(ValueError, match="Unknown client message type"):
            ClientMessage.parse({"type": "teleport"})

    def test_missing_type_raises(self):
        with pytest.raises(ValueError, match="Missing 'type' field"):
            ClientMessage.parse({"text": "hello"})


# ── Server → Client ─────────────────────────────────────────────


class TestNarrativeStream:
    def test_basic_construction(self):
        msg = NarrativeStream(text="The door creaks open...")
        assert msg.type == "narrative_stream"
        assert msg.text == "The door creaks open..."
        assert msg.mood == "neutral"
        assert msg.breath_group == 0
        assert msg.is_final is False

    def test_all_fields(self):
        msg = NarrativeStream(
            text="A shadow looms.",
            mood="tense",
            breath_group=3,
            is_final=True,
        )
        assert msg.mood == "tense"
        assert msg.breath_group == 3
        assert msg.is_final is True


class TestRollRequest:
    def test_basic_construction(self):
        msg = RollRequest(
            request_id="roll-001",
            roll_type="attack",
            formula="1d20+5",
        )
        assert msg.type == "roll_request"
        assert msg.request_id == "roll-001"
        assert msg.roll_type == "attack"
        assert msg.formula == "1d20+5"
        assert msg.prompt == ""
        assert msg.auto_timeout_s == 30

    def test_custom_timeout(self):
        msg = RollRequest(
            request_id="r1",
            roll_type="save",
            formula="1d20+3",
            prompt="Dexterity saving throw!",
            auto_timeout_s=15,
        )
        assert msg.prompt == "Dexterity saving throw!"
        assert msg.auto_timeout_s == 15


class TestStateUpdate:
    def test_defaults_none(self):
        msg = StateUpdate()
        assert msg.type == "state_update"
        assert msg.character is None
        assert msg.scene is None
        assert msg.world_clock is None

    def test_with_data(self):
        msg = StateUpdate(
            character={"name": "Elara", "hp": 25},
            scene={"location": "tavern"},
        )
        assert msg.character["name"] == "Elara"
        assert msg.scene["location"] == "tavern"
        assert msg.world_clock is None


class TestEnvironmentChange:
    def test_defaults(self):
        msg = EnvironmentChange(location="Dark Forest")
        assert msg.type == "environment_change"
        assert msg.location == "Dark Forest"
        assert msg.atmosphere == ""
        assert msg.time_of_day == ""
        assert msg.chaos == 5
        assert msg.preset_hint == "tavern"

    def test_all_fields(self):
        msg = EnvironmentChange(
            location="Dragon's Lair",
            atmosphere="oppressive heat",
            time_of_day="night",
            chaos=9,
            preset_hint="dungeon",
        )
        assert msg.chaos == 9
        assert msg.preset_hint == "dungeon"


class TestChaosUpdate:
    def test_defaults(self):
        msg = ChaosUpdate(chaos_factor=5)
        assert msg.type == "chaos_update"
        assert msg.chaos_factor == 5
        assert msg.threads == []
        assert msg.consequences == []

    def test_mutable_default_isolation(self):
        """Ensure list defaults don't share state between instances."""
        msg1 = ChaosUpdate(chaos_factor=5)
        msg2 = ChaosUpdate(chaos_factor=7)
        msg1.threads.append({"name": "test"})
        assert msg2.threads == []

    def test_with_data(self):
        msg = ChaosUpdate(
            chaos_factor=8,
            threads=[{"name": "Missing prince"}],
            consequences=[{"event": "tavern burned"}],
        )
        assert len(msg.threads) == 1
        assert msg.consequences[0]["event"] == "tavern burned"


class TestSessionEvent:
    def test_defaults(self):
        msg = SessionEvent(event_type="session_start")
        assert msg.type == "session_event"
        assert msg.event_type == "session_start"
        assert msg.opening_narrative == ""
        assert msg.character is None
        assert msg.summary is None

    def test_with_data(self):
        msg = SessionEvent(
            event_type="session_start",
            opening_narrative="You awaken in a dim cell...",
            character={"name": "Thorin", "class": "Fighter"},
        )
        assert msg.opening_narrative == "You awaken in a dim cell..."
        assert msg.character["name"] == "Thorin"


class TestStateSync:
    def test_defaults(self):
        msg = StateSync()
        assert msg.type == "state_sync"
        assert msg.character is None
        assert msg.scene is None
        assert msg.chaos is None
        assert msg.recent_turns == []
        assert msg.environment is None

    def test_mutable_default_isolation(self):
        """Ensure list defaults don't share state between instances."""
        msg1 = StateSync()
        msg2 = StateSync()
        msg1.recent_turns.append({"turn": 1})
        assert msg2.recent_turns == []

    def test_with_data(self):
        msg = StateSync(
            character={"name": "Elara"},
            scene={"location": "tavern"},
            chaos={"factor": 5},
            recent_turns=[{"turn": 1, "text": "hello"}],
            environment={"location": "Tavern", "atmosphere": "warm"},
        )
        assert msg.character["name"] == "Elara"
        assert len(msg.recent_turns) == 1
        assert msg.environment["atmosphere"] == "warm"


class TestErrorMessage:
    def test_basic_construction(self):
        msg = ErrorMessage(code="INVALID_INPUT", message="Bad request")
        assert msg.type == "error"
        assert msg.code == "INVALID_INPUT"
        assert msg.message == "Bad request"
        assert msg.recoverable is True

    def test_non_recoverable(self):
        msg = ErrorMessage(
            code="SESSION_EXPIRED",
            message="Session no longer valid",
            recoverable=False,
        )
        assert msg.recoverable is False


class TestHeartbeatAck:
    def test_construction(self):
        msg = HeartbeatAck()
        assert msg.type == "heartbeat_ack"


# ── Serialization ────────────────────────────────────────────────


class TestSerialization:
    """Verify model_dump produces clean dicts for JSON serialization."""

    def test_server_message_dump(self):
        msg = NarrativeStream(text="Hello", mood="calm", is_final=True)
        data = msg.model_dump()
        assert data == {
            "type": "narrative_stream",
            "text": "Hello",
            "mood": "calm",
            "breath_group": 0,
            "is_final": True,
        }

    def test_error_message_dump(self):
        msg = ErrorMessage(code="E001", message="fail")
        data = msg.model_dump()
        assert data == {
            "type": "error",
            "code": "E001",
            "message": "fail",
            "recoverable": True,
        }

    def test_client_message_dump(self):
        msg = PlayerInput(text="I search the room")
        data = msg.model_dump()
        assert data == {
            "type": "player_input",
            "text": "I search the room",
            "input_type": "action",
        }

    def test_chaos_update_dump_with_empty_lists(self):
        msg = ChaosUpdate(chaos_factor=5)
        data = msg.model_dump()
        assert data == {
            "type": "chaos_update",
            "chaos_factor": 5,
            "threads": [],
            "consequences": [],
        }
