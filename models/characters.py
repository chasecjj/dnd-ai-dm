"""
Character and NPC schemas — validated game entities.

These models gate ALL writes to the characters and npcs collections.
"""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, field_validator


class Character(BaseModel):
    """Schema for a player character (party member)."""

    name: str
    race: str = "Unknown"
    char_class: str = Field(alias="class", default="Unknown")
    level: int = Field(default=1, ge=1, le=20)
    hp_current: int
    hp_max: int = Field(ge=1)
    ac: int = Field(ge=0)
    pronouns: str = ""
    conditions: List[str] = []
    spell_slots_used: int = Field(default=0, ge=0)
    spell_slots_max: int = Field(default=0, ge=0)
    lay_on_hands_pool: Optional[int] = None
    inventory_notes: str = ""
    backstory_hooks: List[str] = []
    foundry_uuid: Optional[str] = None

    model_config = {"extra": "allow", "populate_by_name": True}

    @field_validator("hp_current")
    @classmethod
    def hp_cannot_exceed_max(cls, v, info):
        hp_max = info.data.get("hp_max")
        if hp_max is not None and v > hp_max:
            return hp_max
        return v


class NPCModel(BaseModel):
    """Schema for a Non-Player Character."""

    name: str
    race: str = "Unknown"
    role: str = "Commoner"
    location: str = "Unknown"
    faction: str = "unaffiliated"
    disposition: str = "neutral"
    alive: bool = True
    tags: List[str] = []
    last_seen_session: Optional[int] = None
    notes: str = ""

    @field_validator("disposition")
    @classmethod
    def validate_disposition(cls, v):
        valid = {"friendly", "neutral", "hostile", "unknown"}
        if v.lower() not in valid:
            return "neutral"
        return v.lower()

    model_config = {"extra": "allow"}
