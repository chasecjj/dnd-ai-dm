"""
Foundry VTT Error Types — Structured exception hierarchy.

Lets callers distinguish retryable failures (relay down, timeout)
from non-retryable ones (bad UUID, auth rejected) so the retry loop
only retries what makes sense.
"""


class FoundryError(Exception):
    """Base class for all Foundry VTT errors."""
    pass


class FoundryConnectionError(FoundryError):
    """Relay is unreachable or returned a server error (5xx). Retryable."""
    pass


class FoundryTimeoutError(FoundryError):
    """Request timed out waiting for relay/Foundry response. Retryable."""
    pass


class FoundryRateLimitError(FoundryError):
    """Relay returned 429 Too Many Requests. Retryable after backoff."""
    pass


class FoundryOfflineError(FoundryError):
    """No Foundry clients are connected to the relay. Retryable later."""
    pass


class FoundryNotFoundError(FoundryError):
    """The requested entity (Actor, Scene, etc.) does not exist (404). NOT retryable."""
    pass


class FoundryAuthError(FoundryError):
    """API key rejected or client ID invalid (401/403). NOT retryable without config change."""
    pass
