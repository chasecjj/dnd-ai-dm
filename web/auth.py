"""Passphrase-based authentication for Quest Mirror.

Single-user auth: a shared passphrase (QUEST_MIRROR_SECRET env var) is
exchanged for an opaque in-memory token.  Tokens live only for the lifetime
of the process — a restart invalidates everything, which is fine for a
solo D&D session companion.

Security notes
--------------
* ``secrets.compare_digest`` is used for passphrase comparison to avoid
  timing-side-channel leaks.
* ``secrets.token_hex(32)`` produces 64 hex chars of cryptographically
  random data for each session token.
"""

from __future__ import annotations

import os
import secrets
from typing import Optional, Set

# ---------------------------------------------------------------------------
# Module-level state
# ---------------------------------------------------------------------------

_active_tokens: Set[str] = set()

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_token() -> str:
    """Return a new 64-character cryptographically random hex token."""
    return secrets.token_hex(32)


def check_passphrase(passphrase: str) -> Optional[str]:
    """Validate *passphrase* against the ``QUEST_MIRROR_SECRET`` env var.

    Returns a freshly generated token on success, or ``None`` on failure.
    The returned token is automatically added to the active set.
    """
    expected = os.environ.get("QUEST_MIRROR_SECRET")
    if expected is None:
        return None

    # Both operands must be str (or bytes) for compare_digest.
    if not secrets.compare_digest(passphrase, expected):
        return None

    token = generate_token()
    _active_tokens.add(token)
    return token


def validate_token(token: str) -> bool:
    """Return ``True`` if *token* is in the active set."""
    return token in _active_tokens


def revoke_token(token: str) -> None:
    """Remove *token* from the active set (no-op if absent)."""
    _active_tokens.discard(token)


def clear_all_tokens() -> None:
    """Remove every active token (used on shutdown)."""
    _active_tokens.clear()
