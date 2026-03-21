"""
SoloSessionManager — Tracks active solo (1-on-1) adventure sessions.

Pure Python — no Discord imports. Each solo session maps a Discord thread
to a single player character for between-session adventures.

Features:
- Per-session ConversationHistory (Phase 0.1 — prevents concurrent corruption)
- Processing locks on manager, not model (Phase 0.2 — asyncio-safe)
- Snapshot stack for multi-turn undo (Phase 3.2a)
- Session state persistence to MongoDB (Phase 2.0)
- Chaos, threads, NPCs, factions, consequences tracking
- Session timeout detection (Phase 3.2b)
- Schema versioning for snapshots (Phase 3.2c)
"""

import asyncio
import time
import uuid
import logging
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any

from pydantic import BaseModel, Field

logger = logging.getLogger("SoloSession")

# Current snapshot schema version — increment on breaking changes
SNAPSHOT_SCHEMA_VERSION = 3

# Maximum undo stack depth (set high for testing phase)
MAX_SNAPSHOT_DEPTH = 999


class SoloTurnSnapshot(BaseModel):
    """Snapshot of state before a turn, for multi-turn undo."""

    turn_number: int
    history_snapshot: List[dict]  # Serialized ConversationHistory entries
    location_before: str  # Location before this turn
    player_input: str  # What the player said
    narrative: str = ""  # What the AI responded
    recent_narratives_snapshot: List[dict] = Field(default_factory=list)  # Narrative window before this turn
    scene_state_snapshot: dict = Field(default_factory=dict)  # Scene state before this turn
    schema_version: int = SNAPSHOT_SCHEMA_VERSION


class SoloSession(BaseModel):
    """Tracks a single active solo adventure session.

    Each session owns its own ConversationHistory instance to prevent
    concurrent sessions from corrupting each other's state.
    """

    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    discord_user_id: int
    thread_id: int
    character_name: str
    started_at: float = Field(default_factory=time.time)
    turn_count: int = 0
    current_location: str
    session_number: int  # Campaign session this solo runs alongside
    solo_log_path: Optional[str] = None  # Vault relative path for the log file

    # Multi-turn undo stack (Phase 3.2a) — replaces single last_snapshot
    snapshot_stack: List[SoloTurnSnapshot] = Field(default_factory=list)

    # Solo engine state (Phase 1-3)
    active_consequences: List[str] = Field(default_factory=list)
    chaos_factor: int = 5  # 1-9, for ChaosTracker
    active_threads: List[dict] = Field(default_factory=list)
    encountered_npcs: List[dict] = Field(default_factory=list)
    factions: List[dict] = Field(default_factory=list)

    # Recent narrative window (Phase 2 — continuity fix)
    # Each entry: {"turn": int, "player_input": str, "narrative": str}
    recent_narratives: List[dict] = Field(default_factory=list)

    # Scene state snapshot (Phase 3 — structural continuity)
    # Dict matching SceneState schema, maintained by chronicler
    scene_state_data: dict = Field(default_factory=dict)

    # Queued narrative directives that didn't make the cut last turn
    queued_directives: List[dict] = Field(default_factory=list)

    # Pause/resume support (Phase 4.0)
    is_paused: bool = False
    conversation_history_data: List[dict] = Field(default_factory=list)  # Full history for pause/resume

    # Session timeout tracking (Phase 3.2b)
    last_activity: float = Field(default_factory=time.time)

    # Backward compatibility: expose last_snapshot as the top of the stack
    @property
    def last_snapshot(self) -> Optional[SoloTurnSnapshot]:
        """Get the most recent snapshot (top of undo stack)."""
        return self.snapshot_stack[-1] if self.snapshot_stack else None

    def push_snapshot(self, snapshot: SoloTurnSnapshot):
        """Push a snapshot onto the undo stack, maintaining max depth."""
        self.snapshot_stack.append(snapshot)
        if len(self.snapshot_stack) > MAX_SNAPSHOT_DEPTH:
            self.snapshot_stack.pop(0)  # Remove oldest

    def pop_snapshot(self) -> Optional[SoloTurnSnapshot]:
        """Pop the most recent snapshot for undo. Returns None if stack is empty."""
        return self.snapshot_stack.pop() if self.snapshot_stack else None

    def touch(self):
        """Update last_activity timestamp."""
        self.last_activity = time.time()

    def push_narrative(self, turn: int, player_input: str, narrative: str):
        """Store a turn's narrative for the sliding window. Keeps last 5."""
        self.recent_narratives.append({
            "turn": turn,
            "player_input": player_input,
            "narrative": narrative,
        })
        if len(self.recent_narratives) > 5:
            self.recent_narratives.pop(0)

    def to_dict(self) -> dict:
        """Serialize for MongoDB persistence."""
        return {
            "id": self.id,
            "discord_user_id": self.discord_user_id,
            "thread_id": self.thread_id,
            "character_name": self.character_name,
            "started_at": self.started_at,
            "turn_count": self.turn_count,
            "current_location": self.current_location,
            "session_number": self.session_number,
            "solo_log_path": self.solo_log_path,
            "snapshot_stack": [s.model_dump() for s in self.snapshot_stack],
            "active_consequences": self.active_consequences,
            "chaos_factor": self.chaos_factor,
            "active_threads": self.active_threads,
            "encountered_npcs": self.encountered_npcs,
            "factions": self.factions,
            "recent_narratives": self.recent_narratives,
            "scene_state_data": self.scene_state_data,
            "queued_directives": self.queued_directives,
            "is_paused": self.is_paused,
            "conversation_history_data": self.conversation_history_data,
            "last_activity": self.last_activity,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SoloSession":
        """Deserialize from MongoDB document."""
        # Restore snapshot stack with schema version checking
        raw_snapshots = data.get("snapshot_stack", [])
        snapshots = []
        for snap_data in raw_snapshots:
            version = snap_data.get("schema_version", 1)
            if version != SNAPSHOT_SCHEMA_VERSION:
                logger.warning(
                    f"Snapshot schema mismatch: got v{version}, expected v{SNAPSHOT_SCHEMA_VERSION}. "
                    f"Skipping snapshot for turn {snap_data.get('turn_number', '?')}."
                )
                continue
            snapshots.append(SoloTurnSnapshot(**snap_data))

        return cls(
            id=data.get("id", str(uuid.uuid4())),
            discord_user_id=data["discord_user_id"],
            thread_id=data["thread_id"],
            character_name=data["character_name"],
            started_at=data.get("started_at", time.time()),
            turn_count=data.get("turn_count", 0),
            current_location=data.get("current_location", "Unknown"),
            session_number=data.get("session_number", 0),
            solo_log_path=data.get("solo_log_path"),
            snapshot_stack=snapshots,
            active_consequences=data.get("active_consequences", []),
            chaos_factor=data.get("chaos_factor", 5),
            active_threads=data.get("active_threads", []),
            encountered_npcs=data.get("encountered_npcs", []),
            factions=data.get("factions", []),
            recent_narratives=data.get("recent_narratives", []),
            scene_state_data=data.get("scene_state_data", {}),
            queued_directives=data.get("queued_directives", []),
            is_paused=data.get("is_paused", False),
            conversation_history_data=data.get("conversation_history_data", []),
            last_activity=data.get("last_activity", time.time()),
        )


class SoloSessionManager:
    """Manages active solo sessions.

    Thread-safe via asyncio.Lock for session registry mutations.
    Per-session processing locks prevent concurrent pipeline runs
    from corrupting state (Phase 0.2).

    Optionally backed by MongoDB for persistence across restarts (Phase 2.0).
    """

    SESSION_TIMEOUT_HOURS = 24  # Auto-end sessions idle this long

    def __init__(self, state_manager=None):
        self._sessions: Dict[int, SoloSession] = {}  # thread_id -> session
        self._lock = asyncio.Lock()
        self._processing_locks: Dict[int, asyncio.Lock] = {}  # thread_id -> lock
        self._histories: Dict[int, Any] = {}  # thread_id -> ConversationHistory
        self._state_manager = state_manager  # Optional MongoDB for persistence

        # Web session UUID → int key mapping (Quest Mirror)
        self._web_session_keys: Dict[str, int] = {}  # session.id -> negative int key
        self._next_web_key: int = 0  # Decremented for each new web session

    async def start_session(
        self,
        discord_user_id: int,
        thread_id: int,
        character_name: str,
        current_location: str,
        session_number: int,
    ) -> SoloSession:
        """Register a new solo session with its own history and processing lock."""
        async with self._lock:
            session = SoloSession(
                discord_user_id=discord_user_id,
                thread_id=thread_id,
                character_name=character_name,
                current_location=current_location,
                session_number=session_number,
            )
            self._sessions[thread_id] = session
            self._processing_locks[thread_id] = asyncio.Lock()

            # Create per-session ConversationHistory (Phase 0.1)
            from tools.context_assembler import ConversationHistory
            self._histories[thread_id] = ConversationHistory()

            # Persist to MongoDB if available
            await self._persist_session(session)

            logger.info(
                f"Solo session started: {character_name} in thread {thread_id}"
            )
            return session

    async def end_session(self, thread_id: int) -> Optional[SoloSession]:
        """End and remove a solo session. Returns the session or None."""
        async with self._lock:
            session = self._sessions.pop(thread_id, None)
            self._processing_locks.pop(thread_id, None)
            self._histories.pop(thread_id, None)

            if session:
                # Remove from MongoDB
                await self._delete_session(thread_id)
                logger.info(
                    f"Solo session ended: {session.character_name} "
                    f"({session.turn_count} turns)"
                )
            return session

    def get_session(self, thread_id: int) -> Optional[SoloSession]:
        """Get the solo session for a thread (sync, no lock needed for reads)."""
        return self._sessions.get(thread_id)

    def get_history(self, thread_id: int):
        """Get the per-session ConversationHistory for a thread."""
        return self._histories.get(thread_id)

    def get_processing_lock(self, thread_id: int) -> Optional[asyncio.Lock]:
        """Get the processing lock for a session (prevents concurrent pipeline runs)."""
        return self._processing_locks.get(thread_id)

    def get_by_user(self, user_id: int) -> Optional[SoloSession]:
        """Get a user's active solo session, if any."""
        for session in self._sessions.values():
            if session.discord_user_id == user_id:
                return session
        return None

    def get_by_character(self, character_name: str) -> Optional[SoloSession]:
        """Get an active solo session for a specific character."""
        char_lower = character_name.lower()
        for session in self._sessions.values():
            if session.character_name.lower() == char_lower:
                return session
        return None

    def is_solo_thread(self, thread_id: int) -> bool:
        """Check if a thread is an active solo session."""
        return thread_id in self._sessions

    async def increment_turn(self, thread_id: int):
        """Increment the turn counter and update activity timestamp."""
        async with self._lock:
            session = self._sessions.get(thread_id)
            if session:
                session.turn_count += 1
                session.touch()
                await self._persist_session(session)

    def all_active(self) -> List[SoloSession]:
        """Return all active solo sessions."""
        return list(self._sessions.values())

    def get_timed_out_sessions(self) -> List[SoloSession]:
        """Get sessions that have been idle longer than the timeout threshold."""
        cutoff = time.time() - (self.SESSION_TIMEOUT_HOURS * 3600)
        return [s for s in self._sessions.values() if s.last_activity < cutoff]

    async def restore_active(self):
        """Restore active sessions from MongoDB on bot restart (Phase 2.0)."""
        if not self._state_manager or not self._state_manager.is_connected:
            return

        try:
            db = self._state_manager._db
            cursor = db.solo_sessions.find({"is_paused": {"$ne": True}})
            count = 0
            async for doc in cursor:
                try:
                    session = SoloSession.from_dict(doc)
                    self._sessions[session.thread_id] = session
                    self._processing_locks[session.thread_id] = asyncio.Lock()

                    from tools.context_assembler import ConversationHistory
                    history = ConversationHistory()
                    # Restore history from the latest snapshot if available
                    if session.snapshot_stack:
                        latest = session.snapshot_stack[-1]
                        from tools.context_assembler import MemoryEntry
                        for entry_data in latest.history_snapshot:
                            history.entries.append(MemoryEntry(
                                text=entry_data["text"],
                                impact=entry_data["base_impact"],
                                turns_ago=entry_data["turns_ago"],
                                timestamp=entry_data.get("timestamp", 0.0),
                                character=entry_data.get("character"),
                                location=entry_data.get("location"),
                            ))
                    self._histories[session.thread_id] = history
                    count += 1
                except Exception as e:
                    logger.warning(f"Failed to restore solo session: {e}")

            if count:
                logger.info(f"Restored {count} active solo sessions from MongoDB")
        except Exception as e:
            logger.error(f"Failed to restore solo sessions: {e}")

    async def pause_session(self, thread_id: int) -> Optional[SoloSession]:
        """Pause a session: serialize history, persist to MongoDB, remove from active memory.

        The session stays in MongoDB with is_paused=True so it can be resumed later.
        Unlike end_session(), the DB doc is NOT deleted.
        """
        async with self._lock:
            session = self._sessions.get(thread_id)
            if not session:
                return None

            # Serialize the full ConversationHistory into the session
            history = self._histories.get(thread_id)
            if history and hasattr(history, 'entries'):
                session.conversation_history_data = [
                    {
                        "text": e.text,
                        "base_impact": e.base_impact,
                        "turns_ago": e.turns_ago,
                        "timestamp": e.timestamp,
                        "character": e.character,
                        "location": e.location,
                    }
                    for e in history.entries
                ]

            session.is_paused = True
            session.touch()

            # Persist to MongoDB (with paused flag)
            await self._persist_session(session)

            # Remove from active memory (free resources)
            self._sessions.pop(thread_id, None)
            self._processing_locks.pop(thread_id, None)
            self._histories.pop(thread_id, None)

            logger.info(
                f"Solo session paused: {session.character_name} "
                f"(turn {session.turn_count}, thread {thread_id})"
            )
            return session

    # ------------------------------------------------------------------
    # Web session support (Quest Mirror)
    # ------------------------------------------------------------------

    async def start_web_session(
        self,
        character_name: str,
        current_location: str,
        session_number: int,
    ) -> Optional[SoloSession]:
        """Register a new web (Quest Mirror) solo session.

        Uses negative integer keys to avoid collision with Discord snowflake IDs.
        Returns None if the character already has an active session (any source).
        """
        async with self._lock:
            # Atomic duplicate check — no two sessions for the same character
            if self._find_by_character_unlocked(character_name) is not None:
                logger.warning(
                    f"Web session rejected: {character_name} already has an active session"
                )
                return None

            # Allocate a unique negative key
            self._next_web_key -= 1
            web_key = self._next_web_key

            session = SoloSession(
                discord_user_id=0,
                thread_id=web_key,
                character_name=character_name,
                current_location=current_location,
                session_number=session_number,
            )
            self._sessions[web_key] = session
            self._processing_locks[web_key] = asyncio.Lock()

            # Create per-session ConversationHistory (same as Discord sessions)
            from tools.context_assembler import ConversationHistory
            self._histories[web_key] = ConversationHistory()

            # Map session UUID → negative int key for web handler lookups
            self._web_session_keys[session.id] = web_key

            logger.info(
                f"Web solo session started: {character_name} (key={web_key}, id={session.id})"
            )
            return session

    def _find_by_character_unlocked(self, character_name: str) -> Optional[SoloSession]:
        """Find an active session by character name (case-insensitive).

        Must be called under self._lock.
        """
        char_lower = character_name.lower()
        for session in self._sessions.values():
            if session.character_name.lower() == char_lower:
                return session
        return None

    def get_by_session_id(self, session_id: str) -> Optional[SoloSession]:
        """Get a web session by its UUID (session.id)."""
        web_key = self._web_session_keys.get(session_id)
        if web_key is None:
            return None
        return self._sessions.get(web_key)

    def get_web_history(self, session_id: str):
        """Get the ConversationHistory for a web session by UUID."""
        web_key = self._web_session_keys.get(session_id)
        if web_key is None:
            return None
        return self._histories.get(web_key)

    def get_web_processing_lock(self, session_id: str) -> Optional[asyncio.Lock]:
        """Get the processing lock for a web session by UUID."""
        web_key = self._web_session_keys.get(session_id)
        if web_key is None:
            return None
        return self._processing_locks.get(web_key)

    def get_web_thread_key(self, session_id: str) -> Optional[int]:
        """Get the negative int thread key for a web session UUID.

        Needed by the web handler to set _solo_thread_id in GameState.
        """
        return self._web_session_keys.get(session_id)

    async def end_web_session(self, session_id: str) -> Optional[SoloSession]:
        """End and remove a web session by UUID. Returns the session or None."""
        async with self._lock:
            web_key = self._web_session_keys.pop(session_id, None)
            if web_key is None:
                return None

            session = self._sessions.pop(web_key, None)
            self._processing_locks.pop(web_key, None)
            self._histories.pop(web_key, None)

            if session:
                logger.info(
                    f"Web solo session ended: {session.character_name} "
                    f"({session.turn_count} turns, key={web_key})"
                )
            return session

    async def resume_session(self, thread_id: int) -> Optional[SoloSession]:
        """Resume a paused session from MongoDB, restoring full state."""
        if not self._state_manager or not self._state_manager.is_connected:
            return None

        async with self._lock:
            try:
                db = self._state_manager._db
                doc = await db.solo_sessions.find_one(
                    {"thread_id": thread_id, "is_paused": True}
                )
                if not doc:
                    return None

                session = SoloSession.from_dict(doc)
                session.is_paused = False
                session.touch()

                # Rebuild ConversationHistory from stored data
                from tools.context_assembler import ConversationHistory, MemoryEntry
                history = ConversationHistory()
                for entry_data in session.conversation_history_data:
                    history.entries.append(MemoryEntry(
                        text=entry_data["text"],
                        impact=entry_data["base_impact"],
                        turns_ago=entry_data["turns_ago"],
                        timestamp=entry_data.get("timestamp", 0.0),
                        character=entry_data.get("character"),
                        location=entry_data.get("location"),
                    ))

                # Clear the serialized history data (now live in memory)
                session.conversation_history_data = []

                # Register in active memory
                self._sessions[thread_id] = session
                self._processing_locks[thread_id] = asyncio.Lock()
                self._histories[thread_id] = history

                # Persist updated state (is_paused=False)
                await self._persist_session(session)

                logger.info(
                    f"Solo session resumed: {session.character_name} "
                    f"(turn {session.turn_count}, thread {thread_id})"
                )
                return session
            except Exception as e:
                logger.error(f"Failed to resume solo session: {e}")
                return None

    async def get_paused_session(
        self, user_id: int = None, character_name: str = None
    ) -> Optional[dict]:
        """Check MongoDB for a paused session matching user or character.

        Returns the raw dict (not loaded into active memory) so the caller
        can decide whether to resume.
        """
        if not self._state_manager or not self._state_manager.is_connected:
            return None

        try:
            db = self._state_manager._db
            query: dict = {"is_paused": True}
            if user_id is not None:
                query["discord_user_id"] = user_id
            if character_name is not None:
                query["character_name"] = {"$regex": f"^{character_name}$", "$options": "i"}
            return await db.solo_sessions.find_one(query)
        except Exception as e:
            logger.warning(f"Failed to check for paused session: {e}")
            return None

    async def _persist_session(self, session: SoloSession):
        """Upsert session to MongoDB (async, non-blocking on failure)."""
        if not self._state_manager or not self._state_manager.is_connected:
            return
        try:
            db = self._state_manager._db
            await db.solo_sessions.replace_one(
                {"thread_id": session.thread_id},
                session.to_dict(),
                upsert=True,
            )
        except Exception as e:
            logger.warning(f"Failed to persist solo session: {e}")

    async def _delete_session(self, thread_id: int):
        """Remove session from MongoDB."""
        if not self._state_manager or not self._state_manager.is_connected:
            return
        try:
            db = self._state_manager._db
            await db.solo_sessions.delete_one({"thread_id": thread_id})
        except Exception as e:
            logger.warning(f"Failed to delete solo session from MongoDB: {e}")
