"""
Pydantic v2 data models — the contract for all game state.

Every write to MongoDB passes through these models first.
If validation fails, nothing is written.
"""

from models.characters import Character, NPCModel
from models.world_state import WorldClock, Consequence, GameEvent
from models.quests import QuestModel
from models.locations import LocationModel
from models.session import SessionLog
from models.chronicler_output import (
    ChroniclerOutput,
    EventEntry,
    CharacterUpdate,
    NPCUpdate,
    QuestUpdate,
    LocationUpdate,
    ClockUpdate,
    ConsequenceEntry,
)

__all__ = [
    "Character",
    "NPCModel",
    "WorldClock",
    "Consequence",
    "GameEvent",
    "QuestModel",
    "LocationModel",
    "SessionLog",
    "ChroniclerOutput",
    "EventEntry",
    "CharacterUpdate",
    "NPCUpdate",
    "QuestUpdate",
    "LocationUpdate",
    "ClockUpdate",
    "ConsequenceEntry",
]
