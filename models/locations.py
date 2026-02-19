"""
Location schema — tracks places in the campaign world.
"""

from typing import List
from pydantic import BaseModel, field_validator


class LocationModel(BaseModel):
    """Schema for a Location."""

    name: str
    type: str = "unknown"
    region: str = "Unknown"
    status: str = "active"
    atmosphere: str = "neutral"
    tags: List[str] = []
    connected_locations: List[str] = []

    @field_validator("status")
    @classmethod
    def validate_status(cls, v):
        valid = {"active", "destroyed", "hidden", "abandoned"}
        if v.lower() not in valid:
            return "active"
        return v.lower()

    model_config = {"extra": "allow"}
