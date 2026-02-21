"""
Player Identity Resolution — Centralized PLAYER_MAP lookup.

Tries multiple Discord name properties in order to find a match.
Pure Python — no discord imports. The caller passes name candidates
via the convenience wrapper resolve_from_message_author().
"""

import logging
from typing import Optional, Dict

logger = logging.getLogger("PlayerIdentity")

# Module-level map, populated at startup from .env
_player_map: Dict[str, str] = {}


def init_player_map(raw_map: Dict[str, str]) -> None:
    """Initialize the player map from parsed .env data.

    Called once at startup from bot/client.py.
    All keys are stored lowercased.
    """
    global _player_map
    _player_map = {k.lower(): v for k, v in raw_map.items()}
    logger.info(f"Player map initialized with {len(_player_map)} entries: {list(_player_map.keys())}")


def resolve_character_name(*name_candidates: Optional[str]) -> Optional[str]:
    """Try multiple name strings against the player map.

    Args:
        *name_candidates: Strings to try, in priority order.
            Typical order: username, global_name, display_name, nick.

    Returns:
        Character name if found, None if no match.
    """
    for name in name_candidates:
        if name is None:
            continue
        key = name.strip().lower()
        if key in _player_map:
            logger.debug(f"Resolved '{key}' -> '{_player_map[key]}'")
            return _player_map[key]
    return None


def resolve_from_message_author(author) -> Optional[str]:
    """Extract all name candidates from a discord User/Member and resolve.

    Accepts any object with .name, .global_name, .display_name attributes.
    Also tries .nick for guild Members. Uses getattr() to avoid importing
    discord types.
    """
    return resolve_character_name(
        getattr(author, 'name', None),
        getattr(author, 'global_name', None),
        getattr(author, 'display_name', None),
        getattr(author, 'nick', None),
    )


def get_player_map() -> Dict[str, str]:
    """Return a copy of the current player map."""
    return dict(_player_map)
