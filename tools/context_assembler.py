"""
ContextAssembler — Builds focused, dynamic prompts from the vault + StateManager.

Replaces all hardcoded context. Uses weighted memory decay
so important events persist longer in the AI's context window
while flavor text fades naturally.

Data source priority:
  1. StateManager (MongoDB) — mechanical truth: HP, conditions, quests, consequences.
  2. Vault (Obsidian markdown) — narrative prose: descriptions, lore, session logs.
  3. Reference Manager — extracted source-book rules and lore excerpts.

If StateManager is not connected, falls back silently to vault-only mode.
"""

import json
import os
import logging
import tempfile
import time
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from tools.vault_manager import VaultManager
from tools.lorebook import Lorebook

if TYPE_CHECKING:
    from tools.reference_manager import ReferenceManager
    from tools.state_manager import StateManager

logger = logging.getLogger('ContextAssembler')


class MemoryEntry:
    """A single event/fact in the conversation history with a weighted impact score."""

    def __init__(self, text: str, impact: int = 5, turns_ago: int = 0, timestamp: float = 0.0,
                 character: str = None, location: str = None):
        self.text = text
        self.base_impact = impact  # 1-10 scale
        self.turns_ago = turns_ago
        self.timestamp = timestamp or time.time()
        self.character = character    # Which character this event involves
        self.location = location      # Where this event happened
    
    @property
    def score(self) -> float:
        """Calculate the current relevance score using exponential decay.
        
        score = base_impact * decay_factor^(turns_ago)
        
        With decay_factor=0.85:
          - After 0 turns: score = impact * 1.0
          - After 4 turns: score ≈ impact * 0.52
          - After 10 turns: score ≈ impact * 0.20
          - After 15 turns: score ≈ impact * 0.09
        
        Critical events (impact=10) persist ~15+ turns.
        Flavor (impact=2) fades after ~5 turns.
        """
        decay_factor = 0.85
        return self.base_impact * (decay_factor ** self.turns_ago)
    
    def __repr__(self) -> str:
        tag = f" [{self.character}]" if self.character else ""
        return f"MemoryEntry(score={self.score:.1f}, turns_ago={self.turns_ago}{tag}, text='{self.text[:50]}...')"


class ConversationHistory:
    """Manages the weighted conversation history for an agent."""
    
    INCLUSION_THRESHOLD = 1.5  # Events scoring below this are dropped
    
    def __init__(self):
        self.entries: List[MemoryEntry] = []
    
    def add_event(self, text: str, impact: int = 5, age_existing: bool = True,
                  character: str = None, location: str = None):
        """Add a new event to history.

        Args:
            text: Event description.
            impact: Base importance score (1-10).
            age_existing: If True (default), all existing entries age by 1 turn.
                Set to False in queue mode or batched chronicler writes.
            character: Character name this event involves (for filtering).
            location: Location where this event happened (for spatial context).
        """
        if age_existing:
            for entry in self.entries:
                entry.turns_ago += 1
        self.entries.append(MemoryEntry(
            text=text, impact=impact, turns_ago=0,
            character=character, location=location,
        ))

    def advance_turn(self):
        """Age all entries by 1 turn without adding a new event.

        Call this once per batch resolve in queue mode, instead of aging
        on every add_event() call.
        """
        for entry in self.entries:
            entry.turns_ago += 1
    
    def get_relevant_history(self, max_entries: int = 20) -> List[MemoryEntry]:
        """Get history entries that are still above the inclusion threshold,
        sorted by score (highest first), capped at max_entries.
        """
        active = [e for e in self.entries if e.score >= self.INCLUSION_THRESHOLD]
        # Sort by score descending
        active.sort(key=lambda e: e.score, reverse=True)
        return active[:max_entries]
    
    def format_for_prompt(self, max_entries: int = 15) -> str:
        """Format the relevant history as a string for injection into a prompt.

        Groups events by location when multiple locations are active,
        and tags events with character names when available.
        """
        relevant = self.get_relevant_history(max_entries)
        if not relevant:
            return "No prior events in memory."

        # Check if we have multiple active locations
        locations = set(e.location for e in relevant if e.location)

        if len(locations) > 1:
            # Group by location for spatial clarity
            lines = []
            for loc in sorted(locations):
                loc_entries = [e for e in relevant if e.location == loc]
                lines.append(f"  **At {loc}:**")
                for entry in loc_entries:
                    importance = "\U0001f534" if entry.score >= 7 else "\U0001f7e1" if entry.score >= 4 else "\u26aa"
                    char_tag = f"[{entry.character}] " if entry.character else ""
                    lines.append(f"    {importance} {char_tag}{entry.text}")
            # Add unlocated events
            unlocated = [e for e in relevant if not e.location]
            if unlocated:
                for entry in unlocated:
                    importance = "\U0001f534" if entry.score >= 7 else "\U0001f7e1" if entry.score >= 4 else "\u26aa"
                    char_tag = f"[{entry.character}] " if entry.character else ""
                    lines.append(f"  {importance} {char_tag}{entry.text}")
            return "\n".join(lines)
        else:
            # Single location or no location data — flat list
            lines = []
            for entry in relevant:
                importance = "\U0001f534" if entry.score >= 7 else "\U0001f7e1" if entry.score >= 4 else "\u26aa"
                char_tag = f"[{entry.character}] " if entry.character else ""
                lines.append(f"  {importance} {char_tag}{entry.text}")
            return "\n".join(lines)
    
    def clear(self):
        """Clear all history."""
        self.entries.clear()

    def save_to_file(self, filepath: str):
        """Serialize conversation history to a JSON file for persistence across restarts.

        Uses atomic writes (write to temp, then os.replace) to prevent
        corruption if the bot crashes mid-write.
        """
        data = [
            {
                "text": e.text,
                "base_impact": e.base_impact,
                "turns_ago": e.turns_ago,
                "timestamp": e.timestamp,
                "character": e.character,
                "location": e.location,
            }
            for e in self.entries
        ]
        tmp_path = None
        try:
            dir_name = os.path.dirname(filepath)
            os.makedirs(dir_name, exist_ok=True)
            with tempfile.NamedTemporaryFile(
                'w', dir=dir_name, suffix='.tmp',
                delete=False, encoding='utf-8',
            ) as tmp:
                json.dump(data, tmp, indent=2, ensure_ascii=False)
                tmp_path = tmp.name
            os.replace(tmp_path, filepath)
            logger.info(f"Saved {len(data)} history entries to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save history: {e}")
            if tmp_path and os.path.exists(tmp_path):
                try:
                    os.unlink(tmp_path)
                except OSError:
                    pass

    def load_from_file(self, filepath: str):
        """Restore conversation history from a JSON checkpoint file."""
        if not os.path.exists(filepath):
            logger.info(f"No history checkpoint found at {filepath}")
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.entries = [
                MemoryEntry(
                    text=e['text'], impact=e['base_impact'],
                    turns_ago=e['turns_ago'], timestamp=e.get('timestamp', 0.0),
                    character=e.get('character'), location=e.get('location'),
                )
                for e in data
            ]
            # Prune entries that have decayed below threshold
            self.entries = [e for e in self.entries if e.score >= self.INCLUSION_THRESHOLD]
            logger.info(f"Restored {len(self.entries)} history entries from {filepath}")
        except Exception as e:
            logger.error(f"Failed to load history: {e}")


class ContextAssembler:
    """Assembles focused context for each agent call from the vault + conversation history.
    
    Context Budget (~4000 tokens max):
      - Party state:        ~500 tokens  (always included)
      - Location + NPCs:    ~500 tokens  (always included)
      - Active quest:       ~300 tokens  (always included)
      - Weighted history:  ~1500 tokens  (ranked by score)
      - Consequences:       ~200 tokens  (if any are due)
      - Reference excerpts: ~1000 tokens (from Reference Manager, when available)
    """
    
    def __init__(
        self,
        vault: VaultManager,
        reference_manager: Optional['ReferenceManager'] = None,
        state_manager: Optional['StateManager'] = None,
    ):
        self.vault = vault
        self.reference_manager = reference_manager
        self.state_manager = state_manager  # Optional async MongoDB backend
        self.history = ConversationHistory()
        self.lorebook = Lorebook(os.path.join(vault.vault_path, "07 - Lore"))
        self.current_session = 0
        self._last_query: Optional[str] = None  # Tracks latest player action for reference search
        self._load_session_number()
    
    def _load_session_number(self):
        """Load the current session number from the world clock."""
        clock = self.vault.read_world_clock()
        self.current_session = clock.get('session', 0)
    
    # ------------------------------------------------------------------
    # Context Building
    # ------------------------------------------------------------------
    
    def build_storyteller_context(self, current_location: Optional[str] = None,
                                   query: Optional[str] = None,
                                   character_locations: Optional[Dict[str, str]] = None,
                                   new_locations: Optional[set] = None) -> str:
        """Build the full context string for the Storyteller agent.

        Args:
            current_location: Primary/fallback location name.
            query: Player action text for reference lookups.
            character_locations: Dict mapping character names to their current locations.
                When the party is split, this provides spatial awareness for all groups.
            new_locations: Set of location names that need full description.
                Locations NOT in this set get a brief version (name + NPCs only).
                ``None`` means full descriptions everywhere (backward-compatible).
        """
        sections = []

        # 1. Party State (always included)
        sections.append(self._build_party_section())

        # 2. Current Location(s) + NPCs present
        if character_locations and len(set(character_locations.values())) > 1:
            # Party is split — build context for ALL active locations
            seen_locations = set()
            for char_name, loc in character_locations.items():
                if loc and loc not in seen_locations:
                    seen_locations.add(loc)
                    if new_locations is None or loc in new_locations:
                        sections.append(self._build_location_section(loc))
                    else:
                        sections.append(self._build_brief_location_section(loc))
            # Add character-location mapping so the AI knows who is where
            mapping_lines = ["## Party Locations (SPLIT PARTY)"]
            for char_name, loc in character_locations.items():
                mapping_lines.append(f"- **{char_name}** is at: {loc}")
            sections.append("\n".join(mapping_lines))
        elif current_location:
            if new_locations is None or current_location in new_locations:
                sections.append(self._build_location_section(current_location))
            else:
                sections.append(self._build_brief_location_section(current_location))
        
        # 3. Active Quests
        sections.append(self._build_quest_section())
        
        # 4. Due Consequences
        consequences = self._build_consequence_section()
        if consequences:
            sections.append(consequences)
        
        # 5. World Clock
        sections.append(self._build_clock_section())
        
        # 6. Conversation History (weighted)
        sections.append(self._build_history_section())
        
        # 7. Reference excerpts (lore from source books)
        ref_query = query or self._last_query
        if ref_query:
            refs = self._build_reference_section(ref_query, mode='lore')
            if refs:
                sections.append(refs)

        # 8. Lorebook triggers (keyword-matched campaign lore)
        lore_query = query or self._last_query
        if lore_query:
            lore_entries = self.lorebook.search(lore_query)
            if lore_entries:
                before = [e for e in lore_entries if e.position == "before"]
                after = [e for e in lore_entries if e.position != "before"]
                # Inject "before" entries at the front
                for entry in reversed(before):
                    sections.insert(0, f"## Lorebook: {entry.name}\n{entry.content[:800]}")
                # Inject "after" entries at the end
                for entry in after:
                    sections.append(f"## Lorebook: {entry.name}\n{entry.content[:800]}")

        return "\n\n---\n\n".join(sections)
    
    def build_solo_storyteller_context(
        self,
        character_name: str,
        location: str,
        new_locations: Optional[set] = None,
        query: Optional[str] = None,
        history: Optional['ConversationHistory'] = None,
        solo_directives: Optional[List[str]] = None,
        recap: Optional[str] = None,
    ) -> str:
        """Build context for a solo session -- single character focus.

        Args:
            character_name: The solo adventurer's name.
            location: Current location.
            new_locations: Set of locations needing full description.
            query: Player action text for reference/lorebook lookups.
            history: Per-session ConversationHistory (Phase 0.1). Falls back to
                global self.history if not provided (backward compatibility).
            solo_directives: List of narrative directive strings to inject
                (oracle, chaos, threads, NPCs, factions).
            recap: Session recap text to inject at the top.
        """
        sections = []

        # 0. Session recap (Phase 1.1)
        if recap:
            sections.append(f"## Session Recap\n{recap}")

        # 1. Solo character only (not full party)
        sections.append(self._build_single_character_section(character_name))

        # 2. Location
        if new_locations is None or location in (new_locations or set()):
            sections.append(self._build_location_section(location))
        else:
            sections.append(self._build_brief_location_section(location))

        # 3. Quests
        sections.append(self._build_quest_section())

        # 4. Clock
        sections.append(self._build_clock_section())

        # 5. History (character-filtered, using per-session history if provided)
        sections.append(self._build_solo_history_section(character_name, history=history))

        # 6. Character knowledge (always included in solo)
        knowledge = self._build_character_knowledge_section(character_name)
        if knowledge:
            sections.append(knowledge)

        # 7. Solo narrative directives (oracle, chaos, threads, NPCs, factions)
        if solo_directives:
            directive_block = "\n".join(solo_directives)
            sections.append(f"## Solo Narrative Directives\n{directive_block}")

        # 8. Lorebook
        lore_query = query or self._last_query
        if lore_query:
            lore_entries = self.lorebook.search(lore_query)
            for entry in lore_entries:
                sections.append(f"## Lorebook: {entry.name}\n{entry.content[:800]}")

        # 9. Reference excerpts
        ref_query = query or self._last_query
        if ref_query:
            refs = self._build_reference_section(ref_query, mode='lore')
            if refs:
                sections.append(refs)

        return "\n\n---\n\n".join(sections)

    def _build_single_character_section(self, character_name: str) -> str:
        """Build a party section for a single character (solo mode)."""
        party = self.vault.get_party_state()
        for member in party:
            if member['frontmatter'].get('name', '').lower() == character_name.lower():
                lines = ["## Solo Character"]
                lines.append(member['summary'])
                body = member.get('body', '')
                if body:
                    lines.append(body.strip())
                return "\n".join(lines)
        return f"## Solo Character\n**{character_name}** (no character data found)"

    def _build_solo_history_section(self, character_name: str,
                                     history: Optional['ConversationHistory'] = None) -> str:
        """Build history section filtered to a single character's events.

        Args:
            character_name: Filter to events involving this character.
            history: Per-session history (Phase 0.1). Falls back to global if not provided.
        """
        source = history or self.history
        relevant = source.get_relevant_history()
        # Include events for this character or general (no character tag)
        filtered = [
            e for e in relevant
            if e.character is None
            or e.character.lower() == character_name.lower()
        ]
        if not filtered:
            return "## Recent Events\nNo prior events in memory."

        lines = ["## Recent Events (solo -- character-filtered)"]
        for entry in filtered:
            importance = "\U0001f534" if entry.score >= 7 else "\U0001f7e1" if entry.score >= 4 else "\u26aa"
            lines.append(f"  {importance} {entry.text}")
        return "\n".join(lines)

    def _build_character_knowledge_section(self, character_name: str) -> str:
        """Build a section from accumulated character knowledge.

        Reads the character knowledge vault file and returns a formatted section,
        truncated to ~1500 chars to fit context budget.
        """
        knowledge_path = os.path.join(
            self.vault.CHARACTER_KNOWLEDGE, f"{character_name}.md"
        )
        result = self.vault.read_file(knowledge_path)
        if not result:
            return ""

        fm, body = result
        if not body or not body.strip():
            return ""

        # Truncate to fit context budget
        truncated = body.strip()[:1500]
        return f"## Character Knowledge: {character_name}\n{truncated}"

    def build_rules_lawyer_context(self, query: Optional[str] = None) -> str:
        """Build context for the Rules Lawyer — focused on mechanics."""
        sections = []
        sections.append(self._build_party_section(detailed=True))
        sections.append(self._build_history_section())
        
        # Reference excerpts (rules from source books)
        ref_query = query or self._last_query
        if ref_query:
            refs = self._build_reference_section(ref_query, mode='rules')
            if refs:
                sections.append(refs)
        
        return "\n\n---\n\n".join(sections)
    
    def build_chronicler_context(self, player_action: str, rules_response: str, story_response: str,
                                  current_location: str = None) -> str:
        """Build context for the Chronicler — the full exchange to analyze.

        Includes location and recent history so the Chronicler can detect
        recurring patterns, know WHERE events happen, and make better
        consequence/quest progress judgments.
        """
        sections = []
        sections.append(self._build_party_section())

        # Location context — so the Chronicler knows WHERE this happened
        if current_location:
            sections.append(self._build_location_section(current_location))

        sections.append(f"## Player Action\n{player_action}")
        sections.append(f"## Rules Ruling\n{rules_response}")
        sections.append(f"## Storyteller Narrative\n{story_response}")
        sections.append(self._build_quest_section())

        # Recent history — so the Chronicler can detect patterns and recurring threads
        sections.append(self._build_history_section())

        # Due consequences — so the Chronicler can recognize when one fires
        consequences = self._build_consequence_section()
        if consequences:
            sections.append(consequences)

        return "\n\n---\n\n".join(sections)
    
    def build_world_architect_context(self) -> str:
        """Build context for the World Architect — focused on lore, NPCs, locations, factions."""
        sections = []
        
        # World Clock / setting
        sections.append(self._build_clock_section())
        
        # Existing NPCs (for continuity)
        npcs = self.vault.list_files("02 - NPCs")
        if npcs:
            npc_lines = ["## Existing NPCs"]
            for npc_file in npcs[:15]:  # Cap at 15 to stay within token budget
                result = self.vault.read_file(npc_file)
                if result:
                    fm, _ = result
                    name = fm.get('name', npc_file.replace('.md', ''))
                    race = fm.get('race', '?')
                    location = fm.get('location', '?')
                    faction = fm.get('faction', '?')
                    npc_lines.append(f"- **{name}** ({race}) — {location} | {faction}")
            sections.append("\n".join(npc_lines))
        
        # Existing Locations
        locations = self.vault.list_files("03 - Locations")
        if locations:
            loc_lines = ["## Existing Locations"]
            for loc_file in locations[:15]:
                # result = self.vault.read_file(f"03 - Locations/{loc_file}")
                result = self.vault.read_file(loc_file)
                if result:
                    fm, _ = result
                    name = fm.get('name', loc_file.replace('.md', ''))
                    loc_type = fm.get('type', '?')
                    region = fm.get('region', '?')
                    loc_lines.append(f"- **{name}** ({loc_type}) — {region}")
            sections.append("\n".join(loc_lines))
        
        # Factions
        factions = self.vault.list_files("05 - Factions")
        if factions:
            faction_lines = ["## Factions"]
            for faction_file in factions[:10]:
                result = self.vault.read_file(faction_file)
                if result:
                    fm, body = result
                    name = fm.get('name', faction_file.replace('.md', ''))
                    faction_lines.append(f"- **{name}**")
                    # Include first paragraph of body for summary
                    first_para = body.strip().split('\n\n')[0][:200] if body else ""
                    if first_para:
                        faction_lines.append(f"  {first_para}")
            sections.append("\n".join(faction_lines))
        
        # Active quests (for narrative connections)
        sections.append(self._build_quest_section())
        
        # Party (brief, for reference)
        sections.append(self._build_party_section())
        
        return "\n\n---\n\n".join(sections)
    
    def build_campaign_planner_context(self) -> str:
        """Build context for the Campaign Planner — focused on session history, arcs, and pacing."""
        sections = []
        
        # World Clock
        sections.append(self._build_clock_section())
        
        # Party state (for encounter balancing)
        sections.append(self._build_party_section(detailed=True))
        
        # Active quests (for narrative thread tracking)
        sections.append(self._build_quest_section())
        
        # Due consequences (upcoming events to weave in)
        consequences = self._build_consequence_section()
        if consequences:
            sections.append(consequences)
        
        # Recent session summaries (for pacing analysis)
        session_lines = ["## Recent Session Summaries"]
        for i in range(max(0, self.current_session - 3), self.current_session + 1):
            result = self.vault.get_session(i)
            if result:
                fm, body = result
                summary_section = self._extract_section(body, 'Summary')
                if summary_section:
                    session_lines.append(f"### Session {i}")
                    session_lines.append(summary_section[:300])
        
        if len(session_lines) > 1:
            sections.append("\n".join(session_lines))
        
        # Conversation history
        sections.append(self._build_history_section())
        
        return "\n\n---\n\n".join(sections)
    
    # ------------------------------------------------------------------
    # Section Builders
    # ------------------------------------------------------------------
    
    def _build_party_section(self, detailed: bool = False) -> str:
        """Build the party state section.

        When detailed=True (Rules Lawyer), includes full character sheet body
        (stats, abilities, spells, inventory) so agents can see actual modifiers.
        """
        party = self.vault.get_party_state()
        if not party:
            return "## Party\nNo party data available."

        lines = ["## Party"]
        for member in party:
            lines.append(member['summary'])
            if detailed:
                fm = member['frontmatter']
                # Include spell slots and special resources
                slots_used = fm.get('spell_slots_used', 0)
                slots_max = fm.get('spell_slots_max', 0)
                if slots_max > 0:
                    lines.append(f"Spell Slots: {slots_max - slots_used}/{slots_max} remaining")
                loh = fm.get('lay_on_hands_pool', 0)
                if loh is not None:
                    lines.append(f"Lay on Hands Pool: {loh}")
                # Include full character sheet body (stats, abilities, spells, inventory)
                body = member.get('body', '')
                if body:
                    lines.append(body.strip())
            lines.append("")

        return "\n".join(lines)
    
    def _build_location_section(self, location_name: str) -> str:
        """Build the location + NPCs section."""
        result = self.vault.get_location(location_name)
        if not result:
            return f"## Current Location\n{location_name} (no detailed data)"
        
        fm, body = result
        lines = [f"## Current Location: {fm.get('name', location_name)}"]
        
        # Extract Description and Current State sections from body
        for section_name in ['Description', 'Current State', 'Notable Features']:
            section = self._extract_section(body, section_name)
            if section:
                lines.append(section)
        
        # Add NPCs at this location
        npcs = self.vault.get_npcs_at_location(location_name)
        if npcs:
            lines.append("\n### NPCs Present")
            for npc in npcs:
                npc_fm = npc['frontmatter']
                disposition = npc_fm.get('disposition', 'unknown')
                npc_status = npc_fm.get('status', 'alive')
                display_status = "DEAD" if npc_status == 'dead' else disposition
                lines.append(f"- **{npc_fm.get('name', '?')}** ({npc_fm.get('role', '?')}) — {display_status}")
        
        return "\n".join(lines)
    
    def _build_brief_location_section(self, location_name: str) -> str:
        """Build a condensed location section for locations already described.

        Omits Description, Current State, and Notable Features prose.
        Still includes NPCs present so the AI knows who's around.
        """
        result = self.vault.get_location(location_name)
        display_name = location_name
        if result:
            fm, _ = result
            display_name = fm.get('name', location_name)

        lines = [
            f"## Current Location: {display_name}",
            "[SAME LOCATION — already described. Focus on action/reaction, not environment.]",
        ]

        npcs = self.vault.get_npcs_at_location(location_name)
        if npcs:
            lines.append("\n### NPCs Present")
            for npc in npcs:
                npc_fm = npc['frontmatter']
                disposition = npc_fm.get('disposition', 'unknown')
                npc_status = npc_fm.get('status', 'alive')
                display_status = "DEAD" if npc_status == 'dead' else disposition
                lines.append(f"- **{npc_fm.get('name', '?')}** ({npc_fm.get('role', '?')}) — {display_status}")

        return "\n".join(lines)

    def _build_quest_section(self) -> str:
        """Build the active quests section."""
        quests = self.vault.get_active_quests()
        if not quests:
            return "## Active Quests\nNo active quests."
        
        lines = ["## Active Quests"]
        for quest in quests:
            fm = quest['frontmatter']
            lines.append(f"- **{fm.get('name', '?')}** (from {fm.get('quest_giver', '?')}) — Status: {fm.get('status', '?')}")
        
        return "\n".join(lines)
    
    def _build_consequence_section(self) -> Optional[str]:
        """Build the due consequences section (if any)."""
        due = self.vault.get_due_consequences(self.current_session)
        if not due:
            return None
        
        lines = ["## ⚠️ Due Consequences (weave these into the narrative)"]
        for c in due:
            lines.append(f"- **{c.get('event', '?')}** (impact: {c.get('impact', '?')})")
            if c.get('notes'):
                lines.append(f"  _{c['notes']}_")
        
        return "\n".join(lines)
    
    def _build_clock_section(self) -> str:
        """Build the world clock section."""
        clock = self.vault.read_world_clock()
        date = clock.get('current_date', 'unknown')
        time = clock.get('time_of_day', 'unknown')
        return f"## World Clock\n**Date:** {date} | **Time:** {time}"
    
    def _build_history_section(self) -> str:
        """Build the conversation history section with weighted entries."""
        history_text = self.history.format_for_prompt()
        return f"## Recent Events (weighted by importance)\n{history_text}"
    
    # ------------------------------------------------------------------
    # Async Context Builders (StateManager-backed, vault fallback)
    # ------------------------------------------------------------------

    @property
    def _has_db(self) -> bool:
        """True if StateManager is connected and usable."""
        return self.state_manager is not None and self.state_manager.is_connected

    async def build_storyteller_context_async(self, current_location: Optional[str] = None,
                                               query: Optional[str] = None,
                                               character_locations: Optional[Dict[str, str]] = None,
                                               new_locations: Optional[set] = None) -> str:
        """Async version of build_storyteller_context — prefers StateManager for mechanical data.

        Args:
            new_locations: Set of location names needing full description.
                ``None`` means full descriptions everywhere (backward-compatible).
        """
        sections = []

        # 1. Party State — prefer DB for HP/conditions accuracy
        sections.append(await self._build_party_section_async())

        # 2. Current Location(s) + NPCs — vault for prose, DB for NPC status
        if character_locations and len(set(character_locations.values())) > 1:
            seen_locations = set()
            for char_name, loc in character_locations.items():
                if loc and loc not in seen_locations:
                    seen_locations.add(loc)
                    if new_locations is None or loc in new_locations:
                        sections.append(await self._build_location_section_async(loc))
                    else:
                        sections.append(self._build_brief_location_section(loc))
            mapping_lines = ["## Party Locations (SPLIT PARTY)"]
            for char_name, loc in character_locations.items():
                mapping_lines.append(f"- **{char_name}** is at: {loc}")
            sections.append("\n".join(mapping_lines))
        elif current_location:
            if new_locations is None or current_location in new_locations:
                sections.append(await self._build_location_section_async(current_location))
            else:
                sections.append(self._build_brief_location_section(current_location))

        # 3. Active Quests — prefer DB
        sections.append(await self._build_quest_section_async())

        # 4. Due Consequences — prefer DB
        consequences = await self._build_consequence_section_async()
        if consequences:
            sections.append(consequences)

        # 5. World Clock
        sections.append(self._build_clock_section())

        # 6. Conversation History (weighted)
        sections.append(self._build_history_section())

        # 7. Reference excerpts
        ref_query = query or self._last_query
        if ref_query:
            refs = self._build_reference_section(ref_query, mode='lore')
            if refs:
                sections.append(refs)

        return "\n\n---\n\n".join(sections)

    async def build_rules_lawyer_context_async(self, query: Optional[str] = None) -> str:
        """Async version — DB-backed party for accurate stats."""
        sections = []
        sections.append(await self._build_party_section_async(detailed=True))
        sections.append(self._build_history_section())

        ref_query = query or self._last_query
        if ref_query:
            refs = self._build_reference_section(ref_query, mode='rules')
            if refs:
                sections.append(refs)

        return "\n\n---\n\n".join(sections)

    async def build_chronicler_context_async(self, player_action: str, rules_response: str,
                                              story_response: str, current_location: str = None) -> str:
        """Async chronicler context — DB-backed party and quests."""
        sections = []
        sections.append(await self._build_party_section_async())

        if current_location:
            sections.append(await self._build_location_section_async(current_location))

        sections.append(f"## Player Action\n{player_action}")
        sections.append(f"## Rules Ruling\n{rules_response}")
        sections.append(f"## Storyteller Narrative\n{story_response}")
        sections.append(await self._build_quest_section_async())
        sections.append(self._build_history_section())

        consequences = await self._build_consequence_section_async()
        if consequences:
            sections.append(consequences)

        return "\n\n---\n\n".join(sections)

    # ------------------------------------------------------------------
    # Async Section Builders (StateManager → vault fallback)
    # ------------------------------------------------------------------

    async def _build_party_section_async(self, detailed: bool = False) -> str:
        """Build party section. Uses StateManager if available, else vault."""
        if not self._has_db:
            return self._build_party_section(detailed)

        try:
            characters = await self.state_manager.get_all_characters()
            if not characters:
                return self._build_party_section(detailed)

            lines = ["## Party"]
            for char in characters:
                name = char.get("name", "?")
                char_class = char.get("class", char.get("char_class", "?"))
                level = char.get("level", "?")
                hp = char.get("hp", "?")
                hp_max = char.get("hp_max", "?")
                conditions = char.get("conditions", [])
                cond_str = f" [{', '.join(conditions)}]" if conditions else ""
                lines.append(f"- **{name}** (Lvl {level} {char_class}) — HP {hp}/{hp_max}{cond_str}")

                if detailed:
                    slots_used = char.get("spell_slots_used", 0)
                    slots_max = char.get("spell_slots_max", 0)
                    if slots_max > 0:
                        lines.append(f"  Spell Slots: {slots_max - slots_used}/{slots_max} remaining")
                    loh = char.get("lay_on_hands_pool")
                    if loh is not None:
                        lines.append(f"  Lay on Hands Pool: {loh}")
                lines.append("")

            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"StateManager party fetch failed, falling back to vault: {e}")
            return self._build_party_section(detailed)

    async def _build_location_section_async(self, location_name: str) -> str:
        """Build location section. Vault for prose, DB for NPC status/disposition."""
        # Vault provides the rich prose description
        base = self._build_location_section(location_name)

        # If DB is available, override NPC statuses with authoritative data
        if not self._has_db:
            return base

        try:
            npcs = await self.state_manager.get_all_npcs()
            npcs_here = [n for n in npcs if n.get("location", "").lower() == location_name.lower()]
            if not npcs_here:
                return base

            # Replace the vault's NPC section with DB-accurate statuses
            npc_lines = ["\n### NPCs Present (verified)"]
            for npc in npcs_here:
                name = npc.get("name", "?")
                role = npc.get("role", "?")
                npc_status = npc.get("status", "alive")
                disposition = npc.get("disposition", "unknown")
                display_status = "DEAD" if npc_status == "dead" else disposition
                npc_lines.append(f"- **{name}** ({role}) — {display_status}")

            # If vault base already has an NPC section, replace it
            if "### NPCs Present" in base:
                idx = base.index("### NPCs Present")
                base = base[:idx].rstrip()
            return base + "\n" + "\n".join(npc_lines)
        except Exception as e:
            logger.warning(f"StateManager NPC fetch failed: {e}")
            return base

    async def _build_quest_section_async(self) -> str:
        """Build active quests section. Uses StateManager if available."""
        if not self._has_db:
            return self._build_quest_section()

        try:
            quests = await self.state_manager.get_all_quests()
            active = [q for q in quests if q.get("status") == "active"]
            if not active:
                return "## Active Quests\nNo active quests."

            lines = ["## Active Quests"]
            for q in active:
                name = q.get("name", "?")
                giver = q.get("quest_giver", "?")
                status = q.get("status", "?")
                lines.append(f"- **{name}** (from {giver}) — Status: {status}")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"StateManager quest fetch failed: {e}")
            return self._build_quest_section()

    async def _build_consequence_section_async(self) -> Optional[str]:
        """Build due consequences section. Uses StateManager if available."""
        if not self._has_db:
            return self._build_consequence_section()

        try:
            consequences = await self.state_manager.get_pending_consequences()
            due = [c for c in consequences if c.get("trigger_session", 999) <= self.current_session]
            if not due:
                return None

            lines = ["## ⚠️ Due Consequences (weave these into the narrative)"]
            for c in due:
                lines.append(f"- **{c.get('event', '?')}** (impact: {c.get('impact', '?')})")
                if c.get("notes"):
                    lines.append(f"  _{c['notes']}_")
            return "\n".join(lines)
        except Exception as e:
            logger.warning(f"StateManager consequence fetch failed: {e}")
            return self._build_consequence_section()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    
    @staticmethod
    def _extract_section(body: str, section_name: str) -> Optional[str]:
        """Extract a named section from a markdown body."""
        lines = body.split('\n')
        capturing = False
        result = []
        
        for line in lines:
            stripped = line.strip()
            if stripped.startswith('#') and section_name.lower() in stripped.lower():
                capturing = True
                result.append(line)
                continue
            
            if capturing:
                if stripped.startswith('#') and section_name.lower() not in stripped.lower():
                    break
                result.append(line)
        
        return '\n'.join(result) if result else None
    
    # ------------------------------------------------------------------
    # Reference Integration
    # ------------------------------------------------------------------
    
    def _build_reference_section(self, query: str, mode: str = 'rules') -> Optional[str]:
        """Search extracted source books for relevant excerpts.
        
        Args:
            query: The player's action or question.
            mode: 'rules' for PHB/MM/etc, 'lore' for Dragon Heist/SCAG/etc.
        """
        if not self.reference_manager:
            return None
        assert self.reference_manager is not None
        
        try:
            if mode == 'rules':
                text = self.reference_manager.search_rules(query, max_results=2, max_tokens=800)
            else:
                text = self.reference_manager.search_lore(query, max_results=2, max_tokens=800)
            
            if not text:
                return None
            
            header = "📚 Rules Reference" if mode == 'rules' else "📚 Lore Reference"
            return f"## {header}\n{text}"
        except Exception as e:
            logger.error(f"Reference search error: {e}")
            return None
    
    # ------------------------------------------------------------------
    # Public API for event tracking
    # ------------------------------------------------------------------
    
    def record_event(self, text: str, impact: int = 5, character: str = None,
                     location: str = None, age_existing: bool = True):
        """Record a new event in the conversation history.

        Impact scale (same as Chronicler output):
          10 = Combat result, major revelation
           8 = NPC interaction, significant choice
           6 = Important discovery, moderate consequence
           4 = Movement, exploration
           2 = Flavor, ambient detail

        Args:
            text: Event description.
            impact: Base importance score (1-10).
            character: Character name involved (for per-character context).
            location: Where this event happened (for spatial grouping).
            age_existing: If False, don't age other entries (use for batched writes).
        """
        self.history.add_event(text, impact, age_existing=age_existing,
                               character=character, location=location)
        logger.info(f"Recorded event (impact={impact}, char={character}): {text[:80]}")
    
    def set_query(self, query: str):
        """Store the latest player action for reference lookups."""
        self._last_query = query
    
    def set_session(self, session_number: int):
        """Update the current session number."""
        self.current_session = session_number

    # ------------------------------------------------------------------
    # Checkpointing (persist memory across bot restarts)
    # ------------------------------------------------------------------

    def save_checkpoint(self, checkpoint_dir: str = None):
        """Save conversation history to disk so it survives bot restarts."""
        if checkpoint_dir is None:
            checkpoint_dir = os.path.join(self.vault.vault_path, "06 - World State")
        filepath = os.path.join(checkpoint_dir, "memory_checkpoint.json")
        self.history.save_to_file(filepath)

    def load_checkpoint(self, checkpoint_dir: str = None):
        """Restore conversation history from the last checkpoint."""
        if checkpoint_dir is None:
            checkpoint_dir = os.path.join(self.vault.vault_path, "06 - World State")
        filepath = os.path.join(checkpoint_dir, "memory_checkpoint.json")
        self.history.load_from_file(filepath)
