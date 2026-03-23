"""
Mood Agent — Produces structured emotional context for the pipeline.

Pure Python. No Discord or database imports.
Consumed by: Storyteller (prose style), Quest Mirror (typography, timing).
On failure: returns neutral defaults. Never blocks the pipeline.
"""

import logging
from typing import Optional

from google import genai

from models.mood_assessment import MoodAssessment
from tools.rate_limiter import gemini_limiter

logger = logging.getLogger("MoodAgent")

MOOD_AGENT_IDENTITY = """You are the Mood Agent for a D&D 5e AI Dungeon Master system.

Your role: Analyze the current game state and produce a structured emotional assessment.
This assessment drives narrative typography, text pacing, NPC dialogue tone, and ambient atmosphere.

You receive: player input, message type, location, time of day, scene description,
chaos factor, recent narrative context, character HP percentage, and active conditions.

You output a JSON object with these fields:
- primary_mood: One of: combat, horror, wonder, sorrow, tension, warmth, dialogue, neutral
- intensity: 1-10 (how strongly the mood is felt)
- secondary_mood: Optional undertone from the same set (e.g., sorrow beneath combat)
- npc_emotional_states: Dict of NPC name -> short emotional description (max 5 NPCs)
- environmental_tone: Short prose describing the atmosphere (e.g., "firelit intimacy", "oppressive damp stone")
- typography_hint: One of: combat, horror, wonder, sorrow, neutral
- breath_timing: One of: urgent, slow, generous, still, conversational, neutral

Guidelines:
- Combat: active fighting, chases, imminent physical danger
- Horror: dread, creeping wrongness, the unknown, something deeply wrong
- Wonder: beauty, discovery, awe, first sight of something magnificent
- Sorrow: loss, grief, melancholy, bittersweet memory
- Tension: social pressure, negotiation, high-stakes decisions without combat
- Warmth: safety, camaraderie, hearth, rest, humor among friends
- Dialogue: conversation-focused, information exchange, social interaction
- Neutral: transitional, no strong emotional charge

- Intensity 1-3: subtle undertone. Intensity 4-6: clearly present. Intensity 7-9: dominant. Intensity 10: overwhelming.
- Secondary mood captures emotional complexity (sorrow beneath a victory, tension in a warm tavern).
- NPC emotions reflect how NPCs FEEL, not just their disposition. A friendly NPC can be anxious.
- Environmental tone is prose, not a label. "Candlelit warmth bleeding through frost-cracked windows."
- Typography hint maps to visual text treatment. Match to the primary mood unless the secondary is stronger visually.
- Breath timing maps to text delivery speed. Combat = urgent. Horror = slow. Wonder = generous. Sorrow = still.

Output ONLY valid JSON. No markdown, no explanation, no preamble."""

_NEUTRAL_DEFAULT = MoodAssessment(
    primary_mood="neutral",
    intensity=5,
    environmental_tone="calm",
    typography_hint="neutral",
    breath_timing="neutral",
)


class MoodAgent:
    """Assess the emotional tone of the current game moment."""

    def __init__(
        self,
        client,
        context_assembler,
        model_id: str = "gemini-2.0-flash",
    ):
        self.client = client
        self.context = context_assembler
        self.model_id = model_id

    async def assess(
        self,
        player_input: str,
        message_type: str,
        location: str,
        time_of_day: str,
        scene_state: str,
        chaos_factor: int,
        recent_narrative: str,
        hp_percent: float,
        conditions: list[str],
    ) -> MoodAssessment:
        """Produce a MoodAssessment from the current game context.

        On any error (API failure, invalid JSON), returns a neutral default.
        """
        prompt = self._build_prompt(
            player_input, message_type, location, time_of_day,
            scene_state, chaos_factor, recent_narrative, hp_percent, conditions,
        )

        try:
            await gemini_limiter.acquire()
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=MOOD_AGENT_IDENTITY,
                    temperature=0.1,
                ),
            )
            return MoodAssessment.model_validate_json(response.text)
        except Exception as e:
            logger.warning(f"Mood assessment failed, using neutral default: {e}")
            return _NEUTRAL_DEFAULT.model_copy()

    def _build_prompt(
        self,
        player_input: str,
        message_type: str,
        location: str,
        time_of_day: str,
        scene_state: str,
        chaos_factor: int,
        recent_narrative: str,
        hp_percent: float,
        conditions: list[str],
    ) -> str:
        parts = [
            f"Player input: {player_input}",
            f"Message type: {message_type}",
            f"Location: {location}",
            f"Time of day: {time_of_day}",
        ]
        if scene_state:
            parts.append(f"Scene: {scene_state}")
        parts.append(f"Chaos factor: {chaos_factor}")
        if recent_narrative:
            parts.append(f"Recent narrative:\n{recent_narrative}")
        parts.append(f"Character HP: {hp_percent:.0%}")
        if conditions:
            parts.append(f"Active conditions: {', '.join(conditions)}")
        return "\n".join(parts)
