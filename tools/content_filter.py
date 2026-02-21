"""
Content Filter — Blocklist-based content filter for player input.

Fast (no LLM calls), reliable for known vocabulary.
Applied at pipeline entry before GameState construction.
"""

import re
import logging
from typing import Tuple

logger = logging.getLogger("ContentFilter")

# Blocklist of terms that should never be processed or narrated.
# Uses word-boundary matching to avoid false positives (e.g., "assassin").
# This list should be expanded as needed based on session logs.
_BLOCKLIST_PATTERNS = [
    # Racial/ethnic slurs
    r"\bn[i\*]gg[ae\*]r?s?\b",
    r"\bk[i\*]ke[s]?\b",
    r"\bsp[i\*]c[s]?\b",
    r"\bch[i\*]nk[s]?\b",
    r"\bw[e\*]tb[a\*]ck[s]?\b",
    r"\bg[o\*]{2}k[s]?\b",
    r"\bcoon[s]?\b",
    # Homophobic slurs
    r"\bf[a\*]gg?[o\*]t[s]?\b",
    r"\btr[a\*]nn[yie]+[s]?\b",
    r"\bdyke[s]?\b",
    # Sexual content
    r"\br[a\*]pe[sd]?\b",
    r"\bmolest",
    # Other severe terms
    r"\bretard(ed)?\b",
]

# Compile patterns once at import time for performance
_COMPILED_PATTERNS = [
    re.compile(pattern, re.IGNORECASE) for pattern in _BLOCKLIST_PATTERNS
]


def filter_content(text: str) -> Tuple[str, bool]:
    """Filter inappropriate content from player input.

    Args:
        text: Raw player input text.

    Returns:
        (filtered_text, was_filtered) — filtered_text has bad terms replaced,
        was_filtered is True if any replacements were made.
    """
    was_filtered = False
    filtered = text

    for pattern in _COMPILED_PATTERNS:
        if pattern.search(filtered):
            was_filtered = True
            filtered = pattern.sub("[inappropriate]", filtered)

    if was_filtered:
        logger.warning(f"Content filtered from input: {text[:100]}...")

    return filtered, was_filtered
