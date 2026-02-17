"""
RateLimiter — Token bucket rate limiter for API calls.

Prevents burning through Gemini quota and handles Discord 429s gracefully.
"""

import time
import asyncio
import logging
from typing import Optional

logger = logging.getLogger('RateLimiter')


class RateLimiter:
    """Token bucket rate limiter.

    Allows up to `max_tokens` requests in a rolling window. Tokens refill
    at a steady rate. Callers use `await limiter.acquire()` before making
    an API call — it will sleep if the bucket is empty.

    Args:
        max_tokens: Maximum burst size (e.g., 15 for Gemini Flash free tier).
        refill_rate: Tokens added per second (e.g., 0.25 = 15 per minute).
        name: Label for logging.
    """

    def __init__(self, max_tokens: int = 15, refill_rate: float = 0.25, name: str = "default"):
        self.max_tokens = max_tokens
        self.refill_rate = refill_rate
        self.name = name
        self.tokens = float(max_tokens)
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    def _refill(self):
        """Add tokens based on elapsed time since last refill."""
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.max_tokens, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    async def acquire(self):
        """Wait until a token is available, then consume one.

        If the bucket is empty, sleeps until at least one token is available.
        """
        async with self._lock:
            self._refill()

            if self.tokens < 1.0:
                wait_time = (1.0 - self.tokens) / self.refill_rate
                logger.warning(f"[{self.name}] Rate limit — waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
                self._refill()

            self.tokens -= 1.0

    @property
    def available(self) -> float:
        """Current number of available tokens (without consuming)."""
        self._refill()
        return self.tokens


# Pre-configured limiters for common use
gemini_limiter = RateLimiter(max_tokens=15, refill_rate=0.25, name="gemini")
discord_limiter = RateLimiter(max_tokens=5, refill_rate=1.0, name="discord")
