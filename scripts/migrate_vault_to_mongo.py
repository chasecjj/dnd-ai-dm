"""
Vault → MongoDB Migration Script

Reads existing Obsidian vault .md files (YAML frontmatter), validates
through Pydantic models, and upserts into MongoDB.

Usage:
    python scripts/migrate_vault_to_mongo.py --dry-run   # Validate only
    python scripts/migrate_vault_to_mongo.py              # Migrate for real

The vault files are NEVER deleted or modified. They remain as the
human-readable narrative backup layer.
"""

import sys
import os
import asyncio
import argparse
import logging

# Ensure project root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from dotenv import load_dotenv
from pydantic import ValidationError

from tools.vault_manager import VaultManager
from tools.state_manager import StateManager
from models.characters import Character, NPCModel
from models.quests import QuestModel
from models.locations import LocationModel
from models.world_state import WorldClock, Consequence
from models.session import SessionLog

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("Migration")


def validate_and_collect(vault: VaultManager, dry_run: bool):
    """Read all vault files, validate through Pydantic, report errors."""
    results = {
        "characters": [],
        "npcs": [],
        "quests": [],
        "locations": [],
        "world_clock": None,
        "consequences": [],
        "sessions": [],
    }
    errors = []

    # --- Characters ---
    for fpath in vault.list_files(vault.PARTY):
        fm, body = vault.read_file(fpath)
        try:
            model = Character.model_validate(fm)
            results["characters"].append(model.model_dump(by_alias=False))
            logger.info(f"  [OK] Character: {fm.get('name', fpath)}")
        except ValidationError as e:
            errors.append(f"Character {fpath}: {e}")
            logger.error(f"  [FAIL] Character {fpath}: {e}")

    # --- NPCs ---
    for fpath in vault.list_files(vault.NPCS):
        fm, body = vault.read_file(fpath)
        try:
            # NPC files use 'class' in frontmatter for role — map it
            if "class" in fm and "role" not in fm:
                fm["role"] = fm.pop("class")
            model = NPCModel.model_validate(fm)
            results["npcs"].append(model.model_dump())
            logger.info(f"  [OK] NPC: {fm.get('name', fpath)}")
        except ValidationError as e:
            errors.append(f"NPC {fpath}: {e}")
            logger.error(f"  [FAIL] NPC {fpath}: {e}")

    # --- Quests (Active + Completed) ---
    for folder in [vault.QUESTS_ACTIVE, vault.QUESTS_COMPLETED]:
        for fpath in vault.list_files(folder):
            fm, body = vault.read_file(fpath)
            try:
                model = QuestModel.model_validate(fm)
                results["quests"].append(model.model_dump())
                logger.info(f"  [OK] Quest: {fm.get('name', fpath)}")
            except ValidationError as e:
                errors.append(f"Quest {fpath}: {e}")
                logger.error(f"  [FAIL] Quest {fpath}: {e}")

    # --- Locations ---
    for fpath in vault.list_files(vault.LOCATIONS):
        fm, body = vault.read_file(fpath)
        try:
            model = LocationModel.model_validate(fm)
            results["locations"].append(model.model_dump())
            logger.info(f"  [OK] Location: {fm.get('name', fpath)}")
        except ValidationError as e:
            errors.append(f"Location {fpath}: {e}")
            logger.error(f"  [FAIL] Location {fpath}: {e}")

    # --- World Clock ---
    clock_fm = vault.read_world_clock()
    if clock_fm:
        try:
            model = WorldClock.model_validate(clock_fm)
            results["world_clock"] = model.model_dump()
            logger.info(f"  [OK] WorldClock")
        except ValidationError as e:
            errors.append(f"WorldClock: {e}")
            logger.error(f"  [FAIL] WorldClock: {e}")

    # --- Consequences ---
    # Parse the consequences.md file for pending entries
    due = vault.get_due_consequences(current_session=9999)  # Get ALL
    for c in due:
        try:
            model = Consequence.model_validate(c)
            results["consequences"].append(model.model_dump())
            logger.info(f"  [OK] Consequence: {c.get('event', '?')[:50]}")
        except ValidationError as e:
            errors.append(f"Consequence: {e}")
            logger.error(f"  [FAIL] Consequence: {e}")

    # --- Session Logs ---
    for fpath in vault.list_files(vault.SESSION_LOG):
        fm, body = vault.read_file(fpath)
        try:
            model = SessionLog.model_validate(fm)
            results["sessions"].append(model.model_dump())
            logger.info(f"  [OK] Session: {fm.get('session_number', fpath)}")
        except ValidationError as e:
            errors.append(f"Session {fpath}: {e}")
            logger.error(f"  [FAIL] Session {fpath}: {e}")

    return results, errors


async def migrate(results: dict, state: StateManager):
    """Write validated data to MongoDB."""
    counts = {}

    for char in results["characters"]:
        await state.upsert_character(char)
    counts["characters"] = len(results["characters"])

    for npc in results["npcs"]:
        await state.upsert_npc(npc)
    counts["npcs"] = len(results["npcs"])

    for quest in results["quests"]:
        await state.upsert_quest(quest)
    counts["quests"] = len(results["quests"])

    for loc in results["locations"]:
        await state.upsert_location(loc)
    counts["locations"] = len(results["locations"])

    if results["world_clock"]:
        await state.update_world_clock(results["world_clock"])
        counts["world_clock"] = 1

    for c in results["consequences"]:
        await state.add_consequence(c)
    counts["consequences"] = len(results["consequences"])

    for s in results["sessions"]:
        await state.upsert_session(s)
    counts["sessions"] = len(results["sessions"])

    return counts


async def main():
    parser = argparse.ArgumentParser(description="Migrate vault data to MongoDB")
    parser.add_argument("--dry-run", action="store_true", help="Validate only, don't write to MongoDB")
    parser.add_argument("--vault-path", default="campaign_vault", help="Path to the Obsidian vault")
    args = parser.parse_args()

    vault = VaultManager(vault_path=args.vault_path)
    logger.info(f"Vault path: {vault.vault_path}")

    logger.info("=" * 60)
    logger.info("Phase 1: Validate all vault data through Pydantic models")
    logger.info("=" * 60)
    results, errors = validate_and_collect(vault, args.dry_run)

    if errors:
        logger.warning(f"\n{'=' * 60}")
        logger.warning(f"VALIDATION ERRORS: {len(errors)}")
        for err in errors:
            logger.warning(f"  - {err}")
        logger.warning(f"{'=' * 60}")
        if args.dry_run:
            logger.info("Fix these errors before running without --dry-run")
            return

    summary = {
        "characters": len(results["characters"]),
        "npcs": len(results["npcs"]),
        "quests": len(results["quests"]),
        "locations": len(results["locations"]),
        "world_clock": 1 if results["world_clock"] else 0,
        "consequences": len(results["consequences"]),
        "sessions": len(results["sessions"]),
    }
    logger.info(f"\nValidation summary: {summary}")

    if args.dry_run:
        logger.info("\n--dry-run complete. No data was written to MongoDB.")
        return

    logger.info(f"\n{'=' * 60}")
    logger.info("Phase 2: Write to MongoDB")
    logger.info(f"{'=' * 60}")

    state = StateManager()
    connected = await state.connect()
    if not connected:
        logger.error("Failed to connect to MongoDB. Aborting migration.")
        return

    try:
        counts = await migrate(results, state)
        logger.info(f"\nMigration complete: {counts}")
    finally:
        await state.close()


if __name__ == "__main__":
    asyncio.run(main())
