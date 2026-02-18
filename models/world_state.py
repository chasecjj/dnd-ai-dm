"""
World state schemas — clock, consequences, and the append-only event log.
"""

from typing import Optional
from datetime import datetime, timezone
from pydantic import BaseModel, Field, field_validator


class WorldClock(BaseModel):
    """The in-game date/time tracker."""

    current_date: str = ""
    time_of_day: str = "morning"
    session: int = Field(default=0, ge=0)
    current_location: str = "Unknown"

    @field_validator("time_of_day")
    @classmethod
    def validate_time(cls, v):
        valid = {"dawn", "morning", "afternoon", "evening", "night", "midnight"}
        if v.lower() not in valid:
            return "morning"
        return v.lower()

    model_config = {"extra": "allow"}


class Consequence(BaseModel):
    """A delayed world event that triggers at a future session."""

    trigger_session: int = Field(ge=0)
    event: str
    impact: int = Field(default=5, ge=1, le=10)
    notes: str = ""
    status: str = "pending"

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid = {"pending", "resolved", "cancelled"}
        if v.lower() not in valid:
            return "pending"
        return v.lower()

    model_config = {"extra": "allow"}


class GameEvent(BaseModel):
    """Append-only event log entry. Never modified after creation."""

    session: int = Field(ge=0)
    description: str
    impact: int = Field(default=5, ge=1, le=10)
    event_type: str = "flavor"
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("event_type")
    @classmethod
    def validate_event_type(cls, v):
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

    model_config = {"extra": "allow"}
