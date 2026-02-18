"""
Session log schema — tracks individual game sessions.
"""

from pydantic import BaseModel, Field, field_validator


class SessionLog(BaseModel):
    """Schema for a Session Log entry."""

    session_number: int = Field(ge=0)
    real_date: str = ""
    ingame_date: str = ""
    status: str = "in_progress"
    location: str = ""

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid = {"in_progress", "completed", "cancelled"}
        if v.lower() not in valid:
            return "in_progress"
        return v.lower()

    model_config = {"extra": "allow"}
