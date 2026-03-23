"""BattleScar — record of a critical roll etched onto a character's die."""

from typing import Literal, Optional
from pydantic import BaseModel, Field


class BattleScar(BaseModel):
    """A scar on the d20 from a critical moment.

    Rendered as normal-map overlays: golden lines for nat 20s,
    dark grooves for nat 1s, ornate marks for crit kills.
    """

    face: int = Field(ge=1, le=20, description="Which d20 face bears the scar")
    scar_type: Literal["nat20", "nat1", "crit_kill"]
    character_name: str
    session_id: Optional[int] = None
    turn_number: Optional[int] = None
    created_at: Optional[str] = None
