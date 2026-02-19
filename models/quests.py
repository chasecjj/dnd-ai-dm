"""
Quest schema — tracks active, completed, and failed quests.
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator


class QuestModel(BaseModel):
    """Schema for a Quest."""

    name: str
    quest_giver: str = "Unknown"
    status: str = "active"
    objectives: List[str] = []
    completed_session: Optional[int] = None
    rewards: Dict[str, Any] = {}

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid = {"active", "completed", "failed", "on_hold"}
        if v.lower() not in valid:
            return "active"
        return v.lower()

    model_config = {"extra": "allow"}
