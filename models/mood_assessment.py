"""MoodAssessment — structured emotional context for the pipeline."""

from typing import Literal, Optional
from pydantic import BaseModel, Field

MOOD_LITERALS = Literal[
    "combat", "horror", "wonder", "sorrow",
    "tension", "warmth", "dialogue", "neutral",
]


class MoodAssessment(BaseModel):
    """Structured mood output from the Mood Agent.

    Consumed by:
    - Storyteller: prose style, NPC dialogue tone
    - Quest Mirror backend: breath-group timing tags
    - Quest Mirror frontend: typography CSS classes
    """

    primary_mood: MOOD_LITERALS
    intensity: int = Field(ge=1, le=10, description="How strongly the mood is felt")
    secondary_mood: Optional[MOOD_LITERALS] = None
    npc_emotional_states: dict[str, str] = Field(
        default_factory=dict,
        description="NPC name -> emotional state string, max 5 entries",
    )
    environmental_tone: str = Field(
        description="Short prose describing the atmosphere: 'firelit intimacy', 'oppressive damp stone'",
    )
    typography_hint: Literal["combat", "horror", "wonder", "sorrow", "neutral"] = "neutral"
    breath_timing: Literal["urgent", "slow", "generous", "still", "conversational", "neutral"] = "neutral"
