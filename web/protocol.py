"""
WebSocket protocol models for Quest Mirror.

Defines the message contract between the React SPA frontend and the
FastAPI/WebSocket backend. All messages are Pydantic v2 models that
serialize to plain dicts for JSON transport.

Client → Server: PlayerInput, DiceResult, SessionEnd, Undo, Heartbeat
Server → Client: NarrativeStream, RollRequest, StateUpdate, EnvironmentChange,
                 ChaosUpdate, SessionEvent, StateSync, ErrorMessage, HeartbeatAck
"""

from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field


# ── Client → Server Messages ────────────────────────────────────


class PlayerInput(BaseModel):
    """Player action or question sent from the SPA."""

    type: Literal["player_input"] = "player_input"
    text: str = Field(max_length=2000)
    input_type: str = "action"


class DiceResult(BaseModel):
    """Player's dice roll result sent back after a RollRequest."""

    type: Literal["dice_result"] = "dice_result"
    request_id: str
    result: int
    natural: int


class SessionEnd(BaseModel):
    """Player requests to end the current session."""

    type: Literal["session_end"] = "session_end"


class Undo(BaseModel):
    """Player requests to undo the last turn."""

    type: Literal["undo"] = "undo"


class Heartbeat(BaseModel):
    """Keep-alive ping from the client."""

    type: Literal["heartbeat"] = "heartbeat"


# ── Client Message Factory ──────────────────────────────────────


_CLIENT_TYPE_MAP: dict[str, type[BaseModel]] = {
    "player_input": PlayerInput,
    "dice_result": DiceResult,
    "session_end": SessionEnd,
    "undo": Undo,
    "heartbeat": Heartbeat,
}


class ClientMessage:
    """Factory for dispatching raw dicts to typed client message models."""

    @staticmethod
    def parse(data: dict) -> BaseModel:
        """Parse a raw dict into the appropriate client message model.

        Raises:
            ValueError: If the ``type`` field is missing or unrecognized.
        """
        msg_type = data.get("type")
        if msg_type is None:
            raise ValueError("Missing 'type' field in client message")

        model_cls = _CLIENT_TYPE_MAP.get(msg_type)
        if model_cls is None:
            raise ValueError(f"Unknown client message type: {msg_type!r}")

        return model_cls.model_validate(data)


# ── Server → Client Messages ────────────────────────────────────


class NarrativeStream(BaseModel):
    """Streamed narrative text from the AI DM, delivered in breath groups."""

    type: Literal["narrative_stream"] = "narrative_stream"
    text: str
    mood: str = "neutral"
    breath_group: int = 0
    is_final: bool = False


class RollRequest(BaseModel):
    """Server asks the player to roll dice."""

    type: Literal["roll_request"] = "roll_request"
    request_id: str
    roll_type: str
    formula: str
    prompt: str = ""
    auto_timeout_s: int = 30


class StateUpdate(BaseModel):
    """Partial state update pushed after pipeline processing."""

    type: Literal["state_update"] = "state_update"
    character: Optional[Dict] = None
    scene: Optional[Dict] = None
    world_clock: Optional[Dict] = None


class EnvironmentChange(BaseModel):
    """Signals that the scene environment has changed (drives UI theming)."""

    type: Literal["environment_change"] = "environment_change"
    location: str
    atmosphere: str = ""
    time_of_day: str = ""
    chaos: int = 5
    preset_hint: str = "tavern"


class ChaosUpdate(BaseModel):
    """Mythic-style chaos factor and thread/consequence lists."""

    type: Literal["chaos_update"] = "chaos_update"
    chaos_factor: int
    threads: List[Dict] = Field(default_factory=list)
    consequences: List[Dict] = Field(default_factory=list)


class SessionEvent(BaseModel):
    """Session lifecycle events (start, end, pause, etc.)."""

    type: Literal["session_event"] = "session_event"
    event_type: str
    opening_narrative: str = ""
    character: Optional[Dict] = None
    summary: Optional[Dict] = None


class StateSync(BaseModel):
    """Full state snapshot sent on reconnect or session start."""

    type: Literal["state_sync"] = "state_sync"
    character: Optional[Dict] = None
    scene: Optional[Dict] = None
    chaos: Optional[Dict] = None
    recent_turns: List[Dict] = Field(default_factory=list)
    environment: Optional[Dict] = None


class ErrorMessage(BaseModel):
    """Error sent to the client with recovery information."""

    type: Literal["error"] = "error"
    code: str
    message: str
    recoverable: bool = True


class HeartbeatAck(BaseModel):
    """Server acknowledges a client heartbeat."""

    type: Literal["heartbeat_ack"] = "heartbeat_ack"
