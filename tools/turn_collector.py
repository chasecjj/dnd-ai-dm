"""
TurnCollector — Collects player messages during a configurable time window
before batching them into a single pipeline invocation.

Pure Python + asyncio. No Discord imports. The caller manages all I/O.

When the first message arrives, a timer starts. Subsequent messages
within the window are accumulated. When the timer expires, all
collected messages are resolved in a single batch.

If only 1 message was collected, the callback receives it alone
so the caller can run the normal single-action path.
"""

import asyncio
import logging
import time
from typing import List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger("TurnCollector")


@dataclass
class PendingMessage:
    """A message waiting to be batched."""

    message: Any  # discord.Message (opaque to this module)
    character_name: Optional[str]
    user_input: str
    timestamp: float = field(default_factory=time.time)


class TurnCollector:
    """Time-based collection window for Auto Mode batching.

    Usage:
        collector = TurnCollector(window_seconds=45, on_resolve=my_callback)

        # In on_message handler:
        is_first = await collector.collect(message, char_name, text)
        # is_first=True means the window just opened (caller should post status)
    """

    def __init__(
        self,
        window_seconds: int = 45,
        on_resolve: Optional[Callable[[List[PendingMessage]], Awaitable[None]]] = None,
    ):
        self.window_seconds: int = window_seconds
        self._pending: List[PendingMessage] = []
        self._window_task: Optional[asyncio.Task] = None
        self._lock: asyncio.Lock = asyncio.Lock()
        self._on_resolve: Optional[Callable[[List[PendingMessage]], Awaitable[None]]] = on_resolve
        self.status_message: Any = None  # discord.Message, managed by caller
        self._enabled: bool = True

    @property
    def is_collecting(self) -> bool:
        """True if a collection window is currently active."""
        return self._window_task is not None and not self._window_task.done()

    @property
    def pending_count(self) -> int:
        return len(self._pending)

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool):
        self._enabled = value

    async def collect(
        self,
        message: Any,
        character_name: Optional[str],
        user_input: str,
    ) -> bool:
        """Add a message to the collection window.

        If this is the first message, starts the timer.
        Returns True if this was the FIRST message (window just opened).
        Returns False if added to an existing window.

        Raises RuntimeError if collection is disabled (caller should
        check .enabled first or handle directly).
        """
        async with self._lock:
            self._pending.append(PendingMessage(
                message=message,
                character_name=character_name,
                user_input=user_input,
            ))

            if self._window_task is None or self._window_task.done():
                # First message — start the window
                self._window_task = asyncio.create_task(self._window_timer())
                logger.info(f"Collection window started ({self.window_seconds}s)")
                return True  # Caller should post status message
            else:
                logger.info(
                    f"Message collected: {character_name or 'Unknown'} "
                    f"(total: {len(self._pending)})"
                )
                return False  # Caller should update status message

    async def _window_timer(self):
        """Timer task. When it expires, triggers resolution."""
        try:
            await asyncio.sleep(self.window_seconds)
        except asyncio.CancelledError:
            return  # cancel() or force_resolve() was called
        await self._resolve()

    async def _resolve(self):
        """Flush collected messages and invoke the resolution callback."""
        async with self._lock:
            messages = list(self._pending)
            self._pending.clear()
            self._window_task = None

        if not messages:
            return

        logger.info(f"Window expired. Resolving {len(messages)} message(s).")

        if self._on_resolve:
            try:
                await self._on_resolve(messages)
            except Exception as e:
                logger.error(f"Resolution callback error: {e}", exc_info=True)

    async def cancel(self):
        """Cancel the current window without resolving."""
        async with self._lock:
            if self._window_task and not self._window_task.done():
                self._window_task.cancel()
            self._pending.clear()
            self._window_task = None
        logger.info("Collection window cancelled.")

    async def force_resolve(self):
        """Immediately resolve the current window (DM triggered)."""
        if self._window_task and not self._window_task.done():
            self._window_task.cancel()
        # Wait a tick for cancellation to propagate
        await asyncio.sleep(0)
        await self._resolve()
