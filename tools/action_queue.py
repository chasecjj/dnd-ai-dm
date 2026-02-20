"""
ActionQueue — Thread-safe action queue for the DM Admin Console.

Player actions are captured and held until the DM reviews and resolves them.
This is pure Python + Pydantic — no Discord imports.
"""

import asyncio
import logging
import time
from typing import Optional, Dict, List, Tuple
from uuid import uuid4

from pydantic import BaseModel, Field

logger = logging.getLogger("ActionQueue")


# ------------------------------------------------------------------
# Models
# ------------------------------------------------------------------

class RollRequest(BaseModel):
    """A single dice roll in an ordered sequence.

    Supports multi-roll actions like Attack → Damage where the player
    rolls attack first, then damage if it hits. Rolls are processed
    in index order; only one is active at a time.
    """

    index: int  # Order in the sequence (0, 1, 2...)
    roll_type: str  # "Attack", "Perception", "Damage", etc.
    formula: str  # "1d20+5"
    dc: Optional[int] = None  # Target DC (None for damage rolls or DM-adjudicated)
    result: Optional[int] = None  # Filled when player rolls
    detail: Optional[str] = None  # "1d20(13)+5 = 18"
    resolved: bool = False  # True when result has been captured


class MonsterRoll(BaseModel):
    """A dice roll made by a monster/NPC, fired by the DM from the admin console."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: float = Field(default_factory=time.time)
    monster_name: str
    roll_type: str  # "Attack", "Damage", "Initiative", etc.
    formula: str  # "1d20+4"
    target: Optional[str] = None  # Target character name, if applicable
    result: Optional[int] = None  # Filled when dice resolve
    detail: Optional[str] = None  # Full roll breakdown


class QueuedAction(BaseModel):
    """A single player action waiting in the DM's queue."""

    id: str = Field(default_factory=lambda: str(uuid4()))
    timestamp: float = Field(default_factory=time.time)

    # Discord context
    discord_user_id: int
    discord_message_id: int
    channel_id: int

    # Game context
    character_name: Optional[str] = None
    player_input: str

    # DM controls
    dm_annotation: Optional[str] = None  # Private note passed to pipeline
    is_dm_event: bool = False  # True if DM-injected event, not a player action

    # Secret/private action support
    is_secret: bool = False  # True if submitted via player's private console
    private_thread_id: Optional[int] = None  # Thread to send results to instead of game table

    # Dice — ordered sequence of rolls (attack → damage, etc.)
    rolls: List[RollRequest] = Field(default_factory=list)

    # Pre-analysis from Rules Lawyer
    rules_pre_analysis: Optional[dict] = None

    # Status lifecycle: pending → analyzing → awaiting_roll → ready → resolved
    status: str = "pending"

    @property
    def needs_roll(self) -> bool:
        """True if this action has any rolls (resolved or not)."""
        return len(self.rolls) > 0

    @property
    def current_pending_roll(self) -> Optional[RollRequest]:
        """The first unresolved roll, or None if all are done."""
        for roll in self.rolls:
            if not roll.resolved:
                return roll
        return None

    @property
    def all_rolls_resolved(self) -> bool:
        """True if all rolls in the sequence have been resolved."""
        return len(self.rolls) > 0 and all(r.resolved for r in self.rolls)

    @property
    def resolved_rolls(self) -> List[RollRequest]:
        """All rolls that have been completed."""
        return [r for r in self.rolls if r.resolved]


class ActionQueue:
    """Thread-safe action queue for the DM console.

    Uses asyncio.Lock for safe concurrent access from Discord event handlers.
    Queue mode is a toggle — when off, the bot behaves as before (auto pipeline).
    """

    def __init__(self):
        self._actions: List[QueuedAction] = []
        self._lock = asyncio.Lock()
        self._pending_rolls: Dict[int, str] = {}  # discord_user_id → action_id
        self._queue_mode: bool = False
        self._player_threads: Dict[int, int] = {}  # discord_user_id → private_thread_id
        self._last_batch: List[QueuedAction] = []  # Backup of last flushed batch for recovery
        self._monster_rolls: List[MonsterRoll] = []  # DM-initiated monster/NPC rolls

    @property
    def is_queue_mode(self) -> bool:
        return self._queue_mode

    def enable_queue_mode(self) -> None:
        self._queue_mode = True
        logger.info("Queue mode ENABLED")

    def disable_queue_mode(self) -> None:
        self._queue_mode = False
        logger.info("Queue mode DISABLED")

    def toggle_queue_mode(self) -> bool:
        """Toggle queue mode on/off. Returns the new state."""
        self._queue_mode = not self._queue_mode
        logger.info(f"Queue mode {'ENABLED' if self._queue_mode else 'DISABLED'}")
        return self._queue_mode

    async def enqueue(self, action: QueuedAction) -> None:
        """Add an action to the end of the queue."""
        async with self._lock:
            self._actions.append(action)
            logger.info(
                f"Enqueued [{action.character_name or 'Unknown'}]: "
                f"{action.player_input[:60]}... (id={action.id[:8]})"
            )

    async def remove(self, action_id: str) -> Optional[QueuedAction]:
        """Remove an action from the queue by ID. Returns the removed action or None."""
        async with self._lock:
            for i, action in enumerate(self._actions):
                if action.id == action_id:
                    removed = self._actions.pop(i)
                    self._pending_rolls.pop(removed.discord_user_id, None)
                    logger.info(f"Removed action {action_id[:8]}")
                    return removed
            return None

    async def get_all(self) -> List[QueuedAction]:
        """Return a copy of all queued actions."""
        async with self._lock:
            return list(self._actions)

    async def get_by_id(self, action_id: str) -> Optional[QueuedAction]:
        """Get a single action by ID."""
        async with self._lock:
            for action in self._actions:
                if action.id == action_id:
                    return action
            return None

    async def flush(self) -> List[QueuedAction]:
        """Return all actions and clear the queue. Used during resolve."""
        async with self._lock:
            actions = list(self._actions)
            self._actions.clear()
            self._pending_rolls.clear()
            logger.info(f"Flushed {len(actions)} actions from queue")
            return actions

    async def flush_ready(self) -> List[QueuedAction]:
        """Return only ready/pending actions. Keeps awaiting_roll actions in queue.

        Saves the flushed batch to _last_batch for recovery if the pipeline fails.
        Call confirm_batch() after successful resolution, or restore_batch() on error.
        """
        async with self._lock:
            ready = []
            remaining = []
            for action in self._actions:
                if action.status in ("ready", "pending"):
                    ready.append(action)
                else:
                    remaining.append(action)
            self._actions = remaining
            self._last_batch = list(ready)
            logger.info(f"Flushed {len(ready)} ready actions, {len(remaining)} remain")
            return ready

    async def confirm_batch(self) -> None:
        """Clear the last batch backup after successful resolution."""
        async with self._lock:
            self._last_batch.clear()

    async def restore_batch(self) -> int:
        """Restore the last flushed batch back to the queue after a pipeline failure.

        Returns the number of actions restored.
        """
        async with self._lock:
            if not self._last_batch:
                return 0
            # Prepend restored actions (they were first in the queue originally)
            for action in self._last_batch:
                action.status = "ready"  # Reset status so they can be re-resolved
            self._actions = self._last_batch + self._actions
            count = len(self._last_batch)
            self._last_batch = []
            logger.info(f"Restored {count} actions to queue after pipeline failure")
            return count

    async def update_action(self, action_id: str, **kwargs) -> bool:
        """Update fields on a queued action. Returns True if found."""
        async with self._lock:
            for action in self._actions:
                if action.id == action_id:
                    for key, value in kwargs.items():
                        if hasattr(action, key):
                            setattr(action, key, value)
                    return True
            return False

    async def set_dm_annotation(self, action_id: str, note: str) -> bool:
        """Attach a DM annotation to an action."""
        return await self.update_action(action_id, dm_annotation=note)

    async def add_dm_event(
        self, text: str, annotation: Optional[str] = None
    ) -> QueuedAction:
        """Add a DM-injected event to the queue (not a player action)."""
        action = QueuedAction(
            discord_user_id=0,
            discord_message_id=0,
            channel_id=0,
            player_input=text,
            dm_annotation=annotation,
            is_dm_event=True,
            status="ready",
        )
        async with self._lock:
            self._actions.append(action)
        logger.info(f"DM event added: {text[:60]}...")
        return action

    async def request_roll(
        self, action_id: str, roll_type: str, formula: str, dc: Optional[int] = None
    ) -> bool:
        """Add a roll request to an action's roll sequence.

        Appends a RollRequest to the action's rolls list. If this is the first
        roll, also registers the user in _pending_rolls and sets status to awaiting_roll.
        """
        async with self._lock:
            for action in self._actions:
                if action.id == action_id:
                    new_index = len(action.rolls)
                    action.rolls.append(RollRequest(
                        index=new_index,
                        roll_type=roll_type,
                        formula=formula,
                        dc=dc,
                    ))
                    action.status = "awaiting_roll"
                    # Only register pending roll if this is the current active roll
                    if action.current_pending_roll and action.current_pending_roll.index == new_index:
                        self._pending_rolls[action.discord_user_id] = action_id
                    return True
            return False

    async def request_rolls(
        self, action_id: str, rolls: List[Dict]
    ) -> bool:
        """Add multiple roll requests at once from pre-analysis.

        Args:
            rolls: List of dicts with keys: roll_type, formula, dc (optional)
        """
        async with self._lock:
            for action in self._actions:
                if action.id == action_id:
                    for i, roll_data in enumerate(rolls):
                        action.rolls.append(RollRequest(
                            index=len(action.rolls),
                            roll_type=roll_data["roll_type"],
                            formula=roll_data["formula"],
                            dc=roll_data.get("dc"),
                        ))
                    action.status = "awaiting_roll"
                    # Register for the first pending roll
                    if action.current_pending_roll is not None:
                        self._pending_rolls[action.discord_user_id] = action_id
                    return True
            return False

    async def update_roll_result(
        self, user_id: int, result: int, detail: str
    ) -> Tuple[Optional[QueuedAction], Optional[RollRequest]]:
        """Record a dice roll result for the current pending roll.

        Resolves the first unresolved roll in the action's sequence. If more
        rolls remain, keeps the action in awaiting_roll and returns the next
        pending roll so the caller can prompt for it.

        Returns:
            (action, next_roll) — action is None if no pending roll found.
            next_roll is None if all rolls are now resolved.
        """
        async with self._lock:
            action_id = self._pending_rolls.get(user_id)
            if not action_id:
                return None, None
            for action in self._actions:
                if action.id == action_id:
                    # Find the current pending roll and resolve it
                    current = action.current_pending_roll
                    if not current:
                        self._pending_rolls.pop(user_id, None)
                        return None, None

                    current.result = result
                    current.detail = detail
                    current.resolved = True
                    logger.info(
                        f"Roll result for {action.character_name}: "
                        f"{current.roll_type} = {result} ({detail})"
                    )

                    # Check if there's another roll in the sequence
                    next_roll = action.current_pending_roll
                    if next_roll:
                        # Keep pending — caller should prompt for next roll
                        return action, next_roll
                    else:
                        # All rolls resolved — action is ready
                        self._pending_rolls.pop(user_id, None)
                        action.status = "ready"
                        return action, None
            return None, None

    async def reorder(self, action_id: str, new_position: int) -> bool:
        """Move an action to a new position in the queue."""
        async with self._lock:
            for i, action in enumerate(self._actions):
                if action.id == action_id:
                    self._actions.pop(i)
                    new_position = max(0, min(new_position, len(self._actions)))
                    self._actions.insert(new_position, action)
                    return True
            return False

    # ------------------------------------------------------------------
    # Monster / NPC rolls
    # ------------------------------------------------------------------
    async def add_monster_roll(self, monster_name: str, roll_type: str,
                               formula: str, target: Optional[str] = None) -> MonsterRoll:
        """Create a monster roll entry (result filled after Foundry rolls)."""
        roll = MonsterRoll(
            monster_name=monster_name,
            roll_type=roll_type,
            formula=formula,
            target=target,
        )
        async with self._lock:
            self._monster_rolls.append(roll)
        logger.info(f"Monster roll added: {monster_name} {roll_type} {formula}")
        return roll

    async def resolve_monster_roll(self, roll_id: str, result: int, detail: str) -> bool:
        """Fill in the result of a monster roll after Foundry dice resolve."""
        async with self._lock:
            for roll in self._monster_rolls:
                if roll.id == roll_id:
                    roll.result = result
                    roll.detail = detail
                    logger.info(f"Monster roll resolved: {roll.monster_name} {roll.roll_type} = {result}")
                    return True
            return False

    async def get_monster_rolls(self) -> List[MonsterRoll]:
        """Return all monster rolls (resolved and unresolved)."""
        async with self._lock:
            return list(self._monster_rolls)

    async def flush_monster_rolls(self) -> List[MonsterRoll]:
        """Return and clear all resolved monster rolls. Called during batch resolve."""
        async with self._lock:
            resolved = [r for r in self._monster_rolls if r.result is not None]
            self._monster_rolls = [r for r in self._monster_rolls if r.result is None]
            return resolved

    # ------------------------------------------------------------------
    # Player thread tracking
    # ------------------------------------------------------------------
    def register_player_thread(self, user_id: int, thread_id: int) -> None:
        """Register a player's private console thread."""
        self._player_threads[user_id] = thread_id

    def get_player_thread(self, user_id: int) -> Optional[int]:
        """Get a player's private console thread ID, or None."""
        return self._player_threads.get(user_id)

    @property
    def count(self) -> int:
        return len(self._actions)

    @property
    def has_pending_rolls(self) -> bool:
        return bool(self._pending_rolls)

    # ------------------------------------------------------------------
    # Sync-safe snapshots (for embed builders and non-async contexts)
    # ------------------------------------------------------------------
    @property
    def actions_snapshot(self) -> List[QueuedAction]:
        """Return a copy of all actions. Safe for sync callers (embed builders)."""
        return list(self._actions)

    @property
    def monster_rolls_snapshot(self) -> List[MonsterRoll]:
        """Return a copy of all monster rolls. Safe for sync callers."""
        return list(self._monster_rolls)

    def is_player_thread(self, channel_id: int) -> bool:
        """Check if a channel ID belongs to a registered player thread."""
        return channel_id in self._player_threads.values()
