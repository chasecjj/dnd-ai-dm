"""
VaultManager — Centralized I/O for the Obsidian Vault.

All agents read from and write to the vault through this module.
Files use YAML frontmatter + Obsidian [[wikilinks]] for cross-referencing.
"""

import os
import re
import yaml
import json
import logging
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime
from contextlib import contextmanager
if os.name == 'nt':
    try:
        import msvcrt
        from msvcrt import LK_NBLCK, LK_UNLCK
    except ImportError:
        msvcrt = None  # type: ignore[assignment]
        LK_NBLCK = 2
        LK_UNLCK = 0
else:
    msvcrt = None  # type: ignore[assignment]
    # Dummy constants for non-Windows
    LK_NBLCK = 2
    LK_UNLCK = 0

from pydantic import ValidationError
from tools.models import PartyMember, NPC, Quest, Location

logger = logging.getLogger('VaultManager')

# ---------------------------------------------------------------------------
# YAML Frontmatter Helpers
# ---------------------------------------------------------------------------

def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """Parse YAML frontmatter from a markdown file.
    
    Returns:
        (frontmatter_dict, body_text)
    """
    if not content.startswith('---'):
        return {}, content
    
    # Find the closing ---
    end_idx = content.find('---', 3)
    if end_idx == -1:
        return {}, content
    
    yaml_str = content[3:end_idx].strip()
    body = content[end_idx + 3:].strip()
    
    try:
        frontmatter = yaml.safe_load(yaml_str) or {}
    except yaml.YAMLError as e:
        logger.error(f"YAML parse error: {e}")
        frontmatter = {}
    
    return frontmatter, body


def build_frontmatter(frontmatter: Dict[str, Any], body: str) -> str:
    """Reconstruct a markdown file with YAML frontmatter."""
    yaml_str = yaml.dump(frontmatter, default_flow_style=False, allow_unicode=True, sort_keys=False)
    return f"---\n{yaml_str}---\n{body}"


# ---------------------------------------------------------------------------
# VaultManager Class
# ---------------------------------------------------------------------------

class VaultManager:
    """Manages all file I/O for the campaign vault."""
    
    # Vault subdirectory constants
    SESSION_LOG = "00 - Session Log"
    PARTY = "01 - Party"
    NPCS = "02 - NPCs"
    LOCATIONS = "03 - Locations"
    QUESTS_ACTIVE = "04 - Quests/Active"
    QUESTS_COMPLETED = "04 - Quests/Completed"
    FACTIONS = "05 - Factions"
    WORLD_STATE = "06 - World State"
    LORE = "07 - Lore"
    TEMPLATES = "_templates"
    
    def __init__(self, vault_path: str = "campaign_vault"):
        self.vault_path = os.path.abspath(vault_path)
        if not os.path.isdir(self.vault_path):
            logger.warning(f"Vault directory not found at {self.vault_path}")
    
    # ------------------------------------------------------------------
    # Core File Operations
    # ------------------------------------------------------------------
    
    def _resolve(self, *parts: str) -> str:
        """Resolve a path relative to the vault root."""
        return os.path.join(self.vault_path, *parts)
    
    def read_file(self, relative_path: str) -> Tuple[Dict[str, Any], str]:
        """Read a vault file and return (frontmatter, body).
        
        Args:
            relative_path: Path relative to vault root (e.g., '01 - Party/Character Name.md')
        """
        full_path = self._resolve(relative_path)
        try:
            with open(full_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return parse_frontmatter(content)
        except FileNotFoundError:
            logger.error(f"Vault file not found: {full_path}")
            return {}, ""
        except Exception as e:
            logger.error(f"Error reading {full_path}: {e}")
            return {}, ""
    
    def write_file(self, relative_path: str, frontmatter: Dict[str, Any], body: str) -> bool:
        """Write a vault file with YAML frontmatter.
        
        Args:
            relative_path: Path relative to vault root.
            frontmatter: Dictionary of YAML frontmatter fields.
            body: Markdown body content.
        
        Returns:
            True on success, False on failure.
        """
        full_path = self._resolve(relative_path)
        try:
            os.makedirs(os.path.dirname(full_path), exist_ok=True)
            content = build_frontmatter(frontmatter, body)
            
            # Write with exclusive lock to prevent partial writes/corruption
            with open(full_path, 'w', encoding='utf-8') as f:
                # Lock the file descriptor
                # Lock the file descriptor
                try:
                    fd = f.fileno()
                    # Use module constants or local fallback
                    lock_mode = getattr(msvcrt, 'LK_NBLCK', LK_NBLCK)
                    unlock_mode = getattr(msvcrt, 'LK_UNLCK', LK_UNLCK)
                    msvcrt.locking(fd, lock_mode, 1)
                    f.write(content)
                    msvcrt.locking(fd, unlock_mode, 1)
                except (OSError, IOError) as e:
                    # Fallback if locking fails/not supported or file is locked by another
                    logger.warning(f"Could not acquire lock for {full_path}, writing anyway.")
                    f.write(content)
                    
            logger.info(f"Wrote vault file: {relative_path}")
            return True
        except Exception as e:
            logger.error(f"Error writing {full_path}: {e}")
            return False
    
    def list_files(self, subfolder: str) -> List[str]:
        """List all .md files in a vault subfolder.
        
        Args:
            subfolder: Subdirectory name (e.g., '01 - Party')
        
        Returns:
            List of relative paths from vault root.
        """
        folder_path = self._resolve(subfolder)
        results = []
        if not os.path.isdir(folder_path):
            return results
        
        for root, _dirs, files in os.walk(folder_path):
            for fname in files:
                if fname.endswith('.md'):
                    full = os.path.join(root, fname)
                    rel = os.path.relpath(full, self.vault_path)
                    results.append(rel)
        return sorted(results)
    
    # ------------------------------------------------------------------
    # Party Operations
    # ------------------------------------------------------------------
    
    def get_party_state(self) -> List[Dict[str, Any]]:
        """Read all party member files and return their frontmatter + key body sections.
        
        Returns a list of dicts, each with keys:
            - frontmatter: the YAML frontmatter dict
            - file: relative path
            - summary: condensed text for context assembly
        """
        party = []
        for fpath in self.list_files(self.PARTY):
            fm, body = self.read_file(fpath)
            # Extract a condensed summary for context
            summary_lines = []
            pronouns = fm.get('pronouns', '')
            pronoun_str = f" [{pronouns}]" if pronouns else ""
            summary_lines.append(f"**{fm.get('name', '?')}**{pronoun_str} — {fm.get('race', '?')} {fm.get('class', '?')} (Level {fm.get('level', '?')})")
            summary_lines.append(f"HP: {fm.get('hp_current', '?')}/{fm.get('hp_max', '?')} | AC: {fm.get('ac', '?')}")
            conditions = fm.get('conditions', [])
            if conditions:
                summary_lines.append(f"Conditions: {', '.join(conditions)}")
            party.append({
                'frontmatter': fm,
                'file': fpath,
                'summary': '\n'.join(summary_lines)
            })
        return party
    
    def update_party_member(self, name: str, updates: Dict[str, Any]) -> bool:
        """Update frontmatter fields for a party member by name.
        
        Args:
            name: Character name (must match frontmatter 'name' field).
            updates: Dict of frontmatter fields to update.
        """
        for fpath in self.list_files(self.PARTY):
            fm, body = self.read_file(fpath)
            if fm.get('name', '').lower() == name.lower():
                try:
                    # Merge and validate
                    merged = {**fm, **updates}
                    # Validate with Pydantic
                    model = PartyMember(**merged)
                    # Update with validated data
                    # model_dump is V2, dict is V1. Using dict() for broader compatibility if V1
                    if hasattr(model, 'model_dump'):
                        fm.update(model.model_dump())
                    else:
                        fm.update(model.dict())
                    
                    return self.write_file(fpath, fm, body)
                except ValidationError as e:
                    logger.error(f"Validation failed for party member {name}: {e}")
                    return False
        logger.warning(f"Party member not found: {name}")
        return False
    
    # ------------------------------------------------------------------
    # NPC Operations
    # ------------------------------------------------------------------
    
    def get_npcs_at_location(self, location: str) -> List[Dict[str, Any]]:
        """Get all NPCs whose frontmatter 'location' matches the given location."""
        results = []
        # Normalize: strip [[ ]] from wikilink format
        loc_clean = location.strip().strip('[]').lower()
        
        for fpath in self.list_files(self.NPCS):
            fm, body = self.read_file(fpath)
            npc_loc = fm.get('location', '').strip().strip('[]').lower()
            if npc_loc and loc_clean in npc_loc:
                results.append({
                    'frontmatter': fm,
                    'file': fpath,
                    'body': body
                })
        return results
    
    def get_npc(self, name: str) -> Optional[Tuple[Dict[str, Any], str]]:
        """Get a specific NPC by name. Returns (frontmatter, body) or None."""
        for fpath in self.list_files(self.NPCS):
            fm, body = self.read_file(fpath)
            if fm.get('name', '').lower() == name.lower():
                return fm, body
        return None
    
    # ------------------------------------------------------------------
    # Location Operations
    # ------------------------------------------------------------------
    
    def get_location(self, name: str) -> Optional[Tuple[Dict[str, Any], str]]:
        """Get a location file by name."""
        for fpath in self.list_files(self.LOCATIONS):
            fm, body = self.read_file(fpath)
            if fm.get('name', '').lower() == name.lower():
                return fm, body
        return None
    
    # ------------------------------------------------------------------
    # Quest Operations
    # ------------------------------------------------------------------
    
    def get_active_quests(self) -> List[Dict[str, Any]]:
        """Get all active quests."""
        quests = []
        for fpath in self.list_files(self.QUESTS_ACTIVE):
            fm, body = self.read_file(fpath)
            quests.append({'frontmatter': fm, 'file': fpath, 'body': body})
        return quests
    
    def complete_quest(self, name: str, session_number: int) -> bool:
        """Move a quest from Active to Completed."""
        for fpath in self.list_files(self.QUESTS_ACTIVE):
            fm, body = self.read_file(fpath)
            if fm.get('name', '').lower() == name.lower():
                fm['status'] = 'completed'
                fm['completed_session'] = session_number
                # Build new path in Completed folder
                filename = os.path.basename(fpath)
                new_path = os.path.join(self.QUESTS_COMPLETED, filename)
                success = self.write_file(new_path, fm, body)
                if success:
                    # Remove from Active
                    try:
                        os.remove(self._resolve(fpath))
                        logger.info(f"Quest completed and moved: {name}")
                    except Exception as e:
                        logger.error(f"Failed to remove old quest file: {e}")
                return success
        return False
    
    # ------------------------------------------------------------------
    # Session Log Operations
    # ------------------------------------------------------------------
    
    def get_latest_session(self) -> Optional[Tuple[Dict[str, Any], str]]:
        """Get the most recent session log file."""
        sessions = self.list_files(self.SESSION_LOG)
        if not sessions:
            return None
        # Sessions are named Session 000.md, Session 001.md, etc. — sorted order works.
        latest = sessions[-1]
        return self.read_file(latest)
    
    def get_session(self, number: int) -> Optional[Tuple[Dict[str, Any], str]]:
        """Get a specific session log by number."""
        filename = f"Session {number:03d}.md"
        rel_path = os.path.join(self.SESSION_LOG, filename)
        if os.path.exists(self._resolve(rel_path)):
            return self.read_file(rel_path)
        return None
    
    def append_to_session_log(self, session_number: int, event_entry: str) -> bool:
        """Append a timestamped event to a session log.

        If the session file doesn't exist, creates it from the template with
        populated frontmatter (session number, date from world clock, real date).

        Args:
            session_number: The session number.
            event_entry: The markdown table row or text to append.
        """
        filename = f"Session {session_number:03d}.md"
        rel_path = os.path.join(self.SESSION_LOG, filename)
        full_path = self._resolve(rel_path)

        try:
            if os.path.exists(full_path):
                with open(full_path, 'r', encoding='utf-8') as f:
                    content = f.read()
                # Append to the Key Events section
                content += f"\n{event_entry}"
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
            else:
                # Create a new session file from template with populated frontmatter
                clock = self.read_world_clock()
                ingame_date = clock.get('current_date', '')
                real_date = datetime.now().strftime('%Y-%m-%d')

                template_path = self._resolve(self.TEMPLATES, "session_template.md")
                if os.path.exists(template_path):
                    fm, body = self.read_file(os.path.join(self.TEMPLATES, "session_template.md"))
                    fm['session_number'] = session_number
                    fm['real_date'] = real_date
                    fm['ingame_date'] = ingame_date
                    fm['status'] = 'in_progress'
                    body = body.replace("{{session_number}}", str(session_number))
                    content = build_frontmatter(fm, body)
                    content += f"\n{event_entry}"
                else:
                    content = f"# Session {session_number}\n\n{event_entry}"

                os.makedirs(os.path.dirname(full_path), exist_ok=True)
                with open(full_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                logger.info(f"Created new session log: {filename}")

            logger.info(f"Appended event to session {session_number}")
            return True
        except Exception as e:
            logger.error(f"Error appending to session log: {e}")
            return False
    
    def update_session_summary(self, session_number: int, summary_text: str) -> bool:
        """Replace the Summary section placeholder in a session log with generated text.

        Also marks the session as 'complete' in the frontmatter.
        """
        filename = f"Session {session_number:03d}.md"
        rel_path = os.path.join(self.SESSION_LOG, filename)
        full_path = self._resolve(rel_path)

        try:
            if not os.path.exists(full_path):
                logger.warning(f"Session log {filename} not found for summary update.")
                return False

            fm, body = self.read_file(rel_path)
            fm['status'] = 'complete'

            # Replace the Summary section placeholder
            placeholder = "_One paragraph overview of what happened._"
            if placeholder in body:
                body = body.replace(placeholder, summary_text)
            else:
                # Try to insert after the ## Summary header
                if "## Summary" in body:
                    parts = body.split("## Summary", 1)
                    # Find the next ## header after Summary
                    after_header = parts[1]
                    next_section = after_header.find("\n## ")
                    if next_section > 0:
                        body = parts[0] + "## Summary\n" + summary_text + "\n" + after_header[next_section:]
                    else:
                        body = parts[0] + "## Summary\n" + summary_text + after_header
                else:
                    body += f"\n## Summary\n{summary_text}\n"

            return self.write_file(rel_path, fm, body)
        except Exception as e:
            logger.error(f"Error updating session summary: {e}")
            return False

    def increment_session(self) -> int:
        """Increment the session number in the world clock. Returns the new number."""
        clock = self.read_world_clock()
        new_session = clock.get('session', 0) + 1
        rel_path = os.path.join(self.WORLD_STATE, "clock.md")
        fm, body = self.read_file(rel_path)
        fm['session'] = new_session
        self.write_file(rel_path, fm, body)
        logger.info(f"Session number incremented to {new_session}")
        return new_session

    # ------------------------------------------------------------------
    # World Clock
    # ------------------------------------------------------------------
    
    def read_world_clock(self) -> Dict[str, Any]:
        """Read the current in-game date/time."""
        fm, _ = self.read_file(os.path.join(self.WORLD_STATE, "clock.md"))
        return fm
    
    def advance_clock(self, new_date: str, time_of_day: str, session: int) -> bool:
        """Update the world clock."""
        rel_path = os.path.join(self.WORLD_STATE, "clock.md")
        fm, body = self.read_file(rel_path)
        fm['current_date'] = new_date
        fm['time_of_day'] = time_of_day
        fm['session'] = session
        
        # Add timeline entry
        new_entry = f"| {session} | {new_date}, {time_of_day} | _(to be filled)_ |"
        body += f"\n{new_entry}"
        
        return self.write_file(rel_path, fm, body)
    
    # ------------------------------------------------------------------
    # Consequence System
    # ------------------------------------------------------------------
    
    def read_consequences(self) -> Tuple[Dict[str, Any], str]:
        """Read the consequence queue."""
        return self.read_file(os.path.join(self.WORLD_STATE, "consequences.md"))
    
    def get_due_consequences(self, current_session: int) -> List[Dict[str, Any]]:
        """Parse the consequence queue and return entries whose trigger session <= current_session.
        
        Returns a list of consequence descriptions.
        """
        _, body = self.read_consequences()
        due = []
        
        # Parse the Pending section for trigger lines
        in_pending = False
        current_entry: Dict[str, Any] = {}
        
        for line in body.split('\n'):
            stripped = line.strip()
            if stripped.startswith('## Pending'):
                in_pending = True
                continue
            if stripped.startswith('## Resolved'):
                in_pending = False
                continue
            
            if in_pending:
                if stripped.startswith('- **trigger:**'):
                    # Parse: - **trigger:** session >= N
                    match = re.search(r'session\s*>=\s*(\d+)', stripped)
                    if match:
                        trigger_session = int(match.group(1))
                        current_entry = {'trigger_session': trigger_session}
                elif stripped.startswith('**event:**') and current_entry:
                    current_entry['event'] = stripped.replace('**event:**', '').strip()
                elif stripped.startswith('**impact:**') and current_entry:
                    try:
                        current_entry['impact'] = int(stripped.replace('**impact:**', '').strip())
                    except ValueError:
                        current_entry['impact'] = 5
                elif stripped.startswith('**notes:**') and current_entry:
                    current_entry['notes'] = stripped.replace('**notes:**', '').strip()
                    # Entry complete — check if due
                    if current_entry.get('trigger_session', 999) <= current_session:
                        due.append(current_entry)
                    current_entry = {}
        
        return due

    def resolve_consequence(self, event_text: str, session_number: int) -> bool:
        """Move a consequence from Pending to Resolved after it fires in-game.

        Searches the Pending section for an entry whose event text matches
        (case-insensitive substring), removes it from Pending, and appends
        it to the Resolved section with a resolution note.

        Args:
            event_text: The event description to match (substring match).
            session_number: The session in which it was resolved.

        Returns:
            True if a matching consequence was found and resolved.
        """
        rel_path = os.path.join(self.WORLD_STATE, "consequences.md")
        fm, body = self.read_file(rel_path)

        if not body or '## Pending' not in body:
            return False

        lines = body.split('\n')
        new_lines = []
        resolved_entry_lines = []
        removing = False
        found = False
        event_lower = event_text.lower()

        for line in lines:
            stripped = line.strip()

            # Detect the start of a consequence block in Pending
            if stripped.startswith('- **trigger:**'):
                # If we were already removing a block, we've moved past it
                if removing:
                    removing = False

            # Check if this block's event matches
            if stripped.startswith('**event:**') and event_lower in stripped.lower():
                # Mark for removal — backtrack to capture the trigger line too
                found = True
                removing = True
                # The trigger line is the last line we added that starts with '- **trigger:**'
                # Pull it back out of new_lines
                backtrack = []
                while new_lines and not new_lines[-1].strip().startswith('- **trigger:**'):
                    backtrack.insert(0, new_lines.pop())
                if new_lines and new_lines[-1].strip().startswith('- **trigger:**'):
                    resolved_entry_lines.append(new_lines.pop())
                resolved_entry_lines.extend(backtrack)
                resolved_entry_lines.append(line)
                continue

            if removing and stripped.startswith('**'):
                resolved_entry_lines.append(line)
                # If this is the notes line, the block is complete
                if stripped.startswith('**notes:**'):
                    removing = False
                continue

            new_lines.append(line)

        if not found:
            return False

        # Build the resolution note
        resolution = f"  **resolved_session:** {session_number}"
        resolved_entry_lines.append(resolution)

        # Insert into the Resolved section
        resolved_block = '\n'.join(resolved_entry_lines)
        new_body = '\n'.join(new_lines)

        if '## Resolved' in new_body:
            new_body = new_body.replace('## Resolved', f"## Resolved\n{resolved_block}\n", 1)
        else:
            new_body += f"\n\n## Resolved\n{resolved_block}\n"

        self.write_file(rel_path, fm, new_body)
        logger.info(f"Resolved consequence: {event_text[:60]}...")
        return True

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------
    
    def search_vault(self, query: str, subfolders: Optional[List[str]] = None) -> List[Dict[str, Any]]:
        """Search vault files for a keyword. Returns matching files with context.
        
        Args:
            query: Search term (case-insensitive).
            subfolders: Optional list of subdirectories to limit search. Searches all if None.
        
        Returns:
            List of dicts with 'file', 'frontmatter', and 'matches' (list of matching lines).
        """
        results = []
        query_lower = query.lower()
        
        folders = subfolders or [
            self.PARTY, self.NPCS, self.LOCATIONS, 
            self.QUESTS_ACTIVE, self.QUESTS_COMPLETED,
            self.FACTIONS, self.WORLD_STATE, self.LORE, self.SESSION_LOG
        ]
        
        for folder in folders:
            for fpath in self.list_files(folder):
                fm, body = self.read_file(fpath)
                # Search in both frontmatter values and body
                fm_str = json.dumps(fm, default=str).lower()
                full_text = fm_str + '\n' + body.lower()
                
                if query_lower in full_text:
                    # Find matching lines for context
                    matches = [
                        line.strip() for line in body.split('\n')
                        if query_lower in line.lower() and line.strip()
                    ]
                    results.append({
                        'file': fpath,
                        'frontmatter': fm,
                        'matches': matches[:5]  # Limit context lines
                    })
        
        return results
    
    # ------------------------------------------------------------------
    # Faction Operations
    # ------------------------------------------------------------------
    
    def get_faction(self, name: str) -> Optional[Tuple[Dict[str, Any], str]]:
        """Get a faction by name."""
        for fpath in self.list_files(self.FACTIONS):
            fm, body = self.read_file(fpath)
            if name.lower() in fm.get('name', '').lower():
                return fm, body
        return None
    
    def update_faction_reputation(self, name: str, delta: int) -> bool:
        """Update a faction's reputation score by a delta amount."""
        for fpath in self.list_files(self.FACTIONS):
            fm, body = self.read_file(fpath)
            if name.lower() in fm.get('name', '').lower():
                current = fm.get('reputation', 0)
                fm['reputation'] = current + delta
                return self.write_file(fpath, fm, body)
        return False
