"""
SceneState — Structured snapshot of the current scene for narrative continuity.

Maintained by the Chronicler after each turn. Injected into the Storyteller's
context as ground truth. Physical descriptions persist across turns unless
the narrative explicitly changes them — preventing description drift.
"""

from typing import List, Optional
from pydantic import BaseModel, Field


class SceneEntity(BaseModel):
    """A character or NPC present in the current scene."""

    name: str
    physical_description: str = ""   # "hulking, one yellow eye, matted fur"
    holding_items: list[str] = Field(default_factory=list)  # ["note", "club"]
    role_or_relationship: str = ""   # "Xanathar enforcer"
    current_demeanor: str = ""       # "wary but curious"


class SceneObject(BaseModel):
    """A notable object in play that might change hands or be referenced."""

    name: str
    holder: str = ""          # who has it, or "" for on ground/table
    description: str = ""     # "crinkled parchment with Zhent snake-wing mark"


class SceneState(BaseModel):
    """Canonical snapshot of the current scene — who's here, what they look like,
    who holds what, and spatial layout.

    Updated incrementally by the Chronicler. Physical descriptions carry forward
    unless the narrative explicitly changes them.
    """

    entities_present: List[SceneEntity] = Field(default_factory=list)
    objects_in_play: List[SceneObject] = Field(default_factory=list)
    spatial_notes: str = ""   # "PC at corner booth, Grigor at bar"
    turn_updated: int = 0
