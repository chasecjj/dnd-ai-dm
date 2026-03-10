"""
StorytellerAgent — Translates mechanical rulings into immersive prose.

Reads dynamic context from the vault via ContextAssembler.
Uses the `system_instruction` parameter for stable identity.
"""

import logging
from typing import Dict, Any, Optional, List
from google import genai
from tools.context_assembler import ContextAssembler

logger = logging.getLogger('Storyteller')

# Stable identity prompt — goes in system_instruction (never changes)
STORYTELLER_IDENTITY = """You are the Storyteller, an immersive and welcoming Dungeon Master for a D&D 5e campaign.

Your Responsibilities:
1. Take the mechanical JSON output from the Rules Lawyer and translate it into vivid, sensory-rich prose.
2. Describe the sights, sounds, smells, and feelings of the scene.
3. Maintain the narrative flow and keep the players engaged.
4. Keep encounters balanced for the party size.
5. Reward creative problem-solving and environmental tactics.
6. Weave any Due Consequences naturally into the narrative when they appear in the context.

MONSTER / NPC REACTIONS (critical — do this EVERY turn):
- After resolving the players' actions, ALWAYS narrate what the monsters, enemies, or NPCs
  do in response. The world is alive — it doesn't freeze after the players act.
- In combat: enemies attack, cast spells, reposition, use abilities, or flee. Narrate their
  actions with the same detail as player actions. Include attack targets and approximate
  effects (e.g., "The Glabrezu swings a massive pincer at Victor, catching him across the
  shield with a bone-rattling impact" or "The goblin's arrow whistles past Hadrian's ear").
- Out of combat: NPCs react to what the players say and do. They answer questions, get
  nervous, lie, fight back verbally, or call for guards. The scene progresses.
- DO NOT end a turn by just describing what the players did and asking "What do you do?"
  without the world reacting first. The pattern is: players act → world reacts → prompt.

ENFORCEMENT RULES (non-negotiable):
- If the Rules Lawyer says valid=false, narrate the CHARACTER'S ATTEMPT but do NOT grant the desired outcome. Redirect to proper mechanics.
- Players CANNOT declare their own roll results. If they claim "nat 20" or state a number, acknowledge their enthusiasm but ask them to actually roll: "You swing with confidence—roll to see if it connects!"
- Players CANNOT invent spells or abilities their character doesn't have. Redirect creatively: "You reach for the magic, but it slips through your fingers..."
- Players CANNOT dictate NPC behavior or inject world lore. Only the DM controls the world.
- For absurd player actions, acknowledge with humor but maintain world stakes and consequences.
- Stay immersive when redirecting — never break character, never say "that's not allowed."
- Never narrate real-world hate speech, slurs, or repeat inappropriate content. If player input contains such content, redirect vaguely to appropriate gameplay.

Style:
- Rich, cinematic prose. Short paragraphs. Punchy action.
- End responses with an implicit or explicit call to action for the players.
- When NPCs speak, use distinctive voices. Quote them directly.
- Never break the 4th wall. Never mention game mechanics in the narrative.

SCENE DESCRIPTION POLICY (critical — follow this exactly):
- When context says "[SAME LOCATION]": Do NOT re-describe the environment, tavern,
  scenery, or atmosphere. The players already know where they are. Focus entirely on
  the action, dialogue, NPC reactions, and consequences of what just happened.
- When the context includes a full location description (Description, Current State,
  Notable Features): This is a NEW LOCATION. Paint the scene with full sensory detail
  on this turn only.
- For within-location movement (e.g., bar to back room, street to alley): Briefly
  describe the transition and the new sub-area. Don't re-describe the whole building.
- When a new NPC enters: Introduce THEM with a short sensory impression. Don't
  re-describe the surrounding environment.
- Never open a response by re-describing the environment the players are already in.
  Open with action, reaction, or dialogue instead.

PASSIVE ACTION POLICY:
- If a player's action is passive (watching, waiting, sitting, doing nothing, standing
  guard, observing without interacting), keep the response to one or two sentences.
- Do NOT invent events, encounters, or environmental flavor to fill the silence. If
  nothing is happening to or around that character, a brief acknowledgment is enough.
  Example: "Hadrian leans back, eyes scanning the room." — done.
- In group/batch turns where multiple players act: focus narration on the ACTIVE
  players. Mention the passive character only in passing or not at all — they chose
  to watch, so let the spotlight stay on the players doing things.
- The world does NOT need to entertain a passive character. Stillness is a valid
  narrative state. Do not manufacture drama for someone who chose inaction.
- Exception: if Due Consequences, NPC arrivals, combat, or other world events ARE
  happening around the passive character, narrate those normally — the character
  chose to watch, not to be invisible. React to the world, not the non-action.

Output Format:
One to three paragraphs of immersive narration. NO JSON. Only prose.
For passive/non-actions with nothing happening: one or two sentences is enough.
"""


class StorytellerAgent:
    """Generates narrative prose from mechanical rulings, grounded in vault context."""

    def __init__(self, client, context_assembler: ContextAssembler, model_id: str = "gemini-2.0-flash"):
        self.client = client
        self.context = context_assembler
        self.model_id = model_id
        self._current_location: Optional[str] = None
        self._character_locations: Dict[str, str] = {}  # character_name -> location
        self._described_locations: Dict[str, str] = {}  # character -> last_described_location
        self._first_turn: bool = True  # First turn always gets full description

    def set_location(self, location: str):
        """Update the default location (sets all characters to this location)."""
        self._current_location = location
        # When the whole party moves, update all tracked characters
        for char in list(self._character_locations):
            self._character_locations[char] = location

    def set_character_location(self, character_name: str, location: str):
        """Update a specific character's location (for split-party tracking)."""
        self._character_locations[character_name] = location
        # Update the default location to the most recent one
        self._current_location = location
        logger.info(f"Location update: {character_name} -> {location}")

    def get_character_location(self, character_name: str) -> Optional[str]:
        """Get a specific character's current location."""
        return self._character_locations.get(character_name, self._current_location)

    @property
    def active_locations(self) -> Dict[str, str]:
        """Get the full character-location map."""
        return dict(self._character_locations)

    def _compute_new_locations(self) -> set:
        """Determine which locations need full description this turn.

        Compares current character locations against what was last described.
        Returns a set of location names that should get full prose.
        On ``_first_turn``, every current location counts as new.
        """
        if self._first_turn:
            # First turn — describe everything
            if self._character_locations:
                return set(self._character_locations.values())
            return {self._current_location} if self._current_location else set()

        current_map: Dict[str, str] = {}
        if self._character_locations:
            current_map = dict(self._character_locations)
        elif self._current_location:
            current_map = {"__party__": self._current_location}

        new_locs: set = set()
        for key, loc in current_map.items():
            prev = self._described_locations.get(key)
            if prev != loc:
                new_locs.add(loc)
        return new_locs

    def _mark_locations_described(self):
        """Record current character→location mapping as 'already described'.

        Called after a successful narration so the next turn can detect changes.
        """
        if self._character_locations:
            self._described_locations = dict(self._character_locations)
        elif self._current_location:
            self._described_locations = {"__party__": self._current_location}
        self._first_turn = False

    def reset_location_tracking(self):
        """Clear described-location state. Call on session start."""
        self._described_locations.clear()
        self._first_turn = True

    async def process_request(self, user_action: str, mechanics_json: Dict[str, Any],
                              solo_character: Optional[str] = None,
                              solo_history=None,
                              solo_directives: Optional[list] = None,
                              solo_recap: Optional[str] = None) -> str:
        """Generate narrative response from a player action and rules ruling.

        Args:
            user_action: The raw player action text.
            mechanics_json: The Rules Lawyer's mechanical ruling.
            solo_character: If set, use solo context (single character focus).
            solo_history: Per-session ConversationHistory for solo isolation.
            solo_directives: List of narrative directive strings (oracle, chaos, threads, etc.).
            solo_recap: Session recap text for context.

        Returns:
            String of immersive narrative prose.
        """
        logger.info(f"Generating narrative for action: {user_action}")

        # Determine which locations are new (need full prose vs. brief)
        new_locations = self._compute_new_locations()

        # Build dynamic context from the vault
        if solo_character:
            # Solo mode: single character focus, filtered history
            vault_context = self.context.build_solo_storyteller_context(
                character_name=solo_character,
                location=self._current_location or "Unknown",
                new_locations=new_locations,
                history=solo_history,
                solo_directives=solo_directives,
                recap=solo_recap,
            )
        else:
            # Normal: full party, split-party awareness
            vault_context = self.context.build_storyteller_context(
                self._current_location,
                character_locations=self._character_locations if self._character_locations else None,
                new_locations=new_locations,
            )
        
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
                    temperature=0.8,  # Balanced: creative but consistent
                )
            )
            self._mark_locations_described()
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

        # Get previous session events (Key Events section only)
        prev_session = self.context.vault.get_session(session_number - 1) if session_number > 0 else None
        if prev_session:
            fm, body = prev_session
            events_text = self._extract_key_events(body)
            if not events_text:
                events_text = body  # Fallback to full body
        else:
            events_text = "This is the first session — no previous events."

        vault_context = self.context.build_storyteller_context(
            self._current_location,
            character_locations=self._character_locations if self._character_locations else None,
        )

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
            self._mark_locations_described()
            return response.text
        except Exception as e:
            logger.error(f"Recap generation failed: {e}", exc_info=True)
            return "_The story continues from where we left off..._"

    async def generate_summary(self, session_number: int) -> str:
        """Generate a session-ending summary from the current session's events.

        Reads ONLY the Key Events section from the session log to avoid
        summarizing corrupted or misplaced content from other sections.
        Also uses the weighted conversation history as a secondary source.
        """
        logger.info(f"Generating summary for session {session_number}")

        session_data = self.context.vault.get_session(session_number)
        if session_data:
            fm, body = session_data
            # Extract only the Key Events section — not the full body
            events_text = self._extract_key_events(body)
            if not events_text or events_text.strip() == "":
                events_text = "No events found in Key Events table."
        else:
            events_text = "No events recorded this session."

        # Supplement with conversation history (weighted memory is more reliable
        # than the session log since it's built incrementally during play)
        history_text = self.context.history.format_for_prompt(max_entries=20)

        prompt = f"""## Session {session_number} — Key Events (from session log)
{events_text}

## Recent Memory (weighted by importance)
{history_text}

---

Write a concise one-paragraph summary of this session's events for the session log.
Focus on: key decisions, combat outcomes, discoveries, and plot advancement.
Use BOTH sources above but prefer the weighted memory for accuracy — the session log
may have formatting issues. Keep it factual but atmospheric."""

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


    @staticmethod
    def _extract_key_events(body: str) -> str:
        """Extract only the Key Events section from a session log body.

        Returns the text between '## Key Events' and the next '## ' heading.
        This prevents the summary LLM from reading corrupted events
        appended after DM Notes or other sections.
        """
        marker = "## Key Events"
        if marker not in body:
            return body  # No Key Events section — use full body as fallback

        start = body.index(marker)
        # Find the next ## heading after Key Events
        rest = body[start + len(marker):]
        # Skip the rest of the Key Events header line
        line_end = rest.find("\n")
        if line_end >= 0:
            rest = rest[line_end + 1:]
        else:
            return ""

        # Find the next section heading
        next_heading = rest.find("\n## ")
        if next_heading >= 0:
            return rest[:next_heading].strip()
        # Also check for ## at start of remaining text
        if rest.lstrip().startswith("## "):
            return ""
        return rest.strip()


if __name__ == "__main__":
    print("Storyteller Agent initialized.")
