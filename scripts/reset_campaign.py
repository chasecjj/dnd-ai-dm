"""
Campaign Reset Script
Clears player-specific data for a fresh campaign start while preserving
the Waterdeep setting (NPCs, locations, factions, lore).

Usage:
    python scripts/reset_campaign.py          # interactive confirmation
    python scripts/reset_campaign.py -y       # skip confirmation
    python scripts/reset_campaign.py --include-foundry  # also reset Foundry VTT
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import sys
from pathlib import Path


# ---------------------------------------------------------------------------
# Resolve paths relative to this script's location
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(os.path.dirname(os.path.abspath(__file__)))
PROJECT_ROOT = SCRIPT_DIR.parent
VAULT_ROOT = PROJECT_ROOT / "campaign_vault"

# Directories whose .md files are wiped on reset
CLEAR_DIRS: list[tuple[str, str]] = [
    ("01 - Party", "Party member files"),
    ("04 - Quests/Active", "Active quest files"),
    ("00 - Session Log", "Session log files"),
]

# Directories that are explicitly preserved
KEEP_DIRS: list[str] = [
    "02 - NPCs/",
    "03 - Locations/",
    "05 - Factions/",
    "07 - Lore/",
    "_templates/",
    "Assets/",
]

# ---------------------------------------------------------------------------
# Default file contents
# ---------------------------------------------------------------------------
DEFAULT_CLOCK_MD = """\
---
type: world_clock
current_date: "1st of Ches"
time_of_day: evening
season: early_spring
session: 0
tags: [meta, world_state]
---
# World Clock

## Current Time
- **In-Game Date:** 1st of Ches (early spring)
- **Time of Day:** Evening
- **Weather:** Not yet established
- **Moon Phase:** Not yet established

## Timeline
| Session | In-Game Date | Key Event |
|---------|-------------|-----------|

## Notes
- Waterdeep: Dragon Heist takes place over Levels 1-5.
- The calendar uses the Harptos Calendar (Forgotten Realms).
- Ches = 3rd month (March equivalent). Early spring — snow melting, days getting longer.
"""

DEFAULT_CONSEQUENCES_MD = """\
---
type: consequences
tags: [meta, world_state]
---
# Consequence Queue

Consequences are ripple effects from party decisions. The Chronicler agent writes new entries here. The Context Assembler checks for due consequences and includes them in the Storyteller's prompt when trigger conditions are met.

## Pending

## Resolved
_(none yet)_
"""

DEFAULT_MEMORY_CHECKPOINT: list[object] = []


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _delete_md_files(directory: Path, label: str) -> int:
    """Delete all .md files in *directory*. Returns count of files deleted."""
    if not directory.is_dir():
        print(f"  (directory does not exist yet: {directory.name}/)")
        return 0

    md_files = sorted(glob.glob(str(directory / "*.md")))
    if not md_files:
        print(f"  (no .md files in {directory.name}/)")
        return 0

    for filepath in md_files:
        filename = os.path.basename(filepath)
        os.remove(filepath)
        print(f"  Deleted: {filename}")
    return len(md_files)


def _overwrite_file(filepath: Path, content: str, label: str) -> None:
    """Overwrite a file with *content*, creating parent dirs if needed."""
    filepath.parent.mkdir(parents=True, exist_ok=True)
    filepath.write_text(content, encoding="utf-8")
    print(f"  Reset:   {filepath.name}  ({label})")


def _print_summary() -> None:
    """Print a preview of what the reset will do."""
    print()
    print("=" * 56)
    print("  CAMPAIGN RESET PREVIEW")
    print("=" * 56)
    print()
    print("  WILL CLEAR:")
    for subdir, description in CLEAR_DIRS:
        target = VAULT_ROOT / subdir
        if target.is_dir():
            count = len(glob.glob(str(target / "*.md")))
            print(f"    - {subdir}/*.md  ({count} file(s)) -- {description}")
        else:
            print(f"    - {subdir}/*.md  (dir not created yet) -- {description}")

    print("    - 06 - World State/clock.md             -- overwrite with defaults")
    print("    - 06 - World State/consequences.md      -- overwrite with defaults")
    print("    - 06 - World State/memory_checkpoint.json -- overwrite with []")
    print()
    print("  WILL KEEP (not touched):")
    for dirname in KEEP_DIRS:
        print(f"    - {dirname}")
    print()
    print("=" * 56)


# ---------------------------------------------------------------------------
# Core reset logic
# ---------------------------------------------------------------------------

def reset_campaign() -> None:
    """Execute the full campaign vault reset."""
    total_deleted = 0

    # -- Clear .md files from player-specific directories --
    for subdir, description in CLEAR_DIRS:
        target_dir = VAULT_ROOT / subdir
        print(f"\n[{description}]  {subdir}/")
        total_deleted += _delete_md_files(target_dir, description)

    # -- Overwrite world state files --
    print(f"\n[World State]  06 - World State/")
    world_state_dir = VAULT_ROOT / "06 - World State"

    _overwrite_file(
        world_state_dir / "clock.md",
        DEFAULT_CLOCK_MD,
        "world clock reset to Session 0",
    )
    _overwrite_file(
        world_state_dir / "consequences.md",
        DEFAULT_CONSEQUENCES_MD,
        "consequence queue cleared",
    )

    checkpoint_path = world_state_dir / "memory_checkpoint.json"
    checkpoint_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path.write_text(
        json.dumps(DEFAULT_MEMORY_CHECKPOINT, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"  Reset:   memory_checkpoint.json  (memory cleared)")

    # -- Summary --
    print()
    print("-" * 56)
    print(f"  Campaign reset complete.  {total_deleted} file(s) deleted, 3 file(s) reset.")
    print("-" * 56)


# ---------------------------------------------------------------------------
# Foundry integration
# ---------------------------------------------------------------------------

def run_foundry_reset() -> None:
    """Import and run the existing reset_foundry.py via asyncio."""
    import asyncio

    # Ensure project root is on the path so reset_foundry imports work
    if str(PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(PROJECT_ROOT))

    from scripts.reset_foundry import main as foundry_main  # type: ignore[import-untyped]

    print()
    print("=" * 56)
    print("  FOUNDRY VTT RESET")
    print("=" * 56)
    asyncio.run(foundry_main())


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Reset the campaign vault for a fresh start.",
    )
    parser.add_argument(
        "-y", "--yes",
        action="store_true",
        help="Skip the confirmation prompt.",
    )
    parser.add_argument(
        "--include-foundry",
        action="store_true",
        help="Also run reset_foundry.py to clear Foundry VTT tokens/encounters.",
    )
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    print()
    print("  D&D AI Dungeon Master -- Campaign Reset")
    print(f"  Vault: {VAULT_ROOT.resolve()}")

    if not VAULT_ROOT.is_dir():
        print(f"\n  ERROR: Vault directory not found: {VAULT_ROOT}")
        print("  Make sure campaign_vault/ exists (symlink or real directory).")
        sys.exit(1)

    _print_summary()

    # Confirmation gate
    if not args.yes:
        answer = input("  Proceed with reset? [y/N] ").strip().lower()
        if answer not in ("y", "yes"):
            print("  Aborted.")
            sys.exit(0)

    reset_campaign()

    if args.include_foundry:
        run_foundry_reset()

    # Next steps
    print()
    print("=" * 56)
    print("  NEXT STEPS")
    print("=" * 56)
    print("  1. Update PLAYER_MAP in .env with new character mappings")
    print("     Format: discord_user:CharName,discord_user2:CharName2")
    print("  2. Create party member files in campaign_vault/01 - Party/")
    print("     (use _templates/ for the markdown template)")
    print("  3. Run the bot:  python orchestration/main.py")
    print()


if __name__ == "__main__":
    main()
