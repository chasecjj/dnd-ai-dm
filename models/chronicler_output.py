"""
ChroniclerOutput — The validation gate between LLM output and the database.

This is the single most important model in the system. Every Chronicler
write passes through `ChroniclerOutput.model_validate_json()`. If the
LLM returns garbage, ValidationError fires and NOTHING is written.

Zero partial corruption is possible.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class EventEntry(BaseModel):
    """A single event extracted from the exchange."""

    description: str
    impact: int = Field(default=5, ge=1, le=10)
    type: str = "flavor"

    @field_validator("type")
    @classmethod
    def validate_type(cls, v):
        valid = {
            "combat",
            "npc_interaction",
            "discovery",
            "movement",
            "flavor",
            "decision",
        }
        if v.lower() not in valid:
            return "flavor"
        return v.lower()


class CharacterUpdate(BaseModel):
    """Partial update to a player character's mechanical state."""

    name: str
    hp_current: Optional[int] = None
    conditions: Optional[List[str]] = None
    spell_slots_used: Optional[int] = None
    lay_on_hands_pool: Optional[int] = None
    # Allow extra fields for flexibility (e.g. temp_hp, death_saves)
    model_config = {"extra": "allow"}


class NPCUpdate(BaseModel):
    """Partial update to an NPC."""

    name: str
    disposition: Optional[str] = None
    alive: Optional[bool] = None
    location: Optional[str] = None
    last_seen_session: Optional[int] = None
    notes: Optional[str] = None

    @field_validator("disposition")
    @classmethod
    def validate_disposition(cls, v):
        if v is None:
            return v
        valid = {"friendly", "neutral", "hostile", "unknown"}
        if v.lower() not in valid:
            return "neutral"
        return v.lower()


class QuestUpdate(BaseModel):
    """Partial update to a quest."""

    name: str
    status: Optional[str] = None
    progress_note: Optional[str] = None
    completed_session: Optional[int] = None

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        if v is None:
            return v
        valid = {"active", "completed", "failed", "on_hold"}
        if v.lower() not in valid:
            return "active"
        return v.lower()


class LocationUpdate(BaseModel):
    """Partial update to a location."""

    name: str
    status: Optional[str] = None
    atmosphere: Optional[str] = None


class ClockUpdate(BaseModel):
    """Update to the world clock."""

    current_date: Optional[str] = None
    time_of_day: Optional[str] = None
    current_location: Optional[str] = None


class ConsequenceEntry(BaseModel):
    """A new delayed consequence to add to the queue."""

    trigger_session: int = Field(ge=0)
    event: str
    impact: int = Field(default=5, ge=1, le=10)
    notes: str = ""


class ChroniclerOutput(BaseModel):
    """The full structured output from the Chronicler LLM.

    This is the ONLY shape accepted by StateManager.apply_chronicler_output().
    If any field fails validation, the entire output is rejected.
    """

    events: List[EventEntry] = []
    character_updates: List[CharacterUpdate] = []
    npc_updates: List[NPCUpdate] = []
    quest_updates: List[QuestUpdate] = []
    location_updates: List[LocationUpdate] = []
    world_clock: Optional[ClockUpdate] = None
    new_consequences: List[ConsequenceEntry] = []
