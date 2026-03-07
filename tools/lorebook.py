"""
Lorebook — Keyword-triggered lore injection for the context assembler.

Scans the campaign vault's lore directory (07 - Lore/) for markdown files
with trigger keywords in their frontmatter. When player input matches
a trigger, the relevant lore is injected into the agent's context window.

Frontmatter fields:
  triggers: [keyword1, keyword2]  — words/phrases that activate this entry
  category: deity|history|faction|location|item|custom
  position: before|after  — inject before or after main context (default: after)

If no explicit triggers are set, falls back to name + tags as implicit triggers.
"""

import os
import logging
from dataclasses import dataclass, field
from typing import List, Optional

import yaml

logger = logging.getLogger("Lorebook")


@dataclass
class LorebookEntry:
    """A single lore entry that can be triggered by keyword match."""

    name: str
    triggers: List[str]
    category: str = "general"
    position: str = "after"  # "before" or "after" main context
    content: str = ""
    source_file: str = ""


class Lorebook:
    """Scans lore files and matches them against player input by keyword."""

    def __init__(self, lore_dir: str):
        self.lore_dir = lore_dir
        self.entries: List[LorebookEntry] = []
        self._scan()

    def _scan(self):
        """Read all .md files in the lore directory and parse their frontmatter."""
        if not os.path.isdir(self.lore_dir):
            logger.info(f"Lore directory not found: {self.lore_dir}")
            return

        for filename in os.listdir(self.lore_dir):
            if not filename.endswith(".md"):
                continue

            filepath = os.path.join(self.lore_dir, filename)
            try:
                entry = self._parse_file(filepath)
                if entry:
                    self.entries.append(entry)
            except Exception as e:
                logger.warning(f"Failed to parse lore file {filename}: {e}")

        logger.info(f"Lorebook loaded {len(self.entries)} entries from {self.lore_dir}")

    def _parse_file(self, filepath: str) -> Optional[LorebookEntry]:
        """Parse a single lore markdown file into a LorebookEntry."""
        with open(filepath, "r", encoding="utf-8") as f:
            raw = f.read()

        # Parse YAML frontmatter
        if not raw.startswith("---"):
            return None

        parts = raw.split("---", 2)
        if len(parts) < 3:
            return None

        try:
            fm = yaml.safe_load(parts[1]) or {}
        except yaml.YAMLError:
            return None

        name = fm.get("name", os.path.basename(filepath).replace(".md", ""))
        body = parts[2].strip()

        # Build trigger list: explicit triggers > fallback to name + tags
        triggers = fm.get("triggers", [])
        if not triggers:
            triggers = [name.lower()]
            tags = fm.get("tags", [])
            if isinstance(tags, list):
                triggers.extend(t.lower() for t in tags if t != "lore")

        # Normalize triggers to lowercase
        triggers = [t.lower().strip() for t in triggers if t]

        return LorebookEntry(
            name=name,
            triggers=triggers,
            category=fm.get("category", "general"),
            position=fm.get("position", "after"),
            content=body,
            source_file=filepath,
        )

    def search(self, text: str) -> List[LorebookEntry]:
        """Find all lorebook entries whose triggers match the given text.

        Uses case-insensitive substring matching. A trigger matches if it
        appears as a word or phrase within the text.

        Args:
            text: Player input or query to match against.

        Returns:
            List of matching LorebookEntry objects, sorted by position
            (before entries first, then after).
        """
        if not text:
            return []

        text_lower = text.lower()
        matched = []

        for entry in self.entries:
            for trigger in entry.triggers:
                if trigger in text_lower:
                    matched.append(entry)
                    break  # One trigger match is enough

        # Sort: "before" entries first, then "after"
        matched.sort(key=lambda e: 0 if e.position == "before" else 1)
        return matched

    def reload(self):
        """Re-scan the lore directory (e.g., after new files are added)."""
        self.entries.clear()
        self._scan()
