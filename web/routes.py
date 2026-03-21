"""REST API routes for Quest Mirror.

Provides endpoints for character listing, solo session management,
and session history.  All bot-manager access uses deferred imports
(getter functions) to avoid circular imports at module load time.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Lazy getters — defer import of bot.client until call time
# ---------------------------------------------------------------------------


def _get_vault():
    from bot.client import vault
    return vault


def _get_solo_manager():
    from bot.client import solo_manager
    return solo_manager


def _get_context_assembler():
    from bot.client import context_assembler
    return context_assembler


def _get_state_manager():
    from bot.client import state_manager
    return state_manager


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class CreateSessionRequest(BaseModel):
    character_name: str


# ---------------------------------------------------------------------------
# Router
# ---------------------------------------------------------------------------

router = APIRouter()


# ---------------------------------------------------------------------------
# GET /characters — list available player characters
# ---------------------------------------------------------------------------


@router.get("/characters")
async def list_characters() -> List[Dict[str, Any]]:
    """List available player characters from the vault.

    If MongoDB is connected, merge mechanical stats (hp, ac, level, etc.)
    from the state manager.
    """
    vault = _get_vault()
    party_dir = os.path.join(vault.vault_path, "01 - Party")

    characters: List[Dict[str, Any]] = []

    if not os.path.isdir(party_dir):
        return characters

    for fname in sorted(os.listdir(party_dir)):
        if not fname.endswith(".md"):
            continue
        name = fname.rsplit(".", 1)[0]
        characters.append({"name": name, "source": "vault"})

    # Merge MongoDB mechanical stats if available
    state_manager = _get_state_manager()
    if state_manager.is_connected:
        try:
            all_chars = await state_manager.get_all_characters()
            db_map = {c["name"].lower(): c for c in all_chars if "name" in c}
            for char in characters:
                db_entry = db_map.get(char["name"].lower())
                if db_entry:
                    char["source"] = "vault+db"
                    for key in ("hp_current", "hp_max", "ac", "level", "race", "class"):
                        if key in db_entry:
                            char[key] = db_entry[key]
        except Exception:
            logger.warning("Failed to merge MongoDB character data", exc_info=True)

    return characters


# ---------------------------------------------------------------------------
# GET /characters/{name} — full character details
# ---------------------------------------------------------------------------


@router.get("/characters/{name}")
async def get_character(name: str) -> Dict[str, Any]:
    """Get full character details.  Tries MongoDB first, falls back to vault."""
    state_manager = _get_state_manager()

    # Try MongoDB first
    if state_manager.is_connected:
        try:
            doc = await state_manager.get_character(name)
            if doc:
                doc["source"] = "db"
                return doc
        except Exception:
            logger.warning("MongoDB character lookup failed", exc_info=True)

    # Fall back to vault
    vault = _get_vault()
    party_files = vault.list_files("01 - Party")
    for fpath in party_files:
        fname = os.path.basename(fpath)
        file_name = fname.rsplit(".", 1)[0]
        if file_name.lower() == name.lower():
            fm, body = vault.read_file(fpath)
            return {
                "name": fm.get("name", file_name),
                "source": "vault",
                "frontmatter": fm,
                "body": body,
            }

    raise HTTPException(status_code=404, detail=f"Character '{name}' not found")


# ---------------------------------------------------------------------------
# GET /solo/sessions — list all active solo sessions
# ---------------------------------------------------------------------------


@router.get("/solo/sessions")
async def list_sessions() -> List[Dict[str, Any]]:
    """List all active solo sessions."""
    solo_manager = _get_solo_manager()
    sessions = solo_manager.all_active()

    result: List[Dict[str, Any]] = []
    for s in sessions:
        result.append({
            "id": s.id,
            "character_name": s.character_name,
            "current_location": s.current_location,
            "turn_count": s.turn_count,
            "started_at": datetime.fromtimestamp(s.started_at, tz=timezone.utc).isoformat(),
            "chaos_factor": s.chaos_factor,
            "status": "paused" if s.is_paused else "active",
            "is_web": s.thread_id <= 0,
        })

    return result


# ---------------------------------------------------------------------------
# POST /solo/sessions — create a new web-based solo session
# ---------------------------------------------------------------------------


@router.post("/solo/sessions")
async def create_session(body: CreateSessionRequest) -> Dict[str, Any]:
    """Create a new web-based (Quest Mirror) solo session."""
    if not body.character_name or not body.character_name.strip():
        raise HTTPException(status_code=400, detail="character_name is required")

    character_name = body.character_name.strip()
    solo_manager = _get_solo_manager()

    # Determine starting location
    vault = _get_vault()
    try:
        world_clock = vault.read_world_clock()
        location = world_clock.get("current_location", "The Yawning Portal")
    except Exception:
        location = "The Yawning Portal"

    # Determine session number
    context_assembler = _get_context_assembler()
    session_number = context_assembler.current_session

    session = await solo_manager.start_web_session(
        character_name=character_name,
        current_location=location,
        session_number=session_number,
    )

    if session is None:
        raise HTTPException(
            status_code=409,
            detail=f"Character '{character_name}' already has an active session",
        )

    return {
        "id": session.id,
        "character_name": session.character_name,
        "current_location": session.current_location,
        "turn_count": session.turn_count,
        "started_at": datetime.fromtimestamp(session.started_at, tz=timezone.utc).isoformat(),
        "chaos_factor": session.chaos_factor,
        "status": "active",
        "is_web": True,
        "session_number": session.session_number,
    }


# ---------------------------------------------------------------------------
# GET /solo/sessions/{session_id}/history — paginated manuscript history
# ---------------------------------------------------------------------------


@router.get("/solo/sessions/{session_id}/history")
async def get_session_history(session_id: str) -> Dict[str, Any]:
    """Get the narrative history for a solo session."""
    solo_manager = _get_solo_manager()
    session = solo_manager.get_by_session_id(session_id)

    if session is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")

    return {
        "session_id": session.id,
        "character_name": session.character_name,
        "turn_count": session.turn_count,
        "recent_narratives": session.recent_narratives,
    }
