"""WebSocket connection handler for Quest Mirror.

Manages real-time communication between the React SPA and the game
pipeline.  Parallels ``_handle_solo_message()`` in ``bot/client.py``
but delivers narrative over WebSocket instead of Discord.

Key differences from the Discord handler:
- Uses session UUID for lookup instead of ``message.channel.id``
- Sets ``_solo_thread_id`` to the *negative int* key from
  ``solo_manager.get_web_thread_key()`` (B1 fix — never 0)
- Streams narrative via breath-group chunks instead of Discord chunked sends
- Heartbeat monitoring replaces Discord's built-in keep-alive
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from typing import Any, Dict, Optional

from starlette.websockets import WebSocketState

from web.auth import validate_token
from web.breath_groups import chunk_narrative
from web.protocol import (
    ChaosUpdate,
    ClientMessage,
    EnvironmentChange,
    ErrorMessage,
    HeartbeatAck,
    NarrativeStream,
    SessionEvent,
    StateSync,
    StateUpdate,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

HEARTBEAT_INTERVAL_S = 15
HEARTBEAT_TIMEOUT_MISSED = 3
BREATH_GROUP_BUFFER_SIZE = 10

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_active_connections: Dict[str, "WebSocketSession"] = {}

# Pipeline serialization — mirrors bot/client.py's _pipeline_semaphore
_pipeline_semaphore = asyncio.Semaphore(1)


# ---------------------------------------------------------------------------
# WebSocketSession
# ---------------------------------------------------------------------------


class WebSocketSession:
    """Manages state for a single WebSocket connection."""

    def __init__(self, ws: Any, session_id: str, token: str) -> None:
        self.ws = ws
        self.session_id = session_id
        self.token = token
        self.missed_heartbeats: int = 0
        self.last_heartbeat: float = time.monotonic()
        self.breath_group_buffer: deque[dict] = deque(maxlen=BREATH_GROUP_BUFFER_SIZE)

    # -- Heartbeat helpers ---------------------------------------------------

    @property
    def is_alive(self) -> bool:
        """True if the connection has not exceeded the missed heartbeat limit."""
        return self.missed_heartbeats < HEARTBEAT_TIMEOUT_MISSED

    def record_heartbeat(self) -> None:
        """Reset the missed heartbeat counter (client sent a heartbeat)."""
        self.missed_heartbeats = 0
        self.last_heartbeat = time.monotonic()

    def tick_heartbeat(self) -> None:
        """Increment the missed heartbeat counter (called by the heartbeat loop)."""
        self.missed_heartbeats += 1

    # -- Sending helpers -----------------------------------------------------

    async def send(self, msg: Any) -> bool:
        """Send a protocol message as JSON.

        Returns ``False`` if the connection is dead.
        """
        try:
            if self.ws.client_state != WebSocketState.CONNECTED:
                return False
            data = msg.model_dump() if hasattr(msg, "model_dump") else msg
            await self.ws.send_json(data)
            return True
        except Exception:
            return False

    async def stream_narrative(self, narrative: str, mood: str = "neutral") -> None:
        """Chunk *narrative* via ``chunk_narrative()`` and send each piece.

        Buffers the last ``BREATH_GROUP_BUFFER_SIZE`` chunks for potential
        retransmission.  No server-side delay between chunks — the client
        owns pacing.
        """
        chunks = chunk_narrative(narrative, mood=mood)
        for chunk in chunks:
            msg = NarrativeStream(
                text=chunk["text"],
                mood=chunk["mood"],
                breath_group=chunk["breath_group"],
                is_final=chunk["is_final"],
            )
            self.breath_group_buffer.append(chunk)
            ok = await self.send(msg)
            if not ok:
                break


# ---------------------------------------------------------------------------
# WebSocket endpoint registration
# ---------------------------------------------------------------------------


def register_ws(app: Any) -> None:
    """Register the WebSocket endpoint on the FastAPI app."""

    @app.websocket("/ws/solo/{session_id}")
    async def ws_solo(websocket: Any, session_id: str) -> None:
        # -- Auth -----------------------------------------------------------
        token = websocket.query_params.get("token", "")
        if not validate_token(token):
            await websocket.close(code=4001, reason="Invalid token")
            return

        # -- Session lookup -------------------------------------------------
        from bot.client import solo_manager

        session = solo_manager.get_by_session_id(session_id)
        if session is None:
            await websocket.close(code=4004, reason="Session not found")
            return

        # -- Accept + setup -------------------------------------------------
        await websocket.accept()
        ws_session = WebSocketSession(websocket, session_id, token)
        _active_connections[session_id] = ws_session

        logger.info(
            "WebSocket connected: session=%s character=%s",
            session_id,
            session.character_name,
        )

        # Send initial state
        await _send_state_sync(ws_session, session)

        # Start heartbeat monitor
        heartbeat_task = asyncio.create_task(_heartbeat_loop(ws_session))

        try:
            while True:
                # Receive with timeout so the loop stays responsive
                try:
                    raw = await asyncio.wait_for(
                        websocket.receive_json(), timeout=HEARTBEAT_INTERVAL_S
                    )
                except asyncio.TimeoutError:
                    # H7 fix: just continue — only _heartbeat_loop ticks
                    continue

                # -- Parse + dispatch ---------------------------------------
                try:
                    msg = ClientMessage.parse(raw)
                except ValueError as parse_err:
                    await ws_session.send(
                        ErrorMessage(
                            code="parse_error",
                            message=str(parse_err),
                            recoverable=True,
                        )
                    )
                    continue

                msg_type = raw.get("type", "")

                if msg_type == "heartbeat":
                    ws_session.record_heartbeat()
                    await ws_session.send(HeartbeatAck())

                elif msg_type == "player_input":
                    await _handle_player_input(ws_session, session, msg)

                elif msg_type == "undo":
                    await _handle_undo(ws_session, session)

                elif msg_type == "session_end":
                    await _handle_session_end(ws_session, session)
                    break

                elif msg_type == "dice_result":
                    logger.info(
                        "DiceResult received (Phase 1a — no async roll flow): %s",
                        raw,
                    )

                else:
                    await ws_session.send(
                        ErrorMessage(
                            code="unknown_type",
                            message=f"Unknown message type: {msg_type!r}",
                            recoverable=True,
                        )
                    )

        except Exception as exc:
            # WebSocket disconnect or unexpected error
            logger.info("WebSocket disconnected: session=%s (%s)", session_id, exc)
        finally:
            heartbeat_task.cancel()
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            _active_connections.pop(session_id, None)
            logger.info("WebSocket cleanup complete: session=%s", session_id)


# ---------------------------------------------------------------------------
# Heartbeat loop
# ---------------------------------------------------------------------------


async def _heartbeat_loop(ws_session: WebSocketSession) -> None:
    """Periodically tick the heartbeat counter.

    Runs every ``HEARTBEAT_INTERVAL_S`` seconds.  Stops when the session
    is no longer alive or when the task is cancelled.
    """
    try:
        while ws_session.is_alive:
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)
            ws_session.tick_heartbeat()
            if not ws_session.is_alive:
                logger.info(
                    "Heartbeat timeout: session=%s (missed=%d)",
                    ws_session.session_id,
                    ws_session.missed_heartbeats,
                )
                # Close the WebSocket to break the main loop
                try:
                    await ws_session.ws.close(
                        code=4002, reason="Heartbeat timeout"
                    )
                except Exception:
                    pass
                break
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# State sync
# ---------------------------------------------------------------------------


async def _send_state_sync(
    ws_session: WebSocketSession, session: Any
) -> None:
    """Send a full ``StateSync`` to the client.

    Loads character data from MongoDB if available and builds the
    ``recent_turns`` list from the session's narrative window.
    """
    # Try to load character data from MongoDB
    character_data: Optional[Dict] = None
    try:
        from bot.client import state_manager

        if state_manager and state_manager.is_connected:
            char_doc = await state_manager.get_character(session.character_name)
            if char_doc:
                character_data = {
                    "name": session.character_name,
                    "location": session.current_location,
                    "data": char_doc,
                }
    except Exception as e:
        logger.warning("Failed to load character data for state sync: %s", e)

    if character_data is None:
        character_data = {
            "name": session.character_name,
            "location": session.current_location,
        }

    # Build recent_turns from session.recent_narratives
    recent_turns = []
    for entry in session.recent_narratives:
        recent_turns.append({
            "turn": entry.get("turn", 0),
            "player_input": entry.get("player_input", ""),
            "narrative": entry.get("narrative", ""),
        })

    # Build chaos info
    chaos_data = {
        "chaos_factor": session.chaos_factor,
        "threads": session.active_threads,
    }

    # Build environment
    env_data = {
        "location": session.current_location,
    }

    await ws_session.send(
        StateSync(
            character=character_data,
            scene=dict(session.scene_state_data) if session.scene_state_data else None,
            chaos=chaos_data,
            recent_turns=recent_turns,
            environment=env_data,
        )
    )


# ---------------------------------------------------------------------------
# Player input handler
# ---------------------------------------------------------------------------


async def _handle_player_input(
    ws_session: WebSocketSession, session: Any, msg: Any
) -> None:
    """Handle a player action or inquiry — the core game loop.

    Parallels ``_handle_solo_message()`` in ``bot/client.py`` (line 526)
    but streams over WebSocket.
    """
    from bot.client import (
        solo_manager,
        game_pipeline,
        storyteller,
        vault,
        pipeline_metrics,
    )
    from tools.content_filter import filter_content
    from tools.solo_session import SoloTurnSnapshot

    session_id = ws_session.session_id
    user_input = msg.text
    character_name = session.character_name

    # 1. Acquire processing lock
    processing_lock = solo_manager.get_web_processing_lock(session_id)
    if processing_lock and processing_lock.locked():
        await ws_session.send(
            ErrorMessage(
                code="processing",
                message="Still processing your last action...",
                recoverable=True,
            )
        )
        return

    async with processing_lock if processing_lock else _nullcontext():
        # 2. Content filter
        user_input, was_filtered = filter_content(user_input)
        if was_filtered:
            logger.info("[Solo/Web] Filtered input for %s", character_name)

        # 3. Inquiry detection (simplified — "dm:" prefix only for Phase 1a)
        is_inquiry = False
        inquiry_input = user_input
        dm_prefixes = ("dm:", "for the dm:", "dm,")
        lower_input = user_input.lower().strip()
        for prefix in dm_prefixes:
            if lower_input.startswith(prefix):
                is_inquiry = True
                inquiry_input = user_input[len(prefix):].strip()
                break

        # 4. Handle inquiry
        if is_inquiry:
            logger.info("[Solo/Web Inquiry] %s: %s", character_name, inquiry_input)
            try:
                session_history = solo_manager.get_web_history(session_id)
                response_text = await storyteller.answer_inquiry(
                    question=inquiry_input,
                    character_name=character_name,
                    location=session.current_location,
                    solo_history=session_history,
                )
                if not response_text:
                    response_text = "The answer eludes you for now..."

                await ws_session.stream_narrative(response_text, mood="inquiry")

                # Lightweight history entry
                if session_history:
                    session_history.add_event(
                        f"[Inquiry] {inquiry_input} -> {response_text[:200]}",
                        impact=3,
                        character=character_name,
                        location=session.current_location,
                        age_existing=False,
                    )
                session.touch()
            except Exception as inquiry_err:
                logger.error("Solo/Web inquiry error: %s", inquiry_err, exc_info=True)
                await ws_session.send(
                    ErrorMessage(
                        code="inquiry_error",
                        message="The DM can't find the answer right now...",
                        recoverable=True,
                    )
                )
            return

        # 5. Full turn flow — snapshot for undo
        session_history = solo_manager.get_web_history(session_id)
        history_snapshot = [
            {
                "text": e.text,
                "base_impact": e.base_impact,
                "turns_ago": e.turns_ago,
                "timestamp": e.timestamp,
                "character": e.character,
                "location": e.location,
            }
            for e in (session_history.entries if session_history else [])
        ]

        turn_number = session.turn_count
        session.push_snapshot(
            SoloTurnSnapshot(
                turn_number=turn_number,
                history_snapshot=history_snapshot,
                location_before=session.current_location,
                player_input=user_input,
                recent_narratives_snapshot=list(session.recent_narratives),
                scene_state_snapshot=dict(session.scene_state_data),
            )
        )

        # Build initial state — CRITICAL: use negative int key, NOT 0
        thread_key = solo_manager.get_web_thread_key(session_id)
        initial_state = {
            "player_input": f"[{character_name}]: {user_input}",
            "character_name": character_name,
            "session": session.session_number,
            "current_location": session.current_location,
            "dice_results": None,
            "is_solo": True,
            "_solo_thread_id": thread_key,
        }

        # 6. Pipeline invocation with retry
        result = None
        _pipeline_start = time.monotonic()
        for _attempt in range(2):
            try:
                async with _pipeline_semaphore:
                    result = await game_pipeline.ainvoke(initial_state)
                pipeline_metrics.record_request(
                    time.monotonic() - _pipeline_start,
                    is_solo=True,
                    success=True,
                )
                break
            except Exception as pipeline_err:
                if _attempt == 0:
                    logger.warning(
                        "Web pipeline attempt 1 failed: %s", pipeline_err
                    )
                    await asyncio.sleep(1)
                else:
                    pipeline_metrics.record_request(
                        time.monotonic() - _pipeline_start,
                        is_solo=True,
                        success=False,
                        error_type="pipeline_error",
                    )
                    logger.error(
                        "Web pipeline failed after retry: %s",
                        pipeline_err,
                        exc_info=True,
                    )
                    await ws_session.send(
                        ErrorMessage(
                            code="pipeline_error",
                            message="The threads of fate tangle momentarily... Try again!",
                            recoverable=True,
                        )
                    )
                    return

        if result is None:
            return

        # 7. Stream narrative
        narrative = result.get("narrative", "")
        if not narrative:
            narrative = "*The moment passes quietly...*"

        mood = result.get("mood", "neutral")
        await ws_session.stream_narrative(narrative, mood=mood)

        # 8. Store narrative in snapshot for undo reference
        if session.last_snapshot:
            session.last_snapshot.narrative = narrative

        # Record exchange in per-session history
        if session_history:
            session_history.add_event(
                f"[Player] {user_input}",
                impact=5,
                character=character_name,
                location=session.current_location,
                age_existing=True,
            )
            session_history.add_event(
                narrative[:500],
                impact=7,
                character=character_name,
                location=session.current_location,
                age_existing=False,
            )

        # Push to sliding window
        session.push_narrative(turn_number, user_input, narrative)

        # 9. Increment turn, track location changes
        await solo_manager.increment_turn(thread_key)

        scene_changes = result.get("scene_changes") or {}
        location_changed = (
            scene_changes.get("location_changed")
            and scene_changes.get("new_location")
        )
        if location_changed:
            new_location = scene_changes["new_location"]
            session.current_location = new_location
            storyteller.set_character_location(character_name, new_location)
            await ws_session.send(
                EnvironmentChange(
                    location=new_location,
                    atmosphere=scene_changes.get("atmosphere", ""),
                    time_of_day=scene_changes.get("time_of_day", ""),
                    chaos=session.chaos_factor,
                )
            )

        # 10. Log to vault
        vault.append_to_solo_log(
            character_name=character_name,
            session_number=session.session_number,
            turn_number=turn_number,
            player_input=user_input,
            narrative=narrative,
            log_path=getattr(session, "solo_log_path", None),
        )

        # 11. Solo post-processing (chaos/threads/NPCs)
        await _solo_post_process(session, result, turn_number)

        # 12. Send StateUpdate and ChaosUpdate
        await ws_session.send(
            StateUpdate(
                scene=dict(session.scene_state_data) if session.scene_state_data else None,
            )
        )
        await ws_session.send(
            ChaosUpdate(
                chaos_factor=session.chaos_factor,
                threads=session.active_threads,
            )
        )

        if result.get("error"):
            logger.error("Web pipeline error: %s", result["error"])


# ---------------------------------------------------------------------------
# Undo handler
# ---------------------------------------------------------------------------


async def _handle_undo(ws_session: WebSocketSession, session: Any) -> None:
    """Pop the last snapshot and restore session state."""
    from bot.client import solo_manager

    snapshot = session.pop_snapshot()
    if snapshot is None:
        await ws_session.send(
            ErrorMessage(
                code="no_undo",
                message="Nothing to undo.",
                recoverable=True,
            )
        )
        return

    # Restore state
    session.turn_count = snapshot.turn_number
    session.current_location = snapshot.location_before
    session.recent_narratives = list(snapshot.recent_narratives_snapshot)
    session.scene_state_data = dict(snapshot.scene_state_snapshot)

    # Restore conversation history
    session_history = solo_manager.get_web_history(ws_session.session_id)
    if session_history and snapshot.history_snapshot:
        from tools.context_assembler import MemoryEntry

        session_history.entries.clear()
        for entry_data in snapshot.history_snapshot:
            session_history.entries.append(
                MemoryEntry(
                    text=entry_data["text"],
                    base_impact=entry_data["base_impact"],
                    turns_ago=entry_data.get("turns_ago", 0),
                    timestamp=entry_data.get("timestamp", 0.0),
                    character=entry_data.get("character"),
                    location=entry_data.get("location"),
                )
            )

    await ws_session.send(
        SessionEvent(event_type="undo_complete")
    )
    await _send_state_sync(ws_session, session)

    logger.info(
        "Undo complete: session=%s turn=%d",
        ws_session.session_id,
        snapshot.turn_number,
    )


# ---------------------------------------------------------------------------
# Session end handler
# ---------------------------------------------------------------------------


async def _handle_session_end(
    ws_session: WebSocketSession, session: Any
) -> None:
    """End the solo session cleanly."""
    from bot.client import solo_manager

    ended = await solo_manager.end_web_session(ws_session.session_id)
    summary = {}
    if ended:
        summary = {
            "character_name": ended.character_name,
            "turns": ended.turn_count,
            "location": ended.current_location,
        }

    await ws_session.send(
        SessionEvent(event_type="end", summary=summary)
    )
    logger.info(
        "Session ended via WebSocket: session=%s character=%s turns=%d",
        ws_session.session_id,
        session.character_name,
        session.turn_count,
    )


# ---------------------------------------------------------------------------
# Solo post-processing (mirrors bot/client.py _solo_post_process)
# ---------------------------------------------------------------------------


async def _solo_post_process(
    session: Any, pipeline_result: dict, turn_number: int
) -> None:
    """Post-process pipeline results for solo-specific tracking.

    Delegates to the canonical implementation in bot.client to avoid
    duplicating ~70 lines of chaos/thread/NPC/faction logic.
    Non-blocking — errors are logged and swallowed.
    """
    try:
        from bot.client import _solo_post_process as _bot_post_process
        await _bot_post_process(session, pipeline_result, turn_number)
    except Exception as e:
        logger.warning("Solo/Web post-processing error (non-blocking): %s", e)


# ---------------------------------------------------------------------------
# Null context manager (for when no processing lock exists)
# ---------------------------------------------------------------------------


class _nullcontext:
    """Async context manager that does nothing (fallback when lock is None)."""

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        pass
