"""
CharacterKnowledge — Schema for accumulated character insights.

The Chronicler extracts personality traits, backstory fragments, relationship
changes, and other observations from gameplay. These persist across sessions
and feed back into richer AI context.
"""

from typing import List
from pydantic import BaseModel, field_validator


class CharacterInsight(BaseModel):
    """A single insight extracted by the Chronicler."""

    character_name: str
    observation: str  # e.g., "Showed reverence at the shrine of Tyr"
    category: str = "personality"

    @field_validator("category")
    @classmethod
    def validate_category(cls, v):
        valid = {
            "personality",
            "backstory",
            "relationship",
            "goal",
            "fear",
            "habit",
            "preference",
        }
        return v.lower() if v.lower() in valid else "personality"


class CharacterKnowledge(BaseModel):
    """Full accumulated knowledge about a character."""

    character_name: str
    observations: List[CharacterInsight] = []
    last_updated_session: int = 0
