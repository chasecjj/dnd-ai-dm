"""
SoloMerge — Bridges solo adventures with group campaign sessions.

Handles:
- Solo → Party state merge on /solo_end (consequences, NPC encounters, threads)
- Party → Solo context injection on /solo start (recent group events)
- Merge summary generation for DM review

Pure Python — no Discord imports.
"""

import logging
import os
import tempfile
from typing import Dict, List, Optional

logger = logging.getLogger("SoloMerge")


def generate_merge_summary(session_data: dict) -> dict:
    """Generate a merge summary from a completed solo session.

    Extracts key state changes for campaign integration:
    - Location (already handled by existing character location tracking)
    - Active consequences
    - NPC encounters
    - Quest threads
    - Character knowledge (already dual-written — no action needed)

    Args:
        session_data: Dict containing solo session state (from SoloSession fields).

    Returns:
        Dict with merge_summary sections.
    """
    character = session_data.get("character_name", "Unknown")
    location = session_data.get("current_location", "Unknown")
    turn_count = session_data.get("turn_count", 0)

    summary = {
        "character": character,
        "final_location": location,
        "turns_played": turn_count,
        "consequences": session_data.get("active_consequences", []),
        "encountered_npcs": [],
        "active_threads": [],
        "resolved_threads": [],
    }

    # Extract NPC encounters
    for npc in session_data.get("encountered_npcs", []):
        if isinstance(npc, dict):
            summary["encountered_npcs"].append({
                "name": npc.get("name", ""),
                "disposition": npc.get("disposition", "neutral"),
                "motivation": npc.get("motivation", ""),
            })

    # Extract thread status
    for thread in session_data.get("active_threads", []):
        if isinstance(thread, dict):
            status = thread.get("status", "active")
            entry = {"title": thread.get("title", ""), "priority": thread.get("priority", 5)}
            if status == "resolved":
                summary["resolved_threads"].append(entry)
            elif status in ("active", "dormant"):
                summary["active_threads"].append(entry)

    return summary


def build_solo_recap_for_group(merge_summary: dict) -> str:
    """Build a context injection for group storyteller based on solo results.

    This is injected into the next group session's storyteller context so
    the AI DM knows what happened during the solo adventure.

    Args:
        merge_summary: Output from generate_merge_summary().

    Returns:
        Context string for storyteller injection.
    """
    character = merge_summary["character"]
    location = merge_summary["final_location"]

    parts = [f"[SOLO RECAP: {character} went on a solo adventure."]
    parts.append(f"Now at {location}.")

    consequences = merge_summary.get("consequences", [])
    if consequences:
        parts.append(f"Carrying: {', '.join(consequences[:3])}.")

    npcs = merge_summary.get("encountered_npcs", [])
    if npcs:
        npc_names = [n["name"] for n in npcs[:3] if n.get("name")]
        if npc_names:
            parts.append(f"Met: {', '.join(npc_names)}.")

    threads = merge_summary.get("active_threads", [])
    if threads:
        thread_titles = [t["title"] for t in threads[:2] if t.get("title")]
        if thread_titles:
            parts.append(f"Pursuing: {', '.join(thread_titles)}.")

    parts.append("]")
    return " ".join(parts)


def write_merge_file(
    vault_manager,
    character_name: str,
    session_number: int,
    merge_summary: dict,
) -> bool:
    """Write a merge summary to the solo log folder for DM review.

    Creates a file like: 00 - Session Log/Solo/{CharName}_Solo_S{NNN}_merge.md

    Args:
        vault_manager: VaultManager instance for file writing.
        character_name: The solo character's name.
        session_number: Campaign session number.
        merge_summary: Output from generate_merge_summary().

    Returns:
        True on success, False on failure.
    """
    filename = f"{character_name}_Solo_S{session_number:03d}_merge.md"
    rel_path = os.path.join(vault_manager.SOLO_LOG, filename)
    full_path = vault_manager._resolve(rel_path)

    try:
        os.makedirs(os.path.dirname(full_path), exist_ok=True)

        lines = [
            "---",
            "type: solo_merge_summary",
            f"character: {character_name}",
            f"campaign_session: {session_number}",
            f"turns_played: {merge_summary.get('turns_played', 0)}",
            f"final_location: {merge_summary.get('final_location', 'Unknown')}",
            "---",
            "",
            f"## Solo Merge Summary: {character_name}",
            "",
        ]

        # Consequences
        consequences = merge_summary.get("consequences", [])
        if consequences:
            lines.append("### Active Consequences")
            for c in consequences:
                lines.append(f"- {c}")
            lines.append("")

        # NPC Encounters
        npcs = merge_summary.get("encountered_npcs", [])
        if npcs:
            lines.append("### NPC Encounters")
            for npc in npcs:
                name = npc.get("name", "Unknown")
                disp = npc.get("disposition", "neutral")
                motiv = npc.get("motivation", "")
                line = f"- **{name}** ({disp})"
                if motiv:
                    line += f" — {motiv}"
                lines.append(line)
            lines.append("")

        # Threads
        active_threads = merge_summary.get("active_threads", [])
        resolved_threads = merge_summary.get("resolved_threads", [])
        if active_threads or resolved_threads:
            lines.append("### Quest Threads")
            for t in active_threads:
                lines.append(f"- [ ] {t.get('title', '')} (priority {t.get('priority', 5)}/10)")
            for t in resolved_threads:
                lines.append(f"- [x] {t.get('title', '')} (resolved)")
            lines.append("")

        content = "\n".join(lines)

        # Atomic write: write to temp file, then os.replace
        tmp_path = None
        dir_name = os.path.dirname(full_path)
        with tempfile.NamedTemporaryFile(
            'w', dir=dir_name, suffix='.tmp',
            delete=False, encoding='utf-8',
        ) as tmp:
            tmp.write(content)
            tmp_path = tmp.name
        os.replace(tmp_path, full_path)

        logger.info(f"Merge summary written: {rel_path}")
        return True

    except Exception as e:
        logger.error(f"Error writing merge summary: {e}")
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return False


def build_campaign_context_for_solo(
    vault_manager,
    character_name: str,
    max_logs: int = 3,
) -> str:
    """Build campaign context to inject into a solo session startup.

    Pulls recent group session logs filtered to events involving the solo character.

    Args:
        vault_manager: VaultManager instance.
        character_name: The solo character's name.
        max_logs: Maximum number of recent session logs to check.

    Returns:
        Context string, or empty string if no relevant context found.
    """
    session_log_dir = os.path.join(vault_manager.vault_path, "00 - Session Log")
    if not os.path.isdir(session_log_dir):
        return ""

    # Get recent session log files (not solo logs)
    try:
        files = [
            f for f in os.listdir(session_log_dir)
            if f.endswith(".md") and not f.startswith(".")
            and os.path.isfile(os.path.join(session_log_dir, f))
        ]
        files.sort(reverse=True)  # Most recent first
        files = files[:max_logs]
    except OSError:
        return ""

    relevant_lines = []
    char_lower = character_name.lower()

    for filename in files:
        filepath = os.path.join(session_log_dir, filename)
        try:
            with open(filepath, 'r', encoding='utf-8') as f:
                content = f.read()

            # Extract lines mentioning the character
            for line in content.split('\n'):
                if char_lower in line.lower() and line.strip():
                    relevant_lines.append(line.strip())
        except (OSError, UnicodeDecodeError):
            continue

    if not relevant_lines:
        return ""

    # Truncate to reasonable context size
    context = "\n".join(relevant_lines[:10])
    if len(context) > 1000:
        context = context[:1000] + "..."

    return (
        f"[CAMPAIGN CONTEXT for {character_name} — recent group events:\n"
        f"{context}\n]"
    )
