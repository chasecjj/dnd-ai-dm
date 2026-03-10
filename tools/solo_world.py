"""
SoloWorld — Thread tracking, NPC registry, and faction dynamics for solo play.

Post-processes ChroniclerOutput to extract and track:
- Plot threads / quest lines (with dormancy detection)
- NPCs encountered (with motivation and disposition tracking)
- Factions (with periodic activity generation)

All data is stored on SoloSession and persisted to MongoDB.
Pure Python — no Discord imports.
"""

import logging
import re
from typing import Dict, List, Optional

logger = logging.getLogger("SoloWorld")


# ---------------------------------------------------------------------------
# Thread / Quest Tracking (Phase 2.2)
# ---------------------------------------------------------------------------

class SoloThread:
    """A plot thread or quest tracked during solo play."""

    def __init__(
        self,
        title: str,
        status: str = "active",
        priority: int = 5,
        created_turn: int = 0,
        last_mentioned_turn: int = 0,
    ):
        self.title = title
        self.status = status  # active, dormant, resolved
        self.priority = priority  # 1-10
        self.created_turn = created_turn
        self.last_mentioned_turn = last_mentioned_turn

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "status": self.status,
            "priority": self.priority,
            "created_turn": self.created_turn,
            "last_mentioned_turn": self.last_mentioned_turn,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SoloThread":
        return cls(
            title=data["title"],
            status=data.get("status", "active"),
            priority=data.get("priority", 5),
            created_turn=data.get("created_turn", 0),
            last_mentioned_turn=data.get("last_mentioned_turn", 0),
        )


class ThreadTracker:
    """Manages plot threads for a solo session."""

    DORMANT_THRESHOLD = 10  # Turns since last mention before marking dormant

    def __init__(self):
        self.threads: List[SoloThread] = []

    def add_thread(self, title: str, turn: int, priority: int = 5):
        """Register a new plot thread."""
        # Don't duplicate
        for t in self.threads:
            if t.title.lower() == title.lower():
                t.last_mentioned_turn = turn
                t.status = "active"
                return
        thread = SoloThread(
            title=title, created_turn=turn,
            last_mentioned_turn=turn, priority=priority,
        )
        self.threads.append(thread)
        logger.info(f"New thread registered: '{title}' (turn {turn})")

    def mention_thread(self, title: str, turn: int):
        """Update last_mentioned_turn for a thread."""
        for t in self.threads:
            if t.title.lower() == title.lower():
                t.last_mentioned_turn = turn
                if t.status == "dormant":
                    t.status = "active"
                    logger.info(f"Thread reactivated: '{title}'")
                return

    def resolve_thread(self, title: str):
        """Mark a thread as resolved."""
        for t in self.threads:
            if t.title.lower() == title.lower():
                t.status = "resolved"
                logger.info(f"Thread resolved: '{title}'")
                return

    def check_dormancy(self, current_turn: int):
        """Mark threads as dormant if not mentioned recently."""
        for t in self.threads:
            if t.status == "active":
                turns_since = current_turn - t.last_mentioned_turn
                if turns_since >= self.DORMANT_THRESHOLD:
                    t.status = "dormant"
                    logger.info(
                        f"Thread went dormant: '{t.title}' "
                        f"(last mentioned {turns_since} turns ago)"
                    )

    def get_active(self) -> List[SoloThread]:
        return [t for t in self.threads if t.status == "active"]

    def get_dormant(self) -> List[SoloThread]:
        return [t for t in self.threads if t.status == "dormant"]

    def get_all_unresolved(self) -> List[SoloThread]:
        return [t for t in self.threads if t.status != "resolved"]

    def to_list(self) -> List[dict]:
        return [t.to_dict() for t in self.threads]

    @classmethod
    def from_list(cls, data: List[dict]) -> "ThreadTracker":
        tracker = cls()
        tracker.threads = [SoloThread.from_dict(d) for d in data]
        return tracker


# Quest-related keywords for heuristic thread detection
QUEST_KEYWORDS = [
    "find", "search", "locate", "rescue", "retrieve", "deliver",
    "investigate", "discover", "explore", "protect", "defend",
    "defeat", "destroy", "steal", "negotiate", "convince",
    "escort", "gather", "collect", "solve", "mystery",
    "missing", "lost", "hidden", "secret", "treasure",
    "bounty", "contract", "reward", "quest", "mission",
]


def extract_threads_from_chronicler(
    chronicler_output: dict,
    narrative: str,
    current_turn: int,
) -> List[dict]:
    """Heuristic thread extraction from chronicler output and narrative.

    Scans scene_changes, npc_updates, quest_updates, and narrative text
    for quest-related patterns. Returns potential new threads for registration.

    Args:
        chronicler_output: Dict from chronicler (events, npc_updates, etc.)
        narrative: The storyteller's narrative text.
        current_turn: Current turn number.

    Returns:
        List of dicts with 'title' and 'priority' keys.
    """
    candidates = []

    # Check quest_updates for new/active quests
    for quest in chronicler_output.get("quest_updates", []):
        if isinstance(quest, dict):
            name = quest.get("name", "")
            status = quest.get("status", "active")
            if name and status == "active":
                candidates.append({"title": name, "priority": 7})

    # Check NPC interactions for implied quests
    for npc in chronicler_output.get("npc_updates", []):
        if isinstance(npc, dict):
            notes = npc.get("notes", "") or ""
            name = npc.get("name", "")
            for keyword in QUEST_KEYWORDS:
                if keyword in notes.lower():
                    # Try to extract a thread title from the notes
                    title = f"{name}'s request" if name else notes[:50]
                    candidates.append({"title": title, "priority": 5})
                    break

    # Check scene_changes for location-based hooks
    scene = chronicler_output.get("scene_changes") or {}
    new_loc = scene.get("new_location")
    if new_loc and scene.get("location_changed"):
        # New location arrival can imply exploration threads
        candidates.append({"title": f"Explore {new_loc}", "priority": 3})

    return candidates


# ---------------------------------------------------------------------------
# NPC Autonomy (Phase 2.3)
# ---------------------------------------------------------------------------

class SoloNPC:
    """An NPC encountered during solo play with motivation tracking."""

    def __init__(
        self,
        name: str,
        disposition: str = "neutral",
        motivation: str = "",
        location: str = "",
        last_seen_turn: int = 0,
    ):
        self.name = name
        self.disposition = disposition  # friendly, neutral, hostile, unknown
        self.motivation = motivation
        self.location = location
        self.last_seen_turn = last_seen_turn

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "disposition": self.disposition,
            "motivation": self.motivation,
            "location": self.location,
            "last_seen_turn": self.last_seen_turn,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SoloNPC":
        return cls(
            name=data["name"],
            disposition=data.get("disposition", "neutral"),
            motivation=data.get("motivation", ""),
            location=data.get("location", ""),
            last_seen_turn=data.get("last_seen_turn", 0),
        )


class SoloNPCRegistry:
    """Registry of NPCs encountered during a solo session."""

    def __init__(self):
        self.npcs: Dict[str, SoloNPC] = {}  # name_lower -> NPC

    def register(self, name: str, turn: int, disposition: str = "neutral",
                 location: str = "", motivation: str = ""):
        """Register or update an NPC."""
        key = name.lower()
        if key in self.npcs:
            npc = self.npcs[key]
            npc.last_seen_turn = turn
            if disposition:
                npc.disposition = disposition
            if location:
                npc.location = location
            if motivation:
                npc.motivation = motivation
        else:
            self.npcs[key] = SoloNPC(
                name=name, disposition=disposition,
                motivation=motivation, location=location,
                last_seen_turn=turn,
            )
            logger.info(f"NPC registered: {name}")

    def get_active_agents(self, current_turn: int, unseen_threshold: int = 5) -> List[SoloNPC]:
        """Get NPCs not seen recently who have known motivations.

        These NPCs might be doing things off-screen that the PC discovers.
        """
        agents = []
        for npc in self.npcs.values():
            turns_since = current_turn - npc.last_seen_turn
            if turns_since >= unseen_threshold and npc.motivation:
                agents.append(npc)
        return agents

    def get_all(self) -> List[SoloNPC]:
        return list(self.npcs.values())

    def to_list(self) -> List[dict]:
        return [npc.to_dict() for npc in self.npcs.values()]

    @classmethod
    def from_list(cls, data: List[dict]) -> "SoloNPCRegistry":
        registry = cls()
        for d in data:
            npc = SoloNPC.from_dict(d)
            registry.npcs[npc.name.lower()] = npc
        return registry


def extract_npcs_from_chronicler(chronicler_output: dict, current_turn: int) -> List[dict]:
    """Extract NPC data from chronicler output for registry updates.

    Reads npc_updates and new_npcs from the chronicler output.
    Infers motivation from NPC notes field.

    Returns:
        List of dicts suitable for SoloNPCRegistry.register().
    """
    results = []

    # Existing NPCs updated
    for npc in chronicler_output.get("npc_updates", []):
        if isinstance(npc, dict):
            entry = {
                "name": npc.get("name", ""),
                "disposition": npc.get("disposition", "neutral"),
                "location": npc.get("location", ""),
                "motivation": _infer_motivation(npc.get("notes", "")),
            }
            if entry["name"]:
                results.append(entry)

    # New NPCs introduced
    for npc in chronicler_output.get("new_npcs", []):
        if isinstance(npc, dict):
            entry = {
                "name": npc.get("name", ""),
                "disposition": npc.get("disposition", "neutral"),
                "location": npc.get("location", ""),
                "motivation": npc.get("personality", ""),  # Use personality as initial motivation
            }
            if entry["name"]:
                results.append(entry)

    return results


def _infer_motivation(notes: str) -> str:
    """Infer NPC motivation from the notes field using simple heuristics."""
    if not notes:
        return ""

    # Look for motivation-indicating phrases
    motivation_patterns = [
        r"(?:wants?|seeks?|tries?|trying|attempting|looking for|searching for)\s+(.{10,60})",
        r"(?:goal|objective|mission|purpose):\s*(.{10,60})",
        r"(?:needs?|requires?|demands?)\s+(.{10,60})",
    ]
    for pattern in motivation_patterns:
        match = re.search(pattern, notes, re.IGNORECASE)
        if match:
            return match.group(1).strip().rstrip(".")

    # If no pattern found but notes are short enough, use them directly
    if len(notes) <= 80:
        return notes
    return ""


def build_npc_activity_directive(active_npcs: List[SoloNPC], current_turn: int) -> str:
    """Build storyteller directive for off-screen NPC activity."""
    if not active_npcs:
        return ""

    lines = ["[NPC ACTIVITY — these characters have been acting off-screen:"]
    for npc in active_npcs[:3]:  # Cap at 3 to avoid directive bloat
        turns_since = current_turn - npc.last_seen_turn
        lines.append(
            f'  - "{npc.name}" ({npc.disposition}, goal: {npc.motivation}) '
            f"unseen {turns_since} turns. Their actions may create consequences "
            f"the PC discovers."
        )
    lines.append("]")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Faction Dynamics (Phase 3.1)
# ---------------------------------------------------------------------------

class SoloFaction:
    """A faction tracked during solo play."""

    def __init__(
        self,
        name: str,
        goals: str = "",
        power_level: int = 3,
        disposition_to_pc: str = "neutral",
        active: bool = True,
        last_action_turn: int = 0,
    ):
        self.name = name
        self.goals = goals
        self.power_level = max(1, min(5, power_level))
        self.disposition_to_pc = disposition_to_pc
        self.active = active
        self.last_action_turn = last_action_turn

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "goals": self.goals,
            "power_level": self.power_level,
            "disposition_to_pc": self.disposition_to_pc,
            "active": self.active,
            "last_action_turn": self.last_action_turn,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SoloFaction":
        return cls(
            name=data["name"],
            goals=data.get("goals", ""),
            power_level=data.get("power_level", 3),
            disposition_to_pc=data.get("disposition_to_pc", "neutral"),
            active=data.get("active", True),
            last_action_turn=data.get("last_action_turn", 0),
        )


class FactionTracker:
    """Tracks faction dynamics during solo play."""

    ACTION_INTERVAL = 5  # Turns between faction activity prompts

    def __init__(self):
        self.factions: Dict[str, SoloFaction] = {}

    def register(self, name: str, goals: str = "", power_level: int = 3,
                 disposition: str = "neutral", turn: int = 0):
        """Register a new faction or update an existing one."""
        key = name.lower()
        if key in self.factions:
            faction = self.factions[key]
            if goals:
                faction.goals = goals
            if disposition:
                faction.disposition_to_pc = disposition
        else:
            self.factions[key] = SoloFaction(
                name=name, goals=goals, power_level=power_level,
                disposition_to_pc=disposition, last_action_turn=turn,
            )
            logger.info(f"Faction registered: {name}")

    def tick(self, current_turn: int) -> List[str]:
        """Check which factions should generate activity this turn.

        Returns list of faction event prompt hints.
        """
        hints = []
        for faction in self.factions.values():
            if not faction.active:
                continue
            turns_since = current_turn - faction.last_action_turn
            if turns_since >= self.ACTION_INTERVAL:
                hint = (
                    f'The {faction.name} ({faction.disposition_to_pc} to PC, '
                    f'power {faction.power_level}/5) are pursuing: {faction.goals}. '
                    f'They have been active off-screen for {turns_since} turns.'
                )
                hints.append(hint)
                faction.last_action_turn = current_turn
        return hints

    def get_active(self) -> List[SoloFaction]:
        return [f for f in self.factions.values() if f.active]

    def to_list(self) -> List[dict]:
        return [f.to_dict() for f in self.factions.values()]

    @classmethod
    def from_list(cls, data: List[dict]) -> "FactionTracker":
        tracker = cls()
        for d in data:
            faction = SoloFaction.from_dict(d)
            tracker.factions[faction.name.lower()] = faction
        return tracker


def build_faction_directive(faction_hints: List[str]) -> str:
    """Build storyteller directive for faction movements."""
    if not faction_hints:
        return ""

    lines = ["[WORLD MOVEMENT — faction activity to weave naturally:"]
    for hint in faction_hints[:2]:  # Cap at 2 factions per turn
        lines.append(f"  - {hint}")
    lines.append("]")
    return "\n".join(lines)


def build_thread_directive(
    active_threads: List[SoloThread],
    dormant_threads: List[SoloThread],
    current_turn: int,
) -> str:
    """Build storyteller directive for thread status."""
    if not active_threads and not dormant_threads:
        return ""

    lines = ["[ACTIVE THREADS:"]
    for i, t in enumerate(active_threads, 1):
        lines.append(f'  {i}. "{t.title}" (active, priority {t.priority}/10)')

    for t in dormant_threads:
        turns_dormant = current_turn - t.last_mentioned_turn
        lines.append(
            f'  - "{t.title}" (dormant {turns_dormant} turns — WEAVE BACK IN)'
        )

    lines.append("]")
    return "\n".join(lines)
