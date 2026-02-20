"""
Character Sync Engine — bidirectional sync between Foundry VTT and Vault/MongoDB.

Three public functions:
    register_character()      — Import a Foundry Actor into vault + MongoDB
    sync_foundry_to_local()   — Pull HP/conditions from Foundry → vault/DB
    push_changes_to_foundry() — Push HP/conditions from vault → Foundry

Pure Python, no Discord awareness. Returns plain dicts for the caller to format.
"""

import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------

async def register_character(
    name: str,
    foundry_client,
    vault_manager,
    state_manager=None,
    player_discord_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Import a Foundry VTT Actor into the vault and optionally MongoDB.

    Returns:
        {success: bool, message: str, data: dict|None}
    """
    try:
        # 1. Search for the actor in Foundry
        results = await foundry_client.search_actors(name)
        if not results:
            return {"success": False, "message": f"No actor found matching '{name}'.", "data": None}

        # Pick best match (exact name match preferred)
        match = None
        for r in results:
            if r.get("name", "").lower() == name.lower():
                match = r
                break
        if not match:
            match = results[0]  # Closest result

        uuid = match.get("uuid")
        if not uuid:
            return {"success": False, "message": f"Actor '{match.get('name')}' has no UUID.", "data": None}

        # 2. Pull full stat block
        stat_block = await foundry_client.get_actor_stat_block(uuid)

        # 3. Pull raw entity for active effects (conditions)
        raw_entity = await foundry_client.get_entity(uuid)
        conditions = _extract_conditions_from_foundry(raw_entity)

        # 4. Build frontmatter
        frontmatter = build_frontmatter_from_stat_block(
            stat_block, conditions, player_discord_name
        )

        # 5. Build markdown body
        body = build_vault_body_from_stat_block(stat_block)

        # 6. Write to vault
        file_path = f"01 - Party/{stat_block['name']}.md"
        vault_manager.write_file(file_path, frontmatter, body)

        # 7. Write to MongoDB if connected
        if state_manager:
            try:
                await state_manager.upsert_character(frontmatter)
            except Exception as e:
                logger.warning(f"MongoDB upsert skipped for {name}: {e}")

        return {
            "success": True,
            "message": f"Registered {stat_block['name']} (UUID: {uuid[:20]}...).",
            "data": {
                "name": stat_block["name"],
                "class": _extract_class_info(stat_block),
                "hp_current": stat_block["hp"]["current"],
                "hp_max": stat_block["hp"]["max"],
                "ac": stat_block["ac"],
                "foundry_uuid": uuid,
            },
        }

    except Exception as e:
        logger.error(f"register_character failed for '{name}': {e}", exc_info=True)
        return {"success": False, "message": f"Registration error: {e}", "data": None}


async def sync_foundry_to_local(
    foundry_client,
    vault_manager,
    state_manager=None,
) -> List[Dict[str, Any]]:
    """Pull HP and conditions from Foundry for all linked party members.

    Returns:
        List of {name, field, old, new} change dicts.
    """
    changes: List[Dict[str, Any]] = []

    try:
        party = vault_manager.get_party_state()
    except Exception as e:
        logger.error(f"sync_foundry_to_local: failed to read party state: {e}")
        return changes

    for member in party:
        fm = member.get("frontmatter", {})
        char_name = fm.get("name", "Unknown")
        uuid = fm.get("foundry_uuid")
        if not uuid:
            continue  # Not linked to Foundry

        try:
            raw = await foundry_client.get_entity(uuid)
            data = raw.get("data", {})
            system = data.get("system", {})

            # --- HP ---
            foundry_hp = system.get("attributes", {}).get("hp", {}).get("value")
            vault_hp = fm.get("hp_current")
            if foundry_hp is not None and vault_hp is not None and int(foundry_hp) != int(vault_hp):
                changes.append({
                    "name": char_name,
                    "field": "hp_current",
                    "old": vault_hp,
                    "new": int(foundry_hp),
                })

            # --- Conditions (from active effects) ---
            foundry_conditions = _extract_conditions_from_foundry(raw)
            vault_conditions = sorted(fm.get("conditions", []))
            if foundry_conditions != vault_conditions:
                changes.append({
                    "name": char_name,
                    "field": "conditions",
                    "old": vault_conditions,
                    "new": foundry_conditions,
                })

        except Exception as e:
            logger.error(f"sync_foundry_to_local: error syncing {char_name}: {e}")
            continue

    # Apply all changes to vault + DB
    for change in changes:
        try:
            vault_manager.update_party_member(
                change["name"], {change["field"]: change["new"]}
            )
            if state_manager:
                await state_manager.patch_character(
                    change["name"], {change["field"]: change["new"]}
                )
        except Exception as e:
            logger.error(f"sync_foundry_to_local: failed to write {change}: {e}")

    return changes


async def push_changes_to_foundry(
    character_updates: List[Dict[str, Any]],
    vault_manager,
    foundry_client,
) -> List[Dict[str, Any]]:
    """Push local HP changes to Foundry for characters with a foundry_uuid.

    Args:
        character_updates: List of dicts, each with at least 'name' and
            optionally 'hp_current' and/or 'conditions'.
        vault_manager: VaultManager instance (to look up foundry_uuid).
        foundry_client: FoundryClient instance.

    Returns:
        List of {name, field, value, pushed} or {name, error} result dicts.
    """
    results: List[Dict[str, Any]] = []

    # Build a lookup of name → foundry_uuid from vault
    uuid_map: Dict[str, str] = {}
    try:
        party = vault_manager.get_party_state()
        for member in party:
            fm = member.get("frontmatter", {})
            name = fm.get("name", "")
            fuuid = fm.get("foundry_uuid")
            if name and fuuid:
                uuid_map[name.lower()] = fuuid
    except Exception as e:
        logger.error(f"push_changes_to_foundry: failed to read party: {e}")
        return results

    for update in character_updates:
        char_name = update.get("name", "")
        uuid = uuid_map.get(char_name.lower())
        if not uuid:
            continue  # Not linked to Foundry — skip silently

        # --- Push HP ---
        new_hp = update.get("hp_current")
        if new_hp is not None:
            try:
                # Get current Foundry HP to calculate delta
                raw = await foundry_client.get_entity(uuid)
                foundry_hp = (
                    raw.get("data", {})
                    .get("system", {})
                    .get("attributes", {})
                    .get("hp", {})
                    .get("value", 0)
                )
                delta = int(new_hp) - int(foundry_hp)
                if delta != 0:
                    await foundry_client.modify_hp(
                        uuid, abs(delta), increase=(delta > 0)
                    )
                    results.append({
                        "name": char_name,
                        "field": "hp_current",
                        "value": new_hp,
                        "pushed": True,
                    })
            except Exception as e:
                logger.error(f"push HP for {char_name}: {e}")
                results.append({"name": char_name, "error": f"HP push failed: {e}"})

        # --- Conditions: log-only for v1 (Active Effects are fragile) ---
        new_conditions = update.get("conditions")
        if new_conditions is not None:
            results.append({
                "name": char_name,
                "field": "conditions",
                "value": new_conditions,
                "pushed": False,  # Log only — no Foundry write
            })

    return results


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------

def build_frontmatter_from_stat_block(
    stat_block: Dict[str, Any],
    conditions: List[str],
    player_discord_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Map a Foundry stat block to vault YAML frontmatter."""
    hp = stat_block.get("hp", {})
    details = stat_block.get("details", {})

    fm: Dict[str, Any] = {
        "type": "party_member",
        "name": stat_block.get("name", "Unknown"),
        "race": details.get("race", details.get("type", {}).get("value", "Unknown")) if isinstance(details.get("race", details.get("type", "")), str) else "Unknown",
        "class": _extract_class_info(stat_block),
        "level": _extract_level(stat_block),
        "hp_current": hp.get("current", 0),
        "hp_max": hp.get("max", 0),
        "ac": stat_block.get("ac", 10),
        "conditions": conditions,
        "spell_slots_used": 0,
        "spell_slots_max": _count_spell_slots(stat_block),
        "foundry_uuid": stat_block.get("uuid", ""),
        "tags": ["party"],
    }

    if player_discord_name:
        fm["player"] = player_discord_name

    return fm


def build_vault_body_from_stat_block(stat_block: Dict[str, Any]) -> str:
    """Generate the markdown body for a party member vault file."""
    name = stat_block.get("name", "Unknown")
    abilities = stat_block.get("abilities", {})
    spells = stat_block.get("spells", [])
    features = stat_block.get("features", [])
    equipment = stat_block.get("equipment", [])

    lines = [f"# {name}", ""]

    # Stats table
    lines.append("## Stats")
    lines.append("| Stat | Score | Mod |")
    lines.append("|------|-------|-----|")
    for ab in ["str", "dex", "con", "int", "wis", "cha"]:
        ab_data = abilities.get(ab, {})
        val = ab_data.get("value", 10)
        mod = ab_data.get("mod", 0)
        sign = "+" if mod >= 0 else ""
        lines.append(f"| {ab.upper()}  | {val}    | {sign}{mod}  |")
    lines.append("")

    # Features
    if features:
        lines.append("## Abilities & Features")
        for feat in features:
            lines.append(f"- {feat}")
        lines.append("")

    # Spells
    if spells:
        lines.append("## Prepared Spells")
        for spell in spells:
            level = spell.get("level", 0)
            level_str = "Cantrip" if level == 0 else f"{_ordinal(level)} level"
            lines.append(f"- **{spell['name']}** ({level_str})")
        lines.append("")

    # Equipment
    if equipment:
        lines.append("## Inventory")
        for item in equipment:
            lines.append(f"- {item}")
        lines.append("")

    # Placeholder sections
    lines.append("## Personality")
    lines.append("- _To be filled in during play._")
    lines.append("")
    lines.append("## Bonds & Hooks")
    lines.append("- _To be filled in during play._")
    lines.append("")

    return "\n".join(lines)


def _extract_conditions_from_foundry(raw_entity: Dict[str, Any]) -> List[str]:
    """Extract active condition names from a raw Foundry entity."""
    data = raw_entity.get("data", {})
    effects = data.get("effects", [])
    conditions = []
    for effect in effects:
        # Foundry stores conditions as ActiveEffects with a label
        label = effect.get("name") or effect.get("label", "")
        if label and not effect.get("disabled", False):
            conditions.append(label)
    return sorted(conditions)


def _extract_class_info(stat_block: Dict[str, Any]) -> str:
    """Extract class name from stat block details or items."""
    details = stat_block.get("details", {})

    # Player characters: details may have 'class' directly
    if isinstance(details.get("class"), str) and details["class"]:
        return details["class"]

    # DnD5e system stores class as an embedded item of type 'class'
    raw_items = stat_block.get("_raw_items", [])
    # Not available from stat_block — fall back to CR-based type
    cr = stat_block.get("cr", "?")
    actor_type = stat_block.get("type", "npc")
    if actor_type == "character":
        return "Adventurer"  # Generic fallback for PCs
    return f"CR {cr}" if cr != "?" else "Unknown"


def _extract_level(stat_block: Dict[str, Any]) -> int:
    """Extract character level from stat block."""
    details = stat_block.get("details", {})
    # DnD5e: details.level for PCs
    level = details.get("level")
    if isinstance(level, (int, float)) and level >= 1:
        return int(level)
    # Fallback: CR-based
    cr = stat_block.get("cr", 0)
    if isinstance(cr, (int, float)):
        return max(1, int(cr))
    return 1


def _count_spell_slots(stat_block: Dict[str, Any]) -> int:
    """Estimate total spell slots from spells list."""
    spells = stat_block.get("spells", [])
    # Count non-cantrip spells as a rough estimate
    return sum(1 for s in spells if s.get("level", 0) > 0)


def _ordinal(n: int) -> str:
    """Convert integer to ordinal string (1st, 2nd, 3rd, etc.)."""
    if 11 <= (n % 100) <= 13:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"
