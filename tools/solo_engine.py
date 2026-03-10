"""
SoloEngine — Oracle grading, chaos tracking, and narrative directive coordination.

Implements the core solo-specific mechanics that augment the AI DM pipeline:
- OutcomeGrade: Maps dice check results to oracle-style outcomes ("Yes, and..." etc.)
- ChaosTracker: Tracks escalating tension and triggers random events/scene alterations
- NarrativeDirectiveCoordinator: Caps active directives per turn to prevent incoherent output

Pure Python — no Discord imports, no database imports.
"""

import logging
import random
from enum import Enum
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("SoloEngine")


# ---------------------------------------------------------------------------
# Oracle System — Graduated Outcomes (Phase 1.3)
# ---------------------------------------------------------------------------

class OutcomeGrade(Enum):
    """Maps dice outcomes to narrative oracle grades."""
    CRITICAL_SUCCESS = "critical_success"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILURE = "failure"
    CRITICAL_FAILURE = "critical_failure"


# Oracle language mapping for storyteller context injection
OUTCOME_ORACLE = {
    OutcomeGrade.CRITICAL_SUCCESS: (
        '"Yes, and..." — The action succeeds spectacularly with an additional benefit'
    ),
    OutcomeGrade.SUCCESS: (
        '"Yes" — The action succeeds as intended'
    ),
    OutcomeGrade.PARTIAL: (
        '"Yes, but..." — The action succeeds with a complication or cost'
    ),
    OutcomeGrade.FAILURE: (
        '"No, but..." — The action fails, but something unexpected softens the blow'
    ),
    OutcomeGrade.CRITICAL_FAILURE: (
        '"No, and..." — The action fails and creates an additional complication'
    ),
}

# Narration instructions per grade for storyteller guardrails
OUTCOME_NARRATION = {
    OutcomeGrade.CRITICAL_SUCCESS: (
        "Narrate a spectacular success. The character achieves their goal AND gains "
        "something extra — new information, an advantageous position, an impressed NPC, "
        "or a resource bonus. Make it feel earned and exciting."
    ),
    OutcomeGrade.SUCCESS: (
        "Narrate a clean success. The character achieves exactly what they intended. "
        "No complications, no bonuses — just competence rewarded."
    ),
    OutcomeGrade.PARTIAL: (
        "Narrate a qualified success. The character achieves their goal, BUT introduce "
        "a complication: a resource cost, unwanted attention, collateral damage, a time "
        "constraint, or a partial result. The complication should create a new decision point."
    ),
    OutcomeGrade.FAILURE: (
        "Narrate a failure with a silver lining. The character doesn't achieve their goal, "
        "BUT something mitigates the failure: new information revealed, an alternative path "
        "discovered, an NPC intervenes, or the situation changes in an unexpected way. "
        "Never make failure a dead end."
    ),
    OutcomeGrade.CRITICAL_FAILURE: (
        "Narrate a dramatic failure that compounds the situation. The character fails AND "
        "a new problem emerges: an enemy alerted, equipment damaged, an NPC's trust broken, "
        "or the environment shifts against them. Make it dramatic but survivable — "
        "this is a story complication, not a punishment."
    ),
}


def grade_outcome(roll: int, dc: int, is_nat_1: bool = False, is_nat_20: bool = False) -> OutcomeGrade:
    """Grade a dice check result into an oracle outcome.

    Args:
        roll: The total roll result (with modifiers).
        dc: The difficulty class.
        is_nat_1: Whether a natural 1 was rolled.
        is_nat_20: Whether a natural 20 was rolled.

    Returns:
        An OutcomeGrade enum value.
    """
    if is_nat_20 or roll >= dc + 5:
        return OutcomeGrade.CRITICAL_SUCCESS
    elif roll >= dc:
        return OutcomeGrade.SUCCESS
    elif roll >= dc - 3:
        return OutcomeGrade.PARTIAL
    elif is_nat_1 or roll <= dc - 10:
        return OutcomeGrade.CRITICAL_FAILURE
    else:
        return OutcomeGrade.FAILURE


def build_oracle_directive(grade: OutcomeGrade) -> str:
    """Build the storyteller context injection for an oracle grade."""
    oracle_text = OUTCOME_ORACLE[grade]
    narration = OUTCOME_NARRATION[grade]
    return f"[OUTCOME: {oracle_text}]\n[NARRATION GUIDE: {narration}]"


# ---------------------------------------------------------------------------
# Chaos Factor / Tension Escalation (Phase 2.1)
# ---------------------------------------------------------------------------

class SceneAlteration(Enum):
    """How the current scene is modified by chaos."""
    NORMAL = "normal"
    ALTERED = "altered"      # Scene plays out differently than expected
    INTERRUPTED = "interrupted"  # Completely different scene occurs


class ChaosTracker:
    """Tracks escalating tension via a chaos factor (1-9).

    Higher chaos = more random events and scene alterations.
    Based on Mythic GM Emulator's chaos system.
    """

    MIN_CHAOS = 1
    MAX_CHAOS = 9
    DEFAULT_CHAOS = 5

    # Random event types, weighted by narrative value
    EVENT_TYPES = [
        "npc_action",       # An NPC does something off-screen that affects the scene
        "environment_shift", # Weather, lighting, or terrain changes
        "discovery",        # The character notices something previously hidden
        "complication",     # A new obstacle or threat emerges
        "thread_callback",  # A dormant plot thread resurfaces
    ]

    def __init__(self, factor: int = 5):
        self.factor = max(self.MIN_CHAOS, min(self.MAX_CHAOS, factor))

    def adjust(self, direction: str):
        """Adjust chaos up or down based on scene outcome.

        Args:
            direction: "up" (player lost control) or "down" (player gained control).
        """
        if direction == "up" and self.factor < self.MAX_CHAOS:
            self.factor += 1
            logger.debug(f"Chaos factor increased to {self.factor}")
        elif direction == "down" and self.factor > self.MIN_CHAOS:
            self.factor -= 1
            logger.debug(f"Chaos factor decreased to {self.factor}")

    def check_random_event(self) -> Optional[str]:
        """Roll for a random event. Returns event type or None.

        Chance = (chaos_factor - 2) / 10 (so chaos 5 = 30%, chaos 9 = 70%).
        Below factor 3, no random events trigger.
        """
        threshold = self.factor - 2
        if threshold <= 0:
            return None
        roll = random.randint(1, 10)
        if roll <= threshold:
            event_type = random.choice(self.EVENT_TYPES)
            logger.info(f"Chaos random event triggered: {event_type} (roll={roll}, threshold={threshold}, factor={self.factor})")
            return event_type
        return None

    def check_scene_alteration(self) -> SceneAlteration:
        """Check if the next scene should be altered.

        Roll d10; if ≤ (factor - 2), scene is altered (twisted, not replaced).
        Interrupted scenes are disabled — they derail player intent too aggressively.
        """
        threshold = self.factor - 2
        if threshold <= 0:
            return SceneAlteration.NORMAL
        d10 = random.randint(1, 10)
        if d10 <= threshold:
            return SceneAlteration.ALTERED
        return SceneAlteration.NORMAL

    def assess_chronicler_output(self, chronicler_output: dict) -> str:
        """Assess chaos direction from chronicler output (post-processing).

        Checks scene_changes and character_updates for indicators:
        - Player lost control: location forced, HP lost, consequences gained → chaos up
        - Player dominated: quest completed, enemy defeated → chaos down

        Returns:
            "up", "down", or "none"
        """
        score = 0

        # Check character updates
        char_updates = chronicler_output.get("character_updates", [])
        for update in char_updates:
            if isinstance(update, dict):
                hp = update.get("hp_current")
                if hp is not None:
                    # HP loss suggests player losing control
                    score += 1
                conditions = update.get("conditions", [])
                if conditions:
                    score += 1

        # Check scene changes
        scene = chronicler_output.get("scene_changes") or {}
        if scene.get("location_changed"):
            # Forced location change can mean chaos
            score += 1

        # Check events for combat/consequences
        events = chronicler_output.get("events", [])
        for event in events:
            if isinstance(event, dict):
                etype = event.get("type", "")
                if etype == "combat":
                    score += 1
                elif etype == "decision":
                    score -= 1  # Player making decisions = control

        # Check quest completions
        quest_updates = chronicler_output.get("quest_updates", [])
        for quest in quest_updates:
            if isinstance(quest, dict):
                if quest.get("status") == "completed":
                    score -= 2

        if score >= 2:
            return "up"
        elif score <= -1:
            return "down"
        return "none"

    def to_dict(self) -> dict:
        return {"factor": self.factor}

    @classmethod
    def from_dict(cls, data: dict) -> "ChaosTracker":
        return cls(factor=data.get("factor", cls.DEFAULT_CHAOS))


def build_chaos_directive(factor: int, alteration: SceneAlteration,
                          event_type: Optional[str]) -> str:
    """Build storyteller context injection for chaos state."""
    parts = [f"[CHAOS FACTOR: {factor}/9"]

    if alteration == SceneAlteration.ALTERED:
        parts.append("Scene: ALTERED — weave an unexpected twist INTO the current scene. "
                      "Don't replace what the player is doing — add a wrinkle that complicates "
                      "or enriches it. The player's action still resolves, but with an added element.")

    if event_type:
        event_descriptions = {
            "npc_action": "Weave in a detail suggesting an NPC the character has met is "
                          "active off-screen — evidence of their actions, not a scene takeover.",
            "environment_shift": "Add a subtle environmental detail that creates atmosphere — "
                                 "a sound, a shift in lighting, a smell. Flavor, not a new scene.",
            "discovery": "The character notices something small but interesting — a clue, "
                         "a dropped item, a detail they almost missed. A hook, not a redirect.",
            "complication": "Add a minor wrinkle to the current action — a time pressure, "
                            "an observer, a small obstacle. Enriches the scene, doesn't replace it.",
            "thread_callback": "Include a brief callback to a previous encounter — a familiar "
                               "face in a crowd, a symbol they've seen before. A thread tug, not a yank.",
        }
        desc = event_descriptions.get(event_type, "A minor random detail enriches the scene.")
        parts.append(f"Random Event ({event_type}): {desc}")

    return ". ".join(parts) + "]"


# ---------------------------------------------------------------------------
# Narrative Directive Coordinator (Phase 2.4)
# ---------------------------------------------------------------------------

class DirectivePriority(Enum):
    """Priority levels for narrative directives (lower = higher priority)."""
    ORACLE = 1       # Always active when dice are rolled
    CHAOS_EVENT = 2  # When chaos triggers
    DORMANT_THREAD = 3  # Thread reminders
    NPC_ACTIVITY = 4    # Off-screen NPC actions
    FACTION_EVENT = 5   # Faction movements


class NarrativeDirective:
    """A single narrative instruction for the storyteller."""

    def __init__(self, priority: DirectivePriority, text: str):
        self.priority = priority
        self.text = text


def coordinate_directives(
    directives: List[NarrativeDirective],
    max_active: int = 2,
) -> Tuple[List[str], List[NarrativeDirective]]:
    """Select the top directives and queue the rest.

    Args:
        directives: All candidate directives for this turn.
        max_active: Maximum directives to inject (default 2).

    Returns:
        Tuple of (active_directive_texts, queued_directives).
    """
    if not directives:
        return [], []

    # Sort by priority (lower enum value = higher priority)
    sorted_dirs = sorted(directives, key=lambda d: d.priority.value)

    active = sorted_dirs[:max_active]
    queued = sorted_dirs[max_active:]

    active_texts = [d.text for d in active]

    if queued:
        logger.debug(
            f"Directive coordinator: {len(active)} active, {len(queued)} queued "
            f"(queued priorities: {[d.priority.name for d in queued]})"
        )

    return active_texts, queued
