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


if __name__ == "__main__":
    print("Storyteller Agent initialized.")
