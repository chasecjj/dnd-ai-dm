"""
StateManager — Async MongoDB service for all mechanical game state.

Every write passes through Pydantic validation. Raw dicts and raw JSON
strings are never written directly. This is the single source of truth
for character stats, quest status, NPC records, world clock, and consequences.

The Obsidian vault remains the narrative layer (session prose, lore text).
MongoDB is the mechanical layer.

Requires:
  - MONGODB_URI in .env (default: mongodb://localhost:27017)
  - Database name: dnd_ai_dm (configurable)
"""

import os
import re
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone

from pydantic import ValidationError

logger = logging.getLogger("StateManager")

# ---------------------------------------------------------------------------
# Lazy motor import — allows the rest of the codebase to load even if
# MongoDB is not installed or not running. StateManager methods will
# raise clear errors if called without a connection.
# ---------------------------------------------------------------------------
try:
    from motor.motor_asyncio import AsyncIOMotorClient
    HAS_MOTOR = True
except ImportError:
    HAS_MOTOR = False
    AsyncIOMotorClient = None  # type: ignore[assignment,misc]

from models.characters import Character, NPCModel
from models.world_state import WorldClock, Consequence, GameEvent
from models.quests import QuestModel
from models.locations import LocationModel
from models.session import SessionLog
from models.chronicler_output import ChroniclerOutput


class StateManager:
    """Async MongoDB-backed state manager with Pydantic validation on every write.

    Collections:
        characters  — Player characters (party members)
        npcs        — Non-Player Characters
        quests      — Active, completed, and failed quests
        locations   — Campaign locations
        world_clock — Single document: the current in-game date/time
        consequences — Delayed world events
        events      — Append-only game event log
        sessions    — Session log metadata
    """

    def __init__(
        self,
        uri: Optional[str] = None,
        db_name: str = "dnd_ai_dm",
    ):
        self.uri = uri or os.getenv("MONGODB_URI", "mongodb://localhost:27017")
        self.db_name = db_name
        self._client: Any = None
        self._db: Any = None

    # ------------------------------------------------------------------
    # Connection
    # ------------------------------------------------------------------

    async def connect(self) -> bool:
        """Connect to MongoDB. Returns True on success."""
        if not HAS_MOTOR:
            logger.error(
                "motor is not installed. Run: pip install motor"
            )
            return False
        try:
            self._client = AsyncIOMotorClient(self.uri)
            # Verify connectivity
            await self._client.admin.command("ping")
            self._db = self._client[self.db_name]
            logger.info(f"StateManager connected to MongoDB: {self.db_name}")
            return True
        except Exception as e:
            logger.error(f"MongoDB connection failed: {e}")
            self._client = None
            self._db = None
            return False

    async def close(self):
        """Close the MongoDB connection."""
        if self._client:
            self._client.close()
            self._client = None
            self._db = None

    @property
    def is_connected(self) -> bool:
        return self._db is not None

    def _require_connection(self):
        if not self.is_connected:
            raise RuntimeError("StateManager is not connected to MongoDB.")

    # ------------------------------------------------------------------
    # Characters (Party Members)
    # ------------------------------------------------------------------

    async def get_character(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a character by name (case-insensitive)."""
        self._require_connection()
        doc = await self._db.characters.find_one(
            {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
        )
        if doc:
            doc.pop("_id", None)
        return doc

    async def get_all_characters(self) -> List[Dict[str, Any]]:
        """Get all party members."""
        self._require_connection()
        cursor = self._db.characters.find()
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def upsert_character(self, data: Dict[str, Any]) -> bool:
        """Validate and upsert a character. Returns True on success."""
        self._require_connection()
        try:
            model = Character.model_validate(data)
            doc = model.model_dump(by_alias=False)
            await self._db.characters.update_one(
                {"name": doc["name"]},
                {"$set": doc},
                upsert=True,
            )
            return True
        except ValidationError as e:
            logger.error(f"Character validation failed: {e}")
            return False

    async def patch_character(self, name: str, updates: Dict[str, Any]) -> bool:
        """Apply a partial update to a character (merge + validate)."""
        self._require_connection()
        existing = await self.get_character(name)
        if not existing:
            logger.warning(f"Character not found for patch: {name}")
            return False
        merged = {**existing, **updates}
        return await self.upsert_character(merged)

    # ------------------------------------------------------------------
    # NPCs
    # ------------------------------------------------------------------

    async def get_npc(self, name: str) -> Optional[Dict[str, Any]]:
        self._require_connection()
        doc = await self._db.npcs.find_one(
            {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
        )
        if doc:
            doc.pop("_id", None)
        return doc

    async def get_all_npcs(self) -> List[Dict[str, Any]]:
        """Get all NPCs."""
        self._require_connection()
        cursor = self._db.npcs.find()
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def get_npcs_at_location(self, location: str) -> List[Dict[str, Any]]:
        self._require_connection()
        cursor = self._db.npcs.find(
            {"location": {"$regex": re.escape(location), "$options": "i"}, "alive": True}
        )
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def upsert_npc(self, data: Dict[str, Any]) -> bool:
        self._require_connection()
        try:
            model = NPCModel.model_validate(data)
            doc = model.model_dump()
            await self._db.npcs.update_one(
                {"name": doc["name"]},
                {"$set": doc},
                upsert=True,
            )
            return True
        except ValidationError as e:
            logger.error(f"NPC validation failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Quests
    # ------------------------------------------------------------------

    async def get_all_quests(self) -> List[Dict[str, Any]]:
        """Get all quests regardless of status."""
        self._require_connection()
        cursor = self._db.quests.find()
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def get_active_quests(self) -> List[Dict[str, Any]]:
        self._require_connection()
        cursor = self._db.quests.find({"status": "active"})
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def upsert_quest(self, data: Dict[str, Any]) -> bool:
        self._require_connection()
        try:
            model = QuestModel.model_validate(data)
            doc = model.model_dump()
            await self._db.quests.update_one(
                {"name": doc["name"]},
                {"$set": doc},
                upsert=True,
            )
            return True
        except ValidationError as e:
            logger.error(f"Quest validation failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Locations
    # ------------------------------------------------------------------

    async def get_location(self, name: str) -> Optional[Dict[str, Any]]:
        self._require_connection()
        doc = await self._db.locations.find_one(
            {"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}}
        )
        if doc:
            doc.pop("_id", None)
        return doc

    async def upsert_location(self, data: Dict[str, Any]) -> bool:
        self._require_connection()
        try:
            model = LocationModel.model_validate(data)
            doc = model.model_dump()
            await self._db.locations.update_one(
                {"name": doc["name"]},
                {"$set": doc},
                upsert=True,
            )
            return True
        except ValidationError as e:
            logger.error(f"Location validation failed: {e}")
            return False

    # ------------------------------------------------------------------
    # World Clock
    # ------------------------------------------------------------------

    async def get_world_clock(self) -> Dict[str, Any]:
        self._require_connection()
        doc = await self._db.world_clock.find_one({"_type": "clock"})
        if doc:
            doc.pop("_id", None)
            doc.pop("_type", None)
            return doc
        return {"current_date": "", "time_of_day": "morning", "session": 0, "current_location": "Unknown"}

    async def update_world_clock(self, data: Dict[str, Any]) -> bool:
        self._require_connection()
        try:
            model = WorldClock.model_validate(data)
            doc = model.model_dump()
            doc["_type"] = "clock"
            await self._db.world_clock.update_one(
                {"_type": "clock"},
                {"$set": doc},
                upsert=True,
            )
            return True
        except ValidationError as e:
            logger.error(f"WorldClock validation failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Consequences
    # ------------------------------------------------------------------

    async def get_pending_consequences(self) -> List[Dict[str, Any]]:
        """Get all pending consequences (regardless of trigger session)."""
        self._require_connection()
        cursor = self._db.consequences.find({"status": "pending"})
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def get_due_consequences(self, current_session: int) -> List[Dict[str, Any]]:
        self._require_connection()
        cursor = self._db.consequences.find(
            {"trigger_session": {"$lte": current_session}, "status": "pending"}
        )
        results = []
        async for doc in cursor:
            doc.pop("_id", None)
            results.append(doc)
        return results

    async def add_consequence(self, data: Dict[str, Any]) -> bool:
        self._require_connection()
        try:
            model = Consequence.model_validate(data)
            doc = model.model_dump()
            doc["status"] = "pending"
            await self._db.consequences.insert_one(doc)
            return True
        except ValidationError as e:
            logger.error(f"Consequence validation failed: {e}")
            return False

    async def resolve_consequence(self, event_text: str, session: int) -> bool:
        self._require_connection()
        result = await self._db.consequences.update_one(
            {"event": {"$regex": re.escape(event_text), "$options": "i"}, "status": "pending"},
            {"$set": {"status": "resolved", "resolved_session": session}},
        )
        return result.modified_count > 0

    # ------------------------------------------------------------------
    # Events (append-only log)
    # ------------------------------------------------------------------

    async def log_event(self, data: Dict[str, Any]) -> bool:
        self._require_connection()
        try:
            model = GameEvent.model_validate(data)
            doc = model.model_dump()
            # Ensure timestamp is serializable
            if isinstance(doc.get("timestamp"), datetime):
                doc["timestamp"] = doc["timestamp"].isoformat()
            await self._db.events.insert_one(doc)
            return True
        except ValidationError as e:
            logger.error(f"GameEvent validation failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Sessions
    # ------------------------------------------------------------------

    async def upsert_session(self, data: Dict[str, Any]) -> bool:
        self._require_connection()
        try:
            model = SessionLog.model_validate(data)
            doc = model.model_dump()
            await self._db.sessions.update_one(
                {"session_number": doc["session_number"]},
                {"$set": doc},
                upsert=True,
            )
            return True
        except ValidationError as e:
            logger.error(f"SessionLog validation failed: {e}")
            return False

    # ------------------------------------------------------------------
    # Chronicler Integration — THE critical method
    # ------------------------------------------------------------------

    async def apply_chronicler_output(self, output: ChroniclerOutput, session: int) -> Dict[str, Any]:
        """Apply a validated ChroniclerOutput to the database.

        This is the ONLY method that writes Chronicler results.
        It accepts a ChroniclerOutput object — NEVER raw text or a plain dict.
        If the LLM returned garbage, model_validate_json() would have already
        raised ValidationError before this method is ever called.

        Returns a summary dict of what was applied.
        """
        self._require_connection()
        summary = {"events": 0, "characters": 0, "npcs": 0, "quests": 0, "locations": 0, "consequences": 0, "clock": False}

        # 1. Log events
        for event in output.events:
            await self.log_event({
                "session": session,
                "description": event.description,
                "impact": event.impact,
                "event_type": event.type,
            })
            summary["events"] += 1

        # 2. Patch characters
        for cu in output.character_updates:
            updates = cu.model_dump(exclude_none=True, exclude={"name"})
            if updates:
                success = await self.patch_character(cu.name, updates)
                if success:
                    summary["characters"] += 1

        # 3. Patch NPCs
        for nu in output.npc_updates:
            updates = nu.model_dump(exclude_none=True, exclude={"name"})
            if updates:
                existing = await self.get_npc(nu.name)
                if existing:
                    merged = {**existing, **updates}
                    await self.upsert_npc(merged)
                else:
                    # New NPC — create with defaults
                    await self.upsert_npc({"name": nu.name, **updates})
                summary["npcs"] += 1

        # 4. Patch quests
        for qu in output.quest_updates:
            updates = qu.model_dump(exclude_none=True, exclude={"name"})
            if updates:
                existing_quests = await self._db.quests.find_one(
                    {"name": {"$regex": f"^{re.escape(qu.name)}$", "$options": "i"}}
                )
                if existing_quests:
                    existing_quests.pop("_id", None)
                    merged = {**existing_quests, **updates}
                    success = await self.upsert_quest(merged)
                    if success:
                        summary["quests"] += 1
                else:
                    logger.warning(f"Quest not found for update, skipping: {qu.name}")

        # 5. Patch locations
        for lu in output.location_updates:
            updates = lu.model_dump(exclude_none=True, exclude={"name"})
            if updates:
                existing = await self.get_location(lu.name)
                if existing:
                    merged = {**existing, **updates}
                    await self.upsert_location(merged)
                summary["locations"] += 1

        # 6. Update world clock
        if output.world_clock:
            clock_data = output.world_clock.model_dump(exclude_none=True)
            if clock_data:
                current = await self.get_world_clock()
                merged = {**current, **clock_data, "session": session}
                await self.update_world_clock(merged)
                summary["clock"] = True

        # 7. Add new consequences
        for ce in output.new_consequences:
            await self.add_consequence(ce.model_dump())
            summary["consequences"] += 1

        logger.info(f"Chronicler output applied: {summary}")
        return summary
