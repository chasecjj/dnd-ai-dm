"""
Chronicler Agent — Silent record-keeper for the campaign vault.

Runs after every game action. Never speaks to players.
Analyzes the exchange (player action + rules ruling + storyteller narrative)
and writes structured updates to the vault.
"""

import json
import logging
from typing import Dict, Any, List, Optional
from google import genai
from pydantic import ValidationError

from models.chronicler_output import ChroniclerOutput
from tools.vault_manager import VaultManager
from tools.context_assembler import ContextAssembler

logger = logging.getLogger('Chronicler')


# The Chronicler's extraction schema — tells Gemini exactly what to output.
# Field names MUST match the ChroniclerOutput Pydantic model in models/chronicler_output.py.
CHRONICLER_SCHEMA = """
You must respond with ONLY valid JSON matching this exact schema. No markdown, no explanation.

{
  "events": [
    {
      "description": "One-sentence summary of what happened",
      "impact": 5,
      "type": "combat|npc_interaction|discovery|movement|flavor|decision"
    }
  ],
  "character_updates": [
    {
      "name": "Character Name",
      "hp_current": null,
      "conditions": [],
      "spell_slots_used": null,
      "lay_on_hands_pool": null
    }
  ],
  "npc_updates": [
    {
      "name": "NPC Name",
      "disposition": null,
      "alive": true,
      "notes": ""
    }
  ],
  "quest_updates": [
    {
      "name": "Quest Name",
      "progress_note": "",
      "status": null
    }
  ],
  "new_consequences": [
    {
      "trigger_session": 2,
      "event": "What will happen",
      "caused_by": "What the party did",
      "impact": 7,
      "notes": "DM guidance"
    }
  ],
  "resolved_consequences": [
    "Event text of a due consequence that was addressed in this exchange"
  ],
  "location_updates": [],
  "world_clock": null
}

IMPACT SCALE:
  10 = Combat result, party member dropped to 0 HP, major revelation
   8 = Significant NPC interaction, reputation change, meaningful choice
   6 = Important discovery, moderate consequence, quest progress
   4 = Movement to new area, exploration, minor interaction
   2 = Flavor, ambient description, casual chat

DISPOSITION VALUES: "friendly", "neutral", "hostile", "unknown" (always use strings, never numbers).

Only include sections where something actually changed. Use null for unchanged fields.
"""


class ChroniclerAgent:
    """Analyzes game exchanges and writes structured updates to the vault."""
    
    def __init__(self, client, vault: VaultManager, context_assembler: ContextAssembler, model_id: str = "gemini-2.0-flash"):
        self.client = client
        self.vault = vault
        self.context_assembler = context_assembler
        self.model_id = model_id
        
        self.system_prompt = f"""You are the Chronicler, a silent record-keeper for a D&D 5e campaign.
You NEVER speak to players. Your only job is to analyze game exchanges and extract structured data.

Given:
- The player's action
- The Rules Lawyer's ruling
- The Storyteller's narrative response
- Current party state and active quests

You must extract what changed and output ONLY valid JSON.

{CHRONICLER_SCHEMA}

Be precise. Be concise. Extract ONLY what actually happened — never invent or embellish.
If nothing changed in a category, omit it or use null.
"""
    
    async def process_exchange(self, player_action: str, rules_response: str, story_response: str,
                               session_number: int, current_location: str = None) -> Dict[str, Any]:
        """Process a game exchange and update the vault.

        Args:
            player_action: What the player said/did.
            rules_response: The Rules Lawyer's mechanical ruling.
            story_response: The Storyteller's narrative response.
            session_number: Current session number.
            current_location: The current location name (for spatial context).

        Returns:
            Dict with the extracted changes, or empty dict on failure.
        """
        # Build context for the Chronicler
        context = self.context_assembler.build_chronicler_context(
            player_action, rules_response, story_response,
            current_location=current_location
        )
        
        prompt = f"""Analyze this D&D exchange and extract what changed.

{context}

Respond with ONLY the JSON extraction. No other text."""
        
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=self.system_prompt,
                    temperature=0.1,  # Low temperature for factual extraction
                )
            )
            
            # Parse the JSON response
            raw_text = response.text.strip()
            # Strip markdown code fences if present
            if raw_text.startswith('```'):
                raw_text = raw_text.split('\n', 1)[1]  # Remove first line
                raw_text = raw_text.rsplit('```', 1)[0]  # Remove last fence
            
            # Validate through ChroniclerOutput Pydantic model — the gate
            # between LLM output and vault writes. Invalid JSON is rejected entirely.
            changes = ChroniclerOutput.model_validate_json(raw_text)
            logger.info(f"Chronicler validated output: {len(changes.events)} events, "
                        f"{len(changes.character_updates)} char updates, "
                        f"{len(changes.new_consequences)} consequences")

            # Apply validated changes to the vault
            await self._apply_changes(changes, session_number)

            return changes.model_dump()

        except ValidationError as e:
            logger.error(f"Chronicler output failed validation (nothing written): {e}")
            logger.debug(f"Raw response: {raw_text[:500]}")
            return {}
        except json.JSONDecodeError as e:
            logger.error(f"Chronicler JSON parse error: {e}")
            logger.debug(f"Raw response: {raw_text[:500]}")
            return {}
        except Exception as e:
            logger.error(f"Chronicler error: {e}")
            return {}
    
    async def _apply_changes(self, changes: ChroniclerOutput, session_number: int):
        """Apply validated ChroniclerOutput to the vault files.

        Args:
            changes: A validated ChroniclerOutput instance (never a raw dict).
            session_number: Current session number.
        """

        # 1. Record events in conversation history
        for event in changes.events:
            if event.description:
                self.context_assembler.record_event(event.description, event.impact)
                self.vault.append_to_session_log(
                    session_number,
                    f"| | {event.description} | {event.impact} | |"
                )

        # 2. Update party members (flat fields from CharacterUpdate)
        for update in changes.character_updates:
            # Build dict of non-None fields (excluding 'name')
            update_dict = update.model_dump(exclude={"name"}, exclude_none=True)
            if update.name and update_dict:
                self.vault.update_party_member(update.name, update_dict)
                logger.info(f"Updated party member {update.name}: {update_dict}")

        # 3. Update NPCs (uses string dispositions enforced by Pydantic)
        for update in changes.npc_updates:
            if not update.name:
                continue
            result = self.vault.get_npc(update.name)
            if result:
                fm, body = result
                if update.disposition:
                    fm['disposition'] = update.disposition
                if update.alive is not None:
                    fm['alive'] = update.alive
                fm['last_seen_session'] = session_number
                for fpath in self.vault.list_files(self.vault.NPCS):
                    npc_fm, _ = self.vault.read_file(fpath)
                    if npc_fm.get('name', '').lower() == update.name.lower():
                        if update.notes:
                            body += f"\n\n### Session {session_number} Update\n{update.notes}"
                        self.vault.write_file(fpath, fm, body)
                        break

        # 4. Update quests
        for update in changes.quest_updates:
            if update.name and update.status == 'completed':
                self.vault.complete_quest(update.name, session_number)

        # 5. Add new consequences (with deduplication)
        if changes.new_consequences:
            fm, body = self.vault.read_consequences()
            body_lower = body.lower()

            for c in changes.new_consequences:
                # Deduplication: skip if a very similar consequence already exists
                event_normalized = c.event.strip().lower()
                if event_normalized and self._is_duplicate_consequence(event_normalized, body_lower):
                    logger.info(f"Skipping duplicate consequence: {c.event[:60]}")
                    continue

                entry = f"""
- **trigger:** session >= {c.trigger_session}
  **event:** {c.event}
  **caused_by:** "{c.caused_by}"
  **impact:** {c.impact}
  **notes:** {c.notes}
"""
                body = body.replace('## Resolved', f"{entry}\n## Resolved")
                # Update body_lower so subsequent checks in this batch see the new entry
                body_lower = body.lower()

            self.vault.write_file(
                f"{self.vault.WORLD_STATE}/consequences.md", fm, body
            )

        # 6. Resolve fired consequences
        for event_text in changes.resolved_consequences:
            if event_text:
                success = self.vault.resolve_consequence(event_text, session_number)
                if success:
                    logger.info(f"Resolved consequence: {event_text[:60]}")

        # 7. Advance clock if needed
        if changes.world_clock:
            self.vault.advance_clock(
                new_date=changes.world_clock.current_date or '',
                time_of_day=changes.world_clock.time_of_day or '',
                session=session_number
            )

        logger.info(f"Chronicler applied all changes for session {session_number}")

    @staticmethod
    def _is_duplicate_consequence(new_event: str, existing_body: str) -> bool:
        """Check if a consequence already exists in the body text.

        Uses substring matching and word-overlap heuristic to catch near-duplicates
        like 'The thieves guild notices the party' vs 'Thieves guild takes notice of party'.
        """
        # Exact substring match
        if new_event in existing_body:
            return True

        # Word-overlap heuristic: if 60%+ of significant words match an existing entry,
        # it's likely a duplicate
        new_words = set(w for w in new_event.split() if len(w) > 3)
        if not new_words:
            return False

        # Extract existing consequence events from the body
        for line in existing_body.split('\n'):
            line = line.strip()
            if line.startswith('**event:**'):
                existing_event = line.replace('**event:**', '').strip().lower()
                existing_words = set(w for w in existing_event.split() if len(w) > 3)
                if existing_words and new_words:
                    overlap = len(new_words & existing_words)
                    ratio = overlap / min(len(new_words), len(existing_words))
                    if ratio >= 0.6:
                        return True

        return False
