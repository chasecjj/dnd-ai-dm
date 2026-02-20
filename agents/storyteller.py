"""
StorytellerAgent — Translates mechanical rulings into immersive prose.

Reads dynamic context from the vault via ContextAssembler.
Uses the `system_instruction` parameter for stable identity.
"""

import logging
from typing import Dict, Any, Optional
from google import genai
from tools.context_assembler import ContextAssembler

logger = logging.getLogger('Storyteller')

# Stable identity prompt — goes in system_instruction (never changes)
STORYTELLER_IDENTITY = """You are the Storyteller, an immersive and welcoming Dungeon Master for a D&D 5e campaign.

Your Responsibilities:
1. Take the mechanical JSON output from the Rules Lawyer and translate it into vivid, sensory-rich prose.
2. Describe the sights, sounds, smells, and feelings of the scene.
3. Maintain the narrative flow and keep the players engaged.
4. Keep encounters balanced for a 2-player party.
5. Reward creative problem-solving and environmental tactics.
6. Weave any Due Consequences naturally into the narrative when they appear in the context.

Style:
- Rich, cinematic prose. Short paragraphs. Punchy action.
- End responses with an implicit or explicit call to action for the players.
- When NPCs speak, use distinctive voices. Quote them directly.
- Never break the 4th wall. Never mention game mechanics in the narrative.

Output Format:
One to three paragraphs of immersive narration. NO JSON. Only prose.
"""


class StorytellerAgent:
    """Generates narrative prose from mechanical rulings, grounded in vault context."""
    
    def __init__(self, client, context_assembler: ContextAssembler, model_id: str = "gemini-2.0-flash"):
        self.client = client
        self.context = context_assembler
        self.model_id = model_id
        self._current_location: Optional[str] = None
    
    def set_location(self, location: str):
        """Update the current location for context building."""
        self._current_location = location
    
    async def process_request(self, user_action: str, mechanics_json: Dict[str, Any]) -> str:
        """Generate narrative response from a player action and rules ruling.
        
        Args:
            user_action: The raw player action text.
            mechanics_json: The Rules Lawyer's mechanical ruling.
        
        Returns:
            String of immersive narrative prose.
        """
        logger.info(f"Generating narrative for action: {user_action}")
        
        # Build dynamic context from the vault
        vault_context = self.context.build_storyteller_context(self._current_location)
        
        # Build the user-facing prompt (dynamic parts)
        prompt = f"""## Current World State (from vault)
{vault_context}

---

## This Turn
**Player Action:** {user_action}
**Rules Lawyer Ruling:** {mechanics_json}

Narrate what happens. Incorporate any Due Consequences naturally if present above."""
        
        if not self.client:
            raise RuntimeError("Storyteller Agent not connected to model.")
        
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=STORYTELLER_IDENTITY,
                    temperature=0.9,  # Higher for creative prose
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Storyteller generation failed: {e}", exc_info=True)
            raise

    async def generate_recap(self, session_number: int) -> str:
        """Generate a session-opening recap from the previous session's events.

        Reads the last session log from the vault and produces a 'Previously on...'
        style narrative summary to ground players at the start of a new session.
        """
        logger.info(f"Generating recap for session {session_number}")

        # Get previous session events
        prev_session = self.context.vault.get_session(session_number - 1) if session_number > 0 else None
        if prev_session:
            fm, body = prev_session
            events_text = body
        else:
            events_text = "This is the first session — no previous events."

        vault_context = self.context.build_storyteller_context(self._current_location)

        prompt = f"""## Current World State
{vault_context}

## Previous Session Events
{events_text}

---

Generate a "Previously on..." recap for the players. 2-3 paragraphs of atmospheric prose
summarizing the key events of the last session, ending with a reminder of where the party
currently is and what they were doing. Set the mood for tonight's session."""

        if not self.client:
            return "_The story continues..._"

        try:
            from tools.rate_limiter import gemini_limiter
            await gemini_limiter.acquire()
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=STORYTELLER_IDENTITY,
                    temperature=0.8,
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Recap generation failed: {e}", exc_info=True)
            return "_The story continues from where we left off..._"

    async def generate_summary(self, session_number: int) -> str:
        """Generate a session-ending summary from the current session's events.

        Reads the current session log and produces a concise one-paragraph summary
        suitable for the session log's Summary section.
        """
        logger.info(f"Generating summary for session {session_number}")

        session_data = self.context.vault.get_session(session_number)
        if session_data:
            fm, body = session_data
            events_text = body
        else:
            events_text = "No events recorded this session."

        prompt = f"""## Session {session_number} Events
{events_text}

---

Write a concise one-paragraph summary of this session's events for the session log.
Focus on: key decisions, combat outcomes, discoveries, and plot advancement.
Keep it factual but atmospheric. This will be stored as the session's Summary section."""

        if not self.client:
            return "_Session summary pending._"

        try:
            from tools.rate_limiter import gemini_limiter
            await gemini_limiter.acquire()
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=STORYTELLER_IDENTITY,
                    temperature=0.5,  # More factual than creative
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Summary generation failed: {e}", exc_info=True)
            return "_Session summary could not be generated._"


if __name__ == "__main__":
    print("Storyteller Agent initialized.")
