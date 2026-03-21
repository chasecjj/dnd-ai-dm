"""Breath-group narrative chunking for Quest Mirror streaming.

Splits narrative text into clause-level chunks suitable for dramatic
streaming over WebSocket.  The client owns pacing (e.g. 300 ms between
groups); this module only produces the chunks.

Key invariant
-------------
``"".join(g["text"] for g in groups).strip() == text.strip()``

Every character of the original text is preserved across chunks.
"""

from __future__ import annotations

import re
from typing import Any

# ---------------------------------------------------------------------------
# Sentence-boundary pattern
# ---------------------------------------------------------------------------
# Matches a sentence-ending punctuation mark (.!?) followed by whitespace
# and then either an uppercase letter or a quote character — indicating a
# new sentence is starting.
_SENTENCE_BOUNDARY = re.compile(
    r'(?<=[.!?])'       # lookbehind: sentence-ending punctuation
    r'(\s+)'             # capture the whitespace between sentences
    r'(?=[A-Z"\u201c\'])'  # lookahead: uppercase or opening quote
)

# ---------------------------------------------------------------------------
# Clause-boundary patterns (only applied to chunks > 60 chars)
# ---------------------------------------------------------------------------
# We split at: ", and ", ", but ", ", or ", ", nor ", ", yet ", ", so ",
# semicolons, or em dashes.  The split keeps punctuation attached to the
# preceding chunk and whitespace attached to the following chunk.
_CLAUSE_BOUNDARY = re.compile(
    r'(?<=[,])'          # lookbehind: comma
    r'(\s+)'             # capture whitespace
    r'(?=(?:and|but|or|nor|yet|so)\s)'  # lookahead: conjunction + space
    r'|'
    r'(?<=[;])'          # lookbehind: semicolon
    r'(\s+)'             # capture whitespace
    r'|'
    r'(?<=\u2014)'       # lookbehind: em dash
    r'()'                # capture nothing (em dash has no trailing space)
)

# Maximum chunk length before we try clause splitting.
_LONG_THRESHOLD = 60


def _is_inside_quote(text: str, pos: int) -> bool:
    """Return True if *pos* falls inside a quoted string.

    Counts straight double-quotes and smart open/close quotes preceding
    *pos* to determine nesting.
    """
    # Count straight double quotes before pos
    straight = text[:pos].count('"')
    if straight % 2 == 1:
        return True

    # Count smart quotes: open without matching close
    opens = text[:pos].count('\u201c')
    closes = text[:pos].count('\u201d')
    if opens > closes:
        return True

    return False


def _split_at_sentences(text: str) -> list[str]:
    """Split *text* at sentence boundaries, preserving all characters."""
    parts: list[str] = []
    last = 0

    for m in _SENTENCE_BOUNDARY.finditer(text):
        # The match starts right after the punctuation mark (due to the
        # lookbehind).  The captured group is the whitespace separator.
        split_pos = m.start()
        if _is_inside_quote(text, split_pos):
            continue
        parts.append(text[last:split_pos])
        last = split_pos

    parts.append(text[last:])
    return [p for p in parts if p]


def _split_long_chunk(chunk: str) -> list[str]:
    """If *chunk* exceeds the threshold, try to split at clause boundaries."""
    if len(chunk.strip()) <= _LONG_THRESHOLD:
        return [chunk]

    # Don't split inside quoted dialogue
    stripped = chunk.strip()
    if stripped.startswith('"') or stripped.startswith('\u201c') or stripped.startswith("'"):
        return [chunk]

    parts: list[str] = []
    last = 0

    for m in _CLAUSE_BOUNDARY.finditer(chunk):
        split_pos = m.start()
        if _is_inside_quote(chunk, split_pos):
            continue
        # Only split if it would produce non-trivial pieces
        before = chunk[last:split_pos]
        if len(before.strip()) < 10:
            continue
        parts.append(chunk[last:split_pos])
        last = split_pos

    parts.append(chunk[last:])
    result = [p for p in parts if p]
    return result if len(result) > 1 else [chunk]


def chunk_narrative(text: str, mood: str = "neutral") -> list[dict[str, Any]]:
    """Split narrative text into breath-group chunks.

    Parameters
    ----------
    text:
        The narrative text to chunk.
    mood:
        Mood label passed through to every chunk (default ``"neutral"``).

    Returns
    -------
    list[dict]:
        Each dict contains ``text``, ``mood``, ``breath_group``, and
        ``is_final``.  An empty or whitespace-only *text* returns ``[]``.
    """
    if not text or not text.strip():
        return []

    # Phase 1: sentence-level splitting
    sentence_chunks = _split_at_sentences(text)

    # Phase 2: clause-level splitting of long chunks
    all_chunks: list[str] = []
    for chunk in sentence_chunks:
        all_chunks.extend(_split_long_chunk(chunk))

    # Build output dicts
    groups: list[dict[str, Any]] = []
    for i, chunk_text in enumerate(all_chunks):
        groups.append({
            "text": chunk_text,
            "mood": mood,
            "breath_group": i,
            "is_final": False,
        })

    if groups:
        groups[-1]["is_final"] = True

    return groups
