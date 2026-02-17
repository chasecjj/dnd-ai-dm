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

from tools.vault_manager import VaultManager
from tools.context_assembler import ContextAssembler

logger = logging.getLogger('Chronicler')


# The Chronicler's extraction schema — tells Gemini exactly what to output
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
  "party_updates": [
    {
      "character": "Character Name",
      "updates": {
        "hp_current": null,
        "conditions": [],
        "spell_slots_used": null,
        "lay_on_hands_pool": null
      }
    }
  ],
  "npc_updates": [
    {
      "name": "NPC Name",
      "disposition_change": null,
      "alive": true,
      "notes": ""
    }
  ],
  "quest_updates": [
    {
      "quest_name": "Quest Name",
      "progress_note": "",
      "status_change": null
    }
  ],
  "consequences": [
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
  "location_state_change": null,
  "clock_advance": null
}

IMPACT SCALE:
  10 = Combat result, party member dropped to 0 HP, major revelation
   8 = Significant NPC interaction, reputation change, meaningful choice
   6 = Important discovery, moderate consequence, quest progress
   4 = Movement to new area, exploration, minor interaction
   2 = Flavor, ambient description, casual chat

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
            
            changes = json.loads(raw_text)
            logger.info(f"Chronicler extracted changes: {list(changes.keys())}")
            
            # Apply changes to the vault
            await self._apply_changes(changes, session_number)
            
            return changes
            
        except json.JSONDecodeError as e:
            logger.error(f"Chronicler JSON parse error: {e}")
            logger.debug(f"Raw response: {raw_text[:500]}")
            return {}
        except Exception as e:
            logger.error(f"Chronicler error: {e}")
            return {}
    
    async def _apply_changes(self, changes: Dict[str, Any], session_number: int):
        """Apply extracted changes to the vault files."""
        
        # 1. Record events in conversation history
        events = changes.get('events', [])
        for event in events:
            desc = event.get('description', '')
            impact = event.get('impact', 5)
            if desc:
                self.context_assembler.record_event(desc, impact)
                # Also append to session log
                self.vault.append_to_session_log(
                    session_number,
                    f"| | {desc} | {impact} | |"
                )
        
        # 2. Update party members
        party_updates = changes.get('party_updates', [])
        for update in party_updates:
            character = update.get('character', '')
            updates = update.get('updates', {})
            # Filter out null values
            filtered = {k: v for k, v in updates.items() if v is not None}
            if character and filtered:
                self.vault.update_party_member(character, filtered)
                logger.info(f"Updated party member {character}: {filtered}")
        
        # 3. Update NPCs
        npc_updates = changes.get('npc_updates', [])
        for update in npc_updates:
            name = update.get('name', '')
            if not name:
                continue
            result = self.vault.get_npc(name)
            if result:
                fm, body = result
                if update.get('disposition_change'):
                    fm['disposition'] = update['disposition_change']
                if 'alive' in update:
                    fm['alive'] = update['alive']
                fm['last_seen_session'] = session_number
                # Find the file path and write back
                for fpath in self.vault.list_files(self.vault.NPCS):
                    npc_fm, _ = self.vault.read_file(fpath)
                    if npc_fm.get('name', '').lower() == name.lower():
                        notes = update.get('notes', '')
                        if notes:
                            body += f"\n\n### Session {session_number} Update\n{notes}"
                        self.vault.write_file(fpath, fm, body)
                        break
        
        # 4. Update quests
        quest_updates = changes.get('quest_updates', [])
        for update in quest_updates:
            quest_name = update.get('quest_name', '')
            status_change = update.get('status_change')
            if quest_name and status_change == 'completed':
                self.vault.complete_quest(quest_name, session_number)
        
        # 5. Add new consequences
        new_consequences = changes.get('consequences', [])
        if new_consequences:
            fm, body = self.vault.read_consequences()
            for c in new_consequences:
                entry = f"""
- **trigger:** session >= {c.get('trigger_session', session_number + 1)}
  **event:** {c.get('event', '')}
  **caused_by:** "{c.get('caused_by', '')}"
  **impact:** {c.get('impact', 5)}
  **notes:** {c.get('notes', '')}
"""
                # Insert before the "## Resolved" section
                body = body.replace('## Resolved', f"{entry}\n## Resolved")
            
            self.vault.write_file(
                f"{self.vault.WORLD_STATE}/consequences.md", fm, body
            )
        
        # 6. Resolve fired consequences
        resolved = changes.get('resolved_consequences', [])
        for event_text in resolved:
            if event_text and isinstance(event_text, str):
                success = self.vault.resolve_consequence(event_text, session_number)
                if success:
                    logger.info(f"Resolved consequence: {event_text[:60]}")

        # 7. Advance clock if needed
        clock_advance = changes.get('clock_advance')
        if clock_advance:
            self.vault.advance_clock(
                new_date=clock_advance.get('date', ''),
                time_of_day=clock_advance.get('time', ''),
                session=session_number
            )
        
        logger.info(f"Chronicler applied all changes for session {session_number}")
