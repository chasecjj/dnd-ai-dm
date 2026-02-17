"""
ContextAssembler — Builds focused, dynamic prompts from the vault.

Replaces all hardcoded context. Uses weighted memory decay
so important events persist longer in the AI's context window
while flavor text fades naturally.
"""

import json
import os
import logging
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from tools.vault_manager import VaultManager

if TYPE_CHECKING:
    from tools.reference_manager import ReferenceManager

logger = logging.getLogger('ContextAssembler')


class MemoryEntry:
    """A single event/fact in the conversation history with a weighted impact score."""
    
    def __init__(self, text: str, impact: int = 5, turns_ago: int = 0):
        self.text = text
        self.base_impact = impact  # 1-10 scale
        self.turns_ago = turns_ago
    
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
        return f"MemoryEntry(score={self.score:.1f}, turns_ago={self.turns_ago}, text='{self.text[:50]}...')"


class ConversationHistory:
    """Manages the weighted conversation history for an agent."""
    
    INCLUSION_THRESHOLD = 1.5  # Events scoring below this are dropped
    
    def __init__(self):
        self.entries: List[MemoryEntry] = []
    
    def add_event(self, text: str, impact: int = 5):
        """Add a new event to history. All existing entries age by 1 turn."""
        for entry in self.entries:
            entry.turns_ago += 1
        self.entries.append(MemoryEntry(text=text, impact=impact, turns_ago=0))
    
    def get_relevant_history(self, max_entries: int = 20) -> List[MemoryEntry]:
        """Get history entries that are still above the inclusion threshold,
        sorted by score (highest first), capped at max_entries.
        """
        active = [e for e in self.entries if e.score >= self.INCLUSION_THRESHOLD]
        # Sort by score descending
        active.sort(key=lambda e: e.score, reverse=True)
        return active[:max_entries]
    
    def format_for_prompt(self, max_entries: int = 15) -> str:
        """Format the relevant history as a string for injection into a prompt."""
        relevant = self.get_relevant_history(max_entries)
        if not relevant:
            return "No prior events in memory."
        
        lines = []
        for entry in relevant:
            # Show score as a visual indicator of importance
            importance = "🔴" if entry.score >= 7 else "🟡" if entry.score >= 4 else "⚪"
            lines.append(f"  {importance} {entry.text}")
        
        return "\n".join(lines)
    
    def clear(self):
        """Clear all history."""
        self.entries.clear()

    def save_to_file(self, filepath: str):
        """Serialize conversation history to a JSON file for persistence across restarts."""
        data = [
            {"text": e.text, "base_impact": e.base_impact, "turns_ago": e.turns_ago}
            for e in self.entries
        ]
        try:
            os.makedirs(os.path.dirname(filepath), exist_ok=True)
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Saved {len(data)} history entries to {filepath}")
        except Exception as e:
            logger.error(f"Failed to save history: {e}")

    def load_from_file(self, filepath: str):
        """Restore conversation history from a JSON checkpoint file."""
        if not os.path.exists(filepath):
            logger.info(f"No history checkpoint found at {filepath}")
            return
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.entries = [
                MemoryEntry(text=e['text'], impact=e['base_impact'], turns_ago=e['turns_ago'])
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
    
    def __init__(self, vault: VaultManager, reference_manager: Optional['ReferenceManager'] = None):
        self.vault = vault
        self.reference_manager = reference_manager
        self.history = ConversationHistory()
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
    
    def build_storyteller_context(self, current_location: Optional[str] = None, query: Optional[str] = None) -> str:
        """Build the full context string for the Storyteller agent.
        
        This is injected as the system instruction, replacing hardcoded prompts.
        """
        sections = []
        
        # 1. Party State (always included)
        sections.append(self._build_party_section())
        
        # 2. Current Location + NPCs present
        if current_location:
            sections.append(self._build_location_section(current_location))
        
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
        
        return "\n\n---\n\n".join(sections)
    
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
        """Build the party state section."""
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
                alive = npc_fm.get('alive', True)
                status = "DEAD" if not alive else disposition
                lines.append(f"- **{npc_fm.get('name', '?')}** ({npc_fm.get('role', '?')}) — {status}")
        
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
    
    def record_event(self, text: str, impact: int = 5):
        """Record a new event in the conversation history.
        
        Impact scale (same as Chronicler output):
          10 = Combat result, major revelation
           8 = NPC interaction, significant choice
           6 = Important discovery, moderate consequence
           4 = Movement, exploration
           2 = Flavor, ambient detail
        """
        self.history.add_event(text, impact)
        logger.info(f"Recorded event (impact={impact}): {text[:80]}")
    
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
