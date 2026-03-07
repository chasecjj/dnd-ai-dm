"""
PlayerAdvisorAgent — Private brainstorming partner for individual players.

Lives in /whisper threads. Helps players understand their character's abilities,
think through tactical options, and craft compelling in-character actions.
NOT the DM — a supportive teammate who knows the character sheet.
"""

import logging
from typing import Optional
from google import genai
from tools.context_assembler import ContextAssembler
from tools.vault_manager import VaultManager

logger = logging.getLogger("PlayerAdvisor")

ADVISOR_IDENTITY = """You are a character advisor for a D&D 5e player. You are NOT the Dungeon Master.

Your job is to help the player understand their character's abilities, think through
tactical options, and craft compelling in-character actions.

You know:
- The player's character sheet (class, race, abilities, spells, equipment)
- The current game situation (location, NPCs present, recent events)
- D&D 5e rules and mechanics

You do NOT:
- Reveal DM secrets, upcoming encounters, or hidden information
- Guarantee outcomes ("you WILL succeed" — never say this)
- Make decisions for the player — present options, let them choose
- Narrate scenes or act as the DM
- Roll dice or determine results

Your tone:
- Supportive teammate, like a more experienced player helping a friend
- Suggest 2-3 concrete options with their mechanics explained briefly
- Mention relevant abilities, spells, and features the character actually has
- Help phrase actions in a way that's engaging and in-character
- Be concise — players are mid-game, not reading a textbook

When the player has decided on an action, suggest clear wording they can use with:
  !commit <their action>
This sends the action to the Game Table for the DM to resolve.
"""


class PlayerAdvisorAgent:
    """Private brainstorming partner for players in /whisper threads."""

    def __init__(self, client, context_assembler: ContextAssembler,
                 vault: VaultManager, model_id: str = "gemini-2.0-flash"):
        self.client = client
        self.context = context_assembler
        self.vault = vault
        self.model_id = model_id
        self._conversations: dict[int, list] = {}  # thread_id -> message history

    def _build_character_context(self, character_name: str) -> str:
        """Build character-specific context for the advisor."""
        party = self.vault.get_party_state()
        char_data = None
        for member in party:
            if member['frontmatter'].get('name', '').lower() == character_name.lower():
                char_data = member
                break

        if not char_data:
            return f"## Your Character: {character_name}\n(No character sheet found in vault)"

        fm = char_data['frontmatter']
        lines = [f"## Your Character: {character_name}", char_data['summary']]

        for key in ['skills', 'features', 'spells', 'equipment', 'proficiencies',
                     'languages', 'saving_throws', 'attacks']:
            val = fm.get(key)
            if val:
                if isinstance(val, list):
                    val = ", ".join(str(v) for v in val)
                lines.append(f"**{key.replace('_', ' ').title()}:** {val}")

        return "\n".join(lines)

    async def advise(self, thread_id: int, character_name: str,
                     player_message: str) -> str:
        """Provide character-specific advice in a brainstorm conversation.

        Args:
            thread_id: The Discord thread ID (for conversation tracking).
            character_name: The player's character name.
            player_message: What the player is asking/saying.

        Returns:
            Advice string to send back to the player.
        """
        logger.info(f"Advising {character_name} (thread {thread_id}): {player_message[:80]}")

        char_context = self._build_character_context(character_name)
        game_context = self.context.build_storyteller_context()

        system = f"""{ADVISOR_IDENTITY}

{char_context}

## Current Game State
{game_context}
"""

        # Get or create conversation history for this thread
        if thread_id not in self._conversations:
            self._conversations[thread_id] = []
        history = self._conversations[thread_id]

        # Build contents with conversation history
        contents = list(history[-10:])  # Last 10 turns
        contents.append({"role": "user", "parts": [{"text": player_message}]})

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=system,
                    temperature=0.7,
                )
            )

            result = response.text

            # Track conversation
            history.append({"role": "user", "parts": [{"text": player_message}]})
            history.append({"role": "model", "parts": [{"text": result}]})

            # Trim if too long
            if len(history) > 20:
                self._conversations[thread_id] = history[-20:]

            return result

        except Exception as e:
            logger.error(f"Advisor failed: {e}", exc_info=True)
            return ("I'm having trouble thinking right now. "
                    "Try rephrasing, or paste your action directly into the Game Table!")

    def clear_conversation(self, thread_id: int):
        """Clear the brainstorm history for a thread."""
        self._conversations.pop(thread_id, None)
        logger.info(f"Cleared advisor conversation for thread {thread_id}")
