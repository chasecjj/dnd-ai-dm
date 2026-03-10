#!/usr/bin/env python3
"""
Vault Normalization Script — One-time migration to canonical formats.

Normalizes all PC and NPC files in the campaign vault to the canonical
format defined in the plan. Dry-run by default; use --apply to write.

Usage:
    python scripts/normalize_vault.py                  # Dry-run (preview)
    python scripts/normalize_vault.py --apply          # Write changes
    python scripts/normalize_vault.py --vault /path    # Custom vault path
"""

import argparse
import json
import os
import re
import sys

# Add project root to path so we can import vault helpers
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tools.vault_manager import parse_frontmatter, build_frontmatter
from tools.templates import (
    NPC_SECTIONS as NPC_CANONICAL_SECTIONS,
    PC_SECTIONS as PC_CANONICAL_SECTIONS,
    NPC_FRONTMATTER_ORDER,
)


# ---------------------------------------------------------------------------
# NPC Normalization
# ---------------------------------------------------------------------------

def normalize_npc(filepath: str, fm: dict, body: str) -> tuple[dict, str, list[str]]:
    """Normalize an NPC file. Returns (new_fm, new_body, changes_list)."""
    changes = []

    # --- Frontmatter normalization ---

    # Ensure type: npc
    if fm.get("type") != "npc":
        fm["type"] = "npc"
        changes.append("Added type: npc")

    # class -> role (rename key)
    if "class" in fm and "role" not in fm:
        fm["role"] = fm.pop("class")
        changes.append(f"Renamed class -> role: {fm['role']}")
    elif "class" in fm and "role" in fm:
        # Both exist — keep role, remove class
        fm.pop("class")
        changes.append("Removed redundant 'class' (role already present)")

    # alive: bool -> status: str
    if "alive" in fm:
        alive_val = fm.pop("alive")
        if "status" not in fm:
            fm["status"] = "alive" if alive_val else "dead"
            changes.append(f"Converted alive: {alive_val} -> status: {fm['status']}")
        else:
            changes.append(f"Removed redundant 'alive' (status already: {fm.get('status')})")

    # Ensure status exists
    if "status" not in fm:
        fm["status"] = "alive"
        changes.append("Added status: alive")

    # Add missing fields
    if "first_seen_session" not in fm:
        fm["first_seen_session"] = None
        changes.append("Added first_seen_session: null")

    if "auto_generated" not in fm:
        fm["auto_generated"] = False
        changes.append("Added auto_generated: false")

    # Normalize disposition
    disposition = fm.get("disposition", "neutral")
    if isinstance(disposition, str):
        normalized = disposition.lower()
        valid = {"friendly", "neutral", "hostile", "unknown"}
        if normalized not in valid:
            fm["disposition"] = "neutral"
            changes.append(f"Fixed disposition: {disposition} -> neutral")
        elif normalized != disposition:
            fm["disposition"] = normalized
            changes.append(f"Lowercased disposition: {disposition} -> {normalized}")

    # Reorder frontmatter to canonical order
    canonical_fm_order = NPC_FRONTMATTER_ORDER
    ordered_fm = {}
    for key in canonical_fm_order:
        if key in fm:
            ordered_fm[key] = fm[key]
    # Preserve any extra keys not in canonical order
    for key in fm:
        if key not in ordered_fm:
            ordered_fm[key] = fm[key]
    fm = ordered_fm

    # --- Body normalization ---

    # Add H1 header if missing
    name = fm.get("name", "Unknown NPC")
    if not body.strip().startswith(f"# {name}"):
        # Check for any H1
        if not re.match(r'^#\s+\S', body.strip()):
            body = f"# {name}\n\n{body}"
            changes.append(f"Added # {name} H1 header")

    # Convert JSON-array Plot Hooks to markdown bullet list
    # Look for a line starting with [ after ## Plot Hooks
    plot_hooks_idx = body.find("## Plot Hooks\n")
    if plot_hooks_idx >= 0:
        after_heading = body[plot_hooks_idx + len("## Plot Hooks\n"):]
        # Find the JSON array — it starts with [ on the next line
        if after_heading.lstrip().startswith("["):
            # Find the matching closing bracket
            bracket_start = plot_hooks_idx + len("## Plot Hooks\n") + (len(after_heading) - len(after_heading.lstrip()))
            bracket_depth = 0
            bracket_end = bracket_start
            for ci, ch in enumerate(body[bracket_start:], bracket_start):
                if ch == "[":
                    bracket_depth += 1
                elif ch == "]":
                    bracket_depth -= 1
                    if bracket_depth == 0:
                        bracket_end = ci + 1
                        break
            json_text = body[bracket_start:bracket_end]
            try:
                hooks_json = json.loads(json_text)
                if isinstance(hooks_json, list) and hooks_json:
                    hooks_md = "\n".join(f"- {hook}" for hook in hooks_json)
                    body = body[:bracket_start] + hooks_md + body[bracket_end:]
                    changes.append("Converted JSON Plot Hooks to markdown bullet list")
            except json.JSONDecodeError:
                # Try with Python literal eval as fallback (handles single quotes)
                import ast
                try:
                    hooks_list = ast.literal_eval(json_text)
                    if isinstance(hooks_list, list) and hooks_list:
                        hooks_md = "\n".join(f"- {hook}" for hook in hooks_list)
                        body = body[:bracket_start] + hooks_md + body[bracket_end:]
                        changes.append("Converted JSON Plot Hooks to markdown bullet list")
                except (ValueError, SyntaxError):
                    pass

    # Merge duplicate session update headings
    body, merge_changes = _merge_duplicate_session_updates(body)
    changes.extend(merge_changes)

    # Reorder body sections to canonical order (preserve all content)
    body, reorder_changes = _reorder_sections(body, name, NPC_CANONICAL_SECTIONS)
    changes.extend(reorder_changes)

    return fm, body, changes


# ---------------------------------------------------------------------------
# PC Normalization
# ---------------------------------------------------------------------------

def normalize_pc(filepath: str, fm: dict, body: str) -> tuple[dict, str, list[str]]:
    """Normalize a PC character sheet. Returns (new_fm, new_body, changes_list)."""
    changes = []

    # Ensure type: party_member
    if fm.get("type") != "party_member":
        fm["type"] = "party_member"
        changes.append("Added type: party_member")

    # Remove redundant char_class if class exists
    if "char_class" in fm and "class" in fm:
        fm.pop("char_class")
        changes.append("Removed redundant char_class (class already present)")

    # --- Body normalization ---

    # Add H1 header if missing
    name = fm.get("name", "Unknown PC")
    if not body.strip().startswith(f"# {name}"):
        if not re.match(r'^#\s+\S', body.strip()):
            body = f"# {name}\n\n{body}"
            changes.append(f"Added # {name} H1 header")

    # Fix bare headers -> ## Headers
    # Match lines that are plain text that should be ## headers
    # (lines that match known section names but don't start with #)
    lines = body.split("\n")
    new_lines = []
    known_sections = set(PC_CANONICAL_SECTIONS)

    for line in lines:
        stripped = line.strip()
        # Check if this line is a bare section name (no # prefix, matches known section)
        if stripped in known_sections and not stripped.startswith("#"):
            new_lines.append(f"## {stripped}")
            changes.append(f"Fixed bare header: '{stripped}' -> '## {stripped}'")
        else:
            new_lines.append(line)

    body = "\n".join(new_lines)

    return fm, body, changes


# ---------------------------------------------------------------------------
# Shared Helpers
# ---------------------------------------------------------------------------

def _merge_duplicate_session_updates(body: str) -> tuple[str, list[str]]:
    """Merge duplicate ### Session N Update headings into single sections."""
    changes = []
    lines = body.split("\n")
    result_lines = []
    session_sections: dict[str, int] = {}  # heading -> index in result_lines
    i = 0

    while i < len(lines):
        line = lines[i]
        # Match ### Session N Update headings
        match = re.match(r'^###\s+Session\s+(\d+)\s+Update\s*$', line.strip())
        if match:
            session_num = match.group(1)
            heading = f"### Session {session_num} Update"

            # Collect content lines after this heading
            content_lines = []
            i += 1
            while i < len(lines):
                next_line = lines[i]
                # Stop at next heading (any level)
                if re.match(r'^#{1,6}\s+', next_line.strip()):
                    break
                if next_line.strip():  # Skip blank lines when collecting
                    content_lines.append(next_line.strip())
                i += 1

            if heading in session_sections:
                # Duplicate! Append content to existing section
                insert_idx = session_sections[heading]
                for content in content_lines:
                    if content.startswith("- "):
                        result_lines.insert(insert_idx + 1, content)
                    else:
                        result_lines.insert(insert_idx + 1, f"- {content}")
                    insert_idx += 1
                    # Update stored index since we inserted lines
                    session_sections[heading] = insert_idx
                changes.append(f"Merged duplicate {heading}")
            else:
                # First occurrence — add heading and format content as bullets
                result_lines.append(heading)
                session_sections[heading] = len(result_lines) - 1
                for content in content_lines:
                    if content.startswith("- "):
                        result_lines.append(content)
                    else:
                        result_lines.append(f"- {content}")
                    session_sections[heading] = len(result_lines) - 1
        else:
            result_lines.append(line)
            i += 1

    if changes:
        return "\n".join(result_lines), changes
    return body, changes


def _reorder_sections(body: str, name: str, canonical_order: list[str]) -> tuple[str, list[str]]:
    """Reorder ## sections to canonical order. Preserves all content including
    non-canonical sections (appended at the end).

    Returns (new_body, changes_list).
    """
    changes = []

    # Split body into H1 header + sections
    # Find the H1 line
    lines = body.split("\n")
    h1_lines = []
    rest_start = 0

    for i, line in enumerate(lines):
        if line.strip().startswith("# ") and not line.strip().startswith("## "):
            h1_lines.append(line)
            rest_start = i + 1
            # Collect any blank lines after H1
            while rest_start < len(lines) and not lines[rest_start].strip():
                rest_start += 1
            break
        elif line.strip().startswith("## "):
            # No H1 found before first ##
            break
        else:
            h1_lines.append(line)
            rest_start = i + 1

    rest = "\n".join(lines[rest_start:])

    # Parse ## sections
    section_pattern = re.compile(r'^(## .+)$', re.MULTILINE)
    sections: dict[str, str] = {}
    section_order: list[str] = []
    parts = section_pattern.split(rest)

    # parts[0] is content before first ##, then alternating header/content
    preamble = parts[0].strip()
    i = 1
    while i < len(parts) - 1:
        header = parts[i].strip()
        content = parts[i + 1]
        section_name = header.replace("## ", "", 1).strip()
        sections[section_name] = content
        section_order.append(section_name)
        i += 2

    # Check if already in canonical order
    canonical_present = [s for s in canonical_order if s in sections]
    actual_present = [s for s in section_order if s in set(canonical_order)]

    if canonical_present != actual_present and len(canonical_present) > 1:
        changes.append("Reordered sections to canonical order")

    # Rebuild: canonical sections first, then any non-canonical, then ### sections
    # (### sections like session updates come after ## sections)
    rebuilt_parts = []
    if "\n".join(h1_lines).strip():
        rebuilt_parts.append("\n".join(h1_lines).strip())

    if preamble:
        rebuilt_parts.append(preamble)

    used = set()
    for section_name in canonical_order:
        if section_name in sections:
            content = sections[section_name]
            rebuilt_parts.append(f"## {section_name}{content}")
            used.add(section_name)

    # Append non-canonical sections in their original order
    for section_name in section_order:
        if section_name not in used:
            content = sections[section_name]
            rebuilt_parts.append(f"## {section_name}{content}")

    new_body = "\n".join(rebuilt_parts) if rebuilt_parts else body

    # Clean up excessive blank lines (3+ -> 2)
    new_body = re.sub(r'\n{3,}', '\n\n', new_body)

    return new_body, changes


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Normalize vault files to canonical format.")
    parser.add_argument("--apply", action="store_true", help="Write changes (default is dry-run)")
    parser.add_argument("--vault", default=None, help="Path to campaign vault (default: campaigns/Default)")
    args = parser.parse_args()

    # Find vault path
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    vault_path = args.vault or os.path.join(project_root, "campaigns", "Default")

    if not os.path.isdir(vault_path):
        print(f"ERROR: Vault not found at {vault_path}")
        sys.exit(1)

    npcs_dir = os.path.join(vault_path, "02 - NPCs")
    party_dir = os.path.join(vault_path, "01 - Party")

    mode = "APPLYING" if args.apply else "DRY-RUN"
    print(f"\n{'='*60}")
    print(f"  Vault Normalization — {mode}")
    print(f"  Vault: {vault_path}")
    print(f"{'='*60}\n")

    # --- NPC normalization ---
    npc_files = []
    if os.path.isdir(npcs_dir):
        npc_files = [f for f in os.listdir(npcs_dir) if f.endswith(".md")]

    npc_fixed = 0
    npc_total = len(npc_files)

    print(f"NPCs ({npc_total} files):")
    print("-" * 40)

    for fname in sorted(npc_files):
        filepath = os.path.join(npcs_dir, fname)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        fm, body = parse_frontmatter(content)

        new_fm, new_body, changes = normalize_npc(filepath, fm, body)

        if changes:
            npc_fixed += 1
            print(f"  {fname}:")
            for change in changes:
                print(f"    - {change}")
            if args.apply:
                new_content = build_frontmatter(new_fm, new_body)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"    [WRITTEN]")
            print()
        else:
            print(f"  {fname}: OK (no changes)")

    # --- PC normalization ---
    pc_files = []
    if os.path.isdir(party_dir):
        pc_files = [f for f in os.listdir(party_dir) if f.endswith(".md")]

    pc_fixed = 0
    pc_total = len(pc_files)

    print(f"\nPCs ({pc_total} files):")
    print("-" * 40)

    for fname in sorted(pc_files):
        filepath = os.path.join(party_dir, fname)
        with open(filepath, "r", encoding="utf-8") as f:
            content = f.read()
        fm, body = parse_frontmatter(content)

        new_fm, new_body, changes = normalize_pc(filepath, fm, body)

        if changes:
            pc_fixed += 1
            print(f"  {fname}:")
            for change in changes:
                print(f"    - {change}")
            if args.apply:
                new_content = build_frontmatter(new_fm, new_body)
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(new_content)
                print(f"    [WRITTEN]")
            print()
        else:
            print(f"  {fname}: OK (no changes)")

    # --- Summary ---
    print(f"\n{'='*60}")
    print(f"  Summary: {pc_total} PCs: {pc_fixed} fixed. {npc_total} NPCs: {npc_fixed} normalized.")
    if not args.apply and (pc_fixed or npc_fixed):
        print(f"  Run with --apply to write changes.")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    main()
