"""
Session Wrapup — Post-session cleanup for session logs and NPC files.

Called from End Session button handler. Three independent steps:
  1. cleanup_session_log  — Gemini deduplicates/reorders Key Events table
  2. create_missing_npcs  — Mechanical sweep: MongoDB NPCs → vault files
  3. consolidate_npc_notes — Gemini merges raw per-turn NPC bullets into clean prose

Each step is independently try/excepted at the orchestrator level so failures
never block session end. Pure Python — no Discord imports.
"""

import json
import logging
import re
from typing import Any, Dict, List, Optional

import google.genai as genai

logger = logging.getLogger("SessionWrapup")


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

async def run_session_wrapup(
    client,
    vault,
    context_assembler,
    state_manager,
    session_number: int,
) -> Dict[str, Any]:
    """Run all post-session cleanup steps.

    Args:
        client: Google Gemini client.
        vault: VaultManager instance.
        context_assembler: ContextAssembler instance.
        state_manager: StateManager instance (may be None in vault-only mode).
        session_number: The session that just ended.

    Returns:
        Dict summarizing what was done.
    """
    results = {"log_cleaned": False, "npcs_created": 0, "npcs_consolidated": 0}

    try:
        results["log_cleaned"] = await cleanup_session_log(
            client, vault, context_assembler, session_number
        )
    except Exception as e:
        logger.error(f"Session log cleanup failed: {e}", exc_info=True)

    try:
        results["npcs_created"] = await create_missing_npcs(
            vault, state_manager, session_number
        )
    except Exception as e:
        logger.error(f"NPC creation sweep failed: {e}", exc_info=True)

    try:
        results["npcs_consolidated"] = await consolidate_npc_notes(
            client, vault, session_number
        )
    except Exception as e:
        logger.error(f"NPC consolidation failed: {e}", exc_info=True)

    logger.info(f"Session {session_number} wrapup complete: {results}")
    return results


# ---------------------------------------------------------------------------
# Step 1: Clean up session log
# ---------------------------------------------------------------------------

async def cleanup_session_log(
    client, vault, context_assembler, session_number: int
) -> bool:
    """Replace raw Key Events table with a clean, deduplicated version."""
    from tools.rate_limiter import gemini_limiter

    session_data = vault.get_session(session_number)
    if not session_data:
        logger.warning(f"No session log found for session {session_number}")
        return False

    fm, body = session_data

    # Extract current Key Events section
    raw_events = _extract_section(body, "Key Events", "Combat Encounters")
    if not raw_events or raw_events.strip() == "":
        raw_events = _extract_section(body, "Key Events", None)

    # Also check for events dumped below DM Notes (the known bug)
    dm_notes_events = _extract_section(body, "DM Notes", None)

    # Get weighted memory as a more reliable timeline
    history_text = context_assembler.history.format_for_prompt(max_entries=30)

    prompt = f"""You are cleaning up a D&D session log. Given the raw events and weighted memory below, produce a CLEAN Key Events table.

## Raw Key Events (may have duplicates, wrong order, or junk)
{raw_events}

## Events found below DM Notes (misplaced — should be in Key Events)
{dm_notes_events or "None"}

## Weighted Memory (most reliable timeline, ordered by importance)
{history_text}

Rules:
- Deduplicate: merge events that describe the same thing into one row
- Order chronologically using Early/Mid/Late for the Time column
- Keep the markdown table format: | Time | Event | Impact | NPCs Involved |
- Each event should be one clear sentence
- Remove all "Session started" entries
- Fill in NPCs Involved where you can identify them
- Filter out crude/inappropriate content — keep the gameplay-relevant version
- Impact should be 2-10 (2=flavor, 4=minor, 6=significant, 8=major, 10=critical)
- Output ONLY the table rows, no header row, no other text
- Do NOT include the | Time | Event | Impact | NPCs Involved | header
- Do NOT include the |------|-------|--------|---------------| separator"""

    await gemini_limiter.acquire()
    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=genai.types.GenerateContentConfig(temperature=0.1),
    )

    clean_rows = response.text.strip()
    if not clean_rows:
        logger.warning("Gemini returned empty session log cleanup")
        return False

    # Rebuild the session body with clean Key Events
    new_body = _replace_key_events(body, clean_rows)
    if new_body == body:
        logger.info("Session log unchanged after cleanup")
        return True

    # Write back
    from tools.vault_manager import build_frontmatter
    content = build_frontmatter(fm, new_body)

    filename = f"Session {session_number:03d}.md"
    rel_path = f"{vault.SESSION_LOG}/{filename}"
    vault.write_file(rel_path, fm, new_body)

    logger.info(f"Session {session_number} log cleaned up")
    return True


def _extract_section(body: str, heading: str, next_heading: Optional[str]) -> str:
    """Extract content between two ## headings."""
    pattern = f"## {re.escape(heading)}"
    match = re.search(pattern, body)
    if not match:
        return ""

    start = body.find("\n", match.start())
    if start < 0:
        return ""
    start += 1

    if next_heading:
        end_pattern = f"## {re.escape(next_heading)}"
        end_match = re.search(end_pattern, body[start:])
        if end_match:
            return body[start : start + end_match.start()].strip()

    return body[start:].strip()


def _replace_key_events(body: str, clean_rows: str) -> str:
    """Replace the Key Events section content with clean rows.

    Also removes any stray event rows found below DM Notes.
    """
    table_header = (
        "| Time | Event | Impact | NPCs Involved |\n"
        "|------|-------|--------|---------------|\n"
    )

    # Find Key Events section
    ke_match = re.search(r"## Key Events", body)
    if not ke_match:
        return body

    ke_start = body.find("\n", ke_match.start()) + 1

    # Find the next ## heading after Key Events
    next_heading = re.search(r"\n## ", body[ke_start:])
    if next_heading:
        ke_end = ke_start + next_heading.start()
    else:
        ke_end = len(body)

    # Rebuild: everything before Key Events content + clean table + everything after
    new_body = body[:ke_start] + table_header + clean_rows + "\n\n" + body[ke_end:].lstrip("\n")

    # Clean up any stray event rows below DM Notes
    dm_notes_match = re.search(r"## DM Notes", new_body)
    if dm_notes_match:
        dm_start = new_body.find("\n", dm_notes_match.start()) + 1
        dm_section = new_body[dm_start:]
        # Remove lines that look like table rows (| ... | ... |)
        cleaned_lines = []
        for line in dm_section.split("\n"):
            if not re.match(r"^\s*\|.*\|.*\|.*\|.*\|", line):
                cleaned_lines.append(line)
        new_body = new_body[:dm_start] + "\n".join(cleaned_lines)

    return new_body


# ---------------------------------------------------------------------------
# Step 2: Create missing NPC vault files
# ---------------------------------------------------------------------------

async def create_missing_npcs(
    vault, state_manager, session_number: int
) -> int:
    """Create vault files for NPCs in MongoDB that don't have vault files.

    Returns number of NPCs created.
    """
    if state_manager is None or not state_manager.is_connected:
        logger.info("StateManager not connected — skipping NPC creation sweep")
        return 0

    # Get all NPCs from MongoDB
    try:
        all_npcs = await state_manager.get_all_npcs()
    except Exception as e:
        logger.warning(f"Could not fetch NPCs from MongoDB: {e}")
        return 0

    if not all_npcs:
        return 0

    # Filter to NPCs seen this session
    session_npcs = [
        npc for npc in all_npcs
        if npc.get("last_seen_session") == session_number
    ]

    created = 0
    for npc in session_npcs:
        name = npc.get("name", "")
        if not name:
            continue

        # Check if vault file exists
        existing = vault.get_npc(name)
        if existing:
            continue

        # Create from MongoDB data
        npc_data = {
            "name": name,
            "race": npc.get("race", "Unknown"),
            "role": npc.get("role", "Unknown"),
            "location": npc.get("location", "Unknown"),
            "disposition": npc.get("disposition", "neutral"),
            "description": npc.get("description", "_Unknown._"),
            "personality": npc.get("personality", "_Unknown._"),
        }

        success = vault.create_npc_file(npc_data, session_number)
        if success:
            created += 1
            logger.info(f"Created missing NPC file: {name}")

    return created


# ---------------------------------------------------------------------------
# Step 3: Consolidate NPC notes
# ---------------------------------------------------------------------------

async def consolidate_npc_notes(
    client, vault, session_number: int
) -> int:
    """Consolidate raw per-turn NPC session update bullets into clean prose.

    Returns number of NPCs consolidated.
    """
    from tools.rate_limiter import gemini_limiter

    # Find NPC files with session update sections
    session_heading = f"### Session {session_number} Update"
    npcs_to_consolidate = []

    for fpath in vault.list_files(vault.NPCS):
        result = vault.read_file(fpath)
        if not result:
            continue
        fm, body = result
        name = fm.get("name", "")
        if not name:
            continue

        if session_heading in body:
            raw_notes = _extract_subsection(body, session_heading)
            if raw_notes and len(raw_notes.strip()) > 10:
                npcs_to_consolidate.append({
                    "name": name,
                    "raw_notes": raw_notes.strip(),
                    "filepath": fpath,
                    "frontmatter": fm,
                    "body": body,
                })

    if not npcs_to_consolidate:
        return 0

    # Build batched prompt
    npc_blocks = []
    for npc in npcs_to_consolidate:
        npc_blocks.append(f"NPC: {npc['name']}\nRaw notes:\n{npc['raw_notes']}")

    prompt = f"""For each NPC below, consolidate their session update notes into 2-3 clean sentences.
Remove duplicates and near-duplicates. Keep only observable facts and meaningful interactions.
Also produce a one-sentence "party_relationship_update" summarizing how this NPC now views the party.

{chr(10).join(npc_blocks)}

Respond with a JSON array (no markdown fencing):
[
  {{
    "name": "NPC Name",
    "consolidated_notes": "Clean 2-3 sentence summary of session interactions.",
    "party_relationship_update": "One sentence on how the NPC views the party now."
  }}
]"""

    await gemini_limiter.acquire()
    response = await client.aio.models.generate_content(
        model="gemini-2.0-flash",
        contents=prompt,
        config=genai.types.GenerateContentConfig(temperature=0.2),
    )

    # Parse response
    response_text = response.text.strip()
    # Strip markdown code fences if present
    if response_text.startswith("```"):
        response_text = re.sub(r"^```(?:json)?\n?", "", response_text)
        response_text = re.sub(r"\n?```$", "", response_text)

    try:
        consolidated = json.loads(response_text)
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse NPC consolidation response: {e}")
        return 0

    # Apply updates
    updated = 0
    consolidated_by_name = {c["name"]: c for c in consolidated}

    for npc in npcs_to_consolidate:
        name = npc["name"]
        if name not in consolidated_by_name:
            continue

        data = consolidated_by_name[name]
        body = npc["body"]

        # Replace session update section content
        new_notes = data.get("consolidated_notes", "")
        if new_notes:
            body = _replace_subsection(body, session_heading, f"- {new_notes}")

        # Update Party Relationship section
        relationship_update = data.get("party_relationship_update", "")
        if relationship_update:
            body = _append_to_section(
                body, "Party Relationship",
                f"\n\n### Session {session_number}\n{relationship_update}"
            )

        # Write back
        vault.write_file(npc["filepath"], npc["frontmatter"], body)
        updated += 1
        logger.info(f"Consolidated notes for NPC: {name}")

    return updated


def _extract_subsection(body: str, heading: str) -> str:
    """Extract content from a ### subsection until the next heading."""
    idx = body.find(heading)
    if idx < 0:
        return ""

    start = body.find("\n", idx)
    if start < 0:
        return ""
    start += 1

    # Find next heading (## or ###)
    next_heading = re.search(r"\n#{2,3} ", body[start:])
    if next_heading:
        return body[start : start + next_heading.start()]
    return body[start:]


def _replace_subsection(body: str, heading: str, new_content: str) -> str:
    """Replace a ### subsection's content."""
    idx = body.find(heading)
    if idx < 0:
        return body

    start = body.find("\n", idx)
    if start < 0:
        return body
    start += 1

    next_heading = re.search(r"\n#{2,3} ", body[start:])
    if next_heading:
        end = start + next_heading.start()
    else:
        end = len(body)

    return body[:start] + new_content + "\n" + body[end:]


def _append_to_section(body: str, section_name: str, text: str) -> str:
    """Append text to the end of a ## section, before the next ## heading."""
    pattern = f"## {re.escape(section_name)}"
    match = re.search(pattern, body)
    if not match:
        return body

    section_start = body.find("\n", match.start()) + 1

    # Find next ## heading
    next_heading = re.search(r"\n## ", body[section_start:])
    if next_heading:
        insert_pos = section_start + next_heading.start()
    else:
        insert_pos = len(body)

    # Avoid duplicate session headers
    check_text = body[section_start:insert_pos]
    session_header_match = re.search(r"### Session \d+\n", text)
    if session_header_match and session_header_match.group() in check_text:
        return body

    return body[:insert_pos] + text + "\n" + body[insert_pos:]
