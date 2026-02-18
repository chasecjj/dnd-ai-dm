"""
Data models for Vault entities using Pydantic for validation.
"""

from typing import List, Optional, Any, Dict
from pydantic import BaseModel, Field, field_validator

class PartyMember(BaseModel):
    """Schema for a party member file."""
    name: str
    race: str = "Unknown"
    char_class: str = Field(alias="class", default="Unknown")
    level: int = 1
    hp_current: int
    hp_max: int
    ac: int
    pronouns: str = ""
    conditions: List[str] = []
    spell_slots_used: int = 0
    spell_slots_max: int = 0
    lay_on_hands_pool: Optional[int] = None
    
    # Allow extra fields for flexibility
    model_config = {"extra": "allow"}

class NPC(BaseModel):
    """Schema for an NPC file."""
    name: str
    race: str = "Unknown"
    role: str = Field(alias="class", default="Commoner")
    location: str = "Unknown"
    faction: str = "unaffiliated"
    disposition: str = "neutral"
    status: str = "alive"
    alive: bool = True
    tags: List[str] = []
    last_seen_session: Optional[int] = None

    @field_validator('disposition')
    @classmethod
    def validate_disposition(cls, v):
        valid = ['friendly', 'neutral', 'hostile', 'unknown']
        if v.lower() not in valid:
            return 'neutral'
        return v.lower()

    model_config = {"extra": "allow"}

class Quest(BaseModel):
    """Schema for a Quest file."""
    name: str
    quest_giver: str = "Unknown"
    status: str = "active"
    completed_session: Optional[int] = None
    rewards: Dict[str, Any] = {}
    
    model_config = {"extra": "allow"}

class Location(BaseModel):
    """Schema for a Location file."""
    name: str
    type: str = "unknown"
    region: str = "Unknown"
    status: str = "active"
    atmosphere: str = "neutral"
    tags: List[str] = []

    model_config = {"extra": "allow"}

class SessionLog(BaseModel):
    """Schema for a Session Log file."""
    session_number: int
    real_date: str
    ingame_date: str
    status: str = "in_progress"
    
    model_config = {"extra": "allow"}
