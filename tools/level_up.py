"""
Level-Up System — Milestone-based D&D 5e character advancement.

Hardcoded class progression tables ensure mechanical accuracy.
Gemini generates the player-friendly guide explaining new abilities.

Usage:
    from tools.level_up import apply_level_up, build_guide_prompt
    summary = apply_level_up(vault, "Victor Saltzpyre")
    prompt = build_guide_prompt([summary])
"""

import re
import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger('LevelUp')


# ---------------------------------------------------------------------------
# Universal Tables
# ---------------------------------------------------------------------------

PROFICIENCY_BONUS = {
    1: 2, 2: 2, 3: 2, 4: 2,
    5: 3, 6: 3, 7: 3, 8: 3,
    9: 4, 10: 4, 11: 4, 12: 4,
    13: 5, 14: 5, 15: 5, 16: 5,
    17: 6, 18: 6, 19: 6, 20: 6,
}


# ---------------------------------------------------------------------------
# Class Progression Data (Levels 2-10)
#
# Each level entry:
#   features         — new class features gained
#   spell_slots_max  — total spell slots at this level (omit if unchanged)
#   lay_on_hands_pool— total LoH pool (Paladin only)
#   choices          — decisions the player must make
#   notes            — mechanical details for the guide prompt
#   spell_slot_detail— human-readable slot breakdown
# ---------------------------------------------------------------------------

CLASS_PROGRESSION = {
    "Paladin": {
        "hit_die": 10,
        "hp_per_level": 6,
        "spellcasting_ability": "CHA",
        "levels": {
            2: {
                "features": ["Fighting Style", "Divine Smite"],
                "spell_slots_max": 2,
                "lay_on_hands_pool": 10,
                "choices": [
                    "Choose a Fighting Style: Defense (+1 AC in armor), Dueling (+2 damage one-handed melee), Great Weapon Fighting (reroll 1-2 on two-handed damage), Protection (impose disadvantage on attack vs nearby ally with shield)"
                ],
                "notes": "Divine Smite: on a melee hit, spend a spell slot for +2d8 radiant damage (+1d8 per slot level above 1st, +1d8 vs undead/fiends, max 5d8).",
            },
            3: {
                "features": ["Divine Health", "Sacred Oath"],
                "spell_slots_max": 3,
                "lay_on_hands_pool": 15,
                "choices": [
                    "Choose a Sacred Oath: Devotion (Sacred Weapon + Turn the Unholy), Ancients (nature protector, Ensnaring Strike + Speak with Animals), Vengeance (relentless hunter, Bane + Hunter's Mark)"
                ],
                "notes": "Divine Health: immune to disease. Sacred Oath grants oath spells (always prepared, free) and Channel Divinity (1 use per short/long rest).",
            },
            4: {
                "features": ["Ability Score Improvement"],
                "spell_slots_max": 3,
                "lay_on_hands_pool": 20,
                "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."],
            },
            5: {
                "features": ["Extra Attack"],
                "spell_slots_max": 6,
                "lay_on_hands_pool": 25,
                "notes": "Extra Attack: attack twice per Attack action. 2nd-level spell slots unlocked.",
                "spell_slot_detail": "4 first-level, 2 second-level",
            },
            6: {
                "features": ["Aura of Protection"],
                "spell_slots_max": 6,
                "lay_on_hands_pool": 30,
                "notes": "Aura of Protection: you and allies within 10 ft add your CHA modifier to all saving throws.",
            },
            7: {
                "features": ["Sacred Oath Feature"],
                "spell_slots_max": 7,
                "lay_on_hands_pool": 35,
                "spell_slot_detail": "4 first-level, 3 second-level",
            },
            8: {
                "features": ["Ability Score Improvement"],
                "spell_slots_max": 7,
                "lay_on_hands_pool": 40,
                "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."],
            },
            9: {
                "features": [],
                "spell_slots_max": 9,
                "lay_on_hands_pool": 45,
                "notes": "3rd-level spell slots unlocked.",
                "spell_slot_detail": "4 first-level, 3 second-level, 2 third-level",
            },
            10: {
                "features": ["Aura of Courage"],
                "spell_slots_max": 9,
                "lay_on_hands_pool": 50,
                "notes": "Aura of Courage: you and allies within 10 ft can't be frightened while you're conscious.",
            },
        },
    },

    "Rogue": {
        "hit_die": 8,
        "hp_per_level": 5,
        "levels": {
            2: {
                "features": ["Cunning Action"],
                "notes": "Cunning Action: bonus action to Dash, Disengage, or Hide each turn. Sneak Attack: 1d6.",
            },
            3: {
                "features": ["Roguish Archetype"],
                "choices": [
                    "Choose a Roguish Archetype: Thief (Fast Hands, Second-Story Work), Assassin (Assassinate, disguise/poison proficiency), Arcane Trickster (limited spellcasting + Mage Hand tricks)"
                ],
                "notes": "Sneak Attack increases to 2d6.",
            },
            4: {
                "features": ["Ability Score Improvement"],
                "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."],
                "notes": "Sneak Attack: 2d6.",
            },
            5: {
                "features": ["Uncanny Dodge"],
                "notes": "Uncanny Dodge: use reaction to halve damage from an attack you can see. Sneak Attack increases to 3d6.",
            },
            6: {
                "features": ["Expertise (2 more)"],
                "choices": ["Choose 2 skill proficiencies to gain Expertise (double proficiency bonus)."],
                "notes": "Sneak Attack: 3d6.",
            },
            7: {
                "features": ["Evasion"],
                "notes": "Evasion: DEX saves for half damage become no damage on success, half on failure. Sneak Attack increases to 4d6.",
            },
            8: {
                "features": ["Ability Score Improvement"],
                "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."],
                "notes": "Sneak Attack: 4d6.",
            },
            9: {
                "features": ["Roguish Archetype Feature"],
                "notes": "Sneak Attack increases to 5d6.",
            },
            10: {
                "features": ["Ability Score Improvement"],
                "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."],
                "notes": "Sneak Attack: 5d6.",
            },
        },
    },

    "Warlock": {
        "hit_die": 8,
        "hp_per_level": 5,
        "spellcasting_ability": "CHA",
        "pact_magic": True,
        "levels": {
            2: {
                "features": ["Eldritch Invocations (2)"],
                "spell_slots_max": 2,
                "choices": [
                    "Choose 2 Eldritch Invocations: Agonizing Blast (+CHA to Eldritch Blast damage), Repelling Blast (push 10ft on EB hit), Devil's Sight (see in magical darkness 120ft), Mask of Many Faces (Disguise Self at will), and more"
                ],
                "notes": "Pact slots: 2 x 1st-level (refresh on short rest).",
            },
            3: {
                "features": ["Pact Boon"],
                "spell_slots_max": 2,
                "choices": [
                    "Choose a Pact Boon: Chain (improved familiar), Blade (summon magic weapon), Tome (extra cantrips + ritual casting)"
                ],
                "notes": "Pact slots upgrade to 2nd-level. Learn one new spell.",
            },
            4: {
                "features": ["Ability Score Improvement"],
                "spell_slots_max": 2,
                "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."],
            },
            5: {
                "features": ["Eldritch Invocation (3rd)"],
                "spell_slots_max": 2,
                "choices": ["Choose a 3rd Eldritch Invocation."],
                "notes": "Pact slots upgrade to 3rd-level. Eldritch Blast fires 2 beams at this level.",
            },
            6: {
                "features": ["Otherworldly Patron Feature"],
                "spell_slots_max": 2,
            },
            7: {
                "features": ["Eldritch Invocation (4th)"],
                "spell_slots_max": 2,
                "choices": ["Choose a 4th Eldritch Invocation."],
                "notes": "Pact slots upgrade to 4th-level.",
            },
            8: {
                "features": ["Ability Score Improvement"],
                "spell_slots_max": 2,
                "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."],
            },
            9: {
                "features": ["Eldritch Invocation (5th)"],
                "spell_slots_max": 2,
                "choices": ["Choose a 5th Eldritch Invocation."],
                "notes": "Pact slots upgrade to 5th-level.",
            },
            10: {
                "features": ["Otherworldly Patron Feature"],
                "spell_slots_max": 2,
            },
        },
    },

    "Bard": {
        "hit_die": 8,
        "hp_per_level": 5,
        "spellcasting_ability": "CHA",
        "levels": {
            2: {
                "features": ["Jack of All Trades", "Song of Rest (d6)"],
                "spell_slots_max": 3,
                "notes": "Jack of All Trades: +half proficiency bonus to non-proficient ability checks. Song of Rest: allies heal +1d6 on short rest.",
            },
            3: {
                "features": ["Bard College", "Expertise (2)"],
                "spell_slots_max": 6,
                "choices": [
                    "Choose a Bard College: Lore (bonus proficiencies, Cutting Words), Valor (medium armor, shields, martial weapons, Combat Inspiration at 3rd)",
                    "Choose 2 skills for Expertise (double proficiency bonus)."
                ],
                "notes": "2nd-level spell slots unlocked.",
                "spell_slot_detail": "4 first-level, 2 second-level",
            },
            4: {
                "features": ["Ability Score Improvement"],
                "spell_slots_max": 7,
                "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."],
                "spell_slot_detail": "4 first-level, 3 second-level",
            },
            5: {
                "features": ["Bardic Inspiration (d8)", "Font of Inspiration"],
                "spell_slots_max": 9,
                "notes": "Bardic Inspiration die upgrades to d8. Font of Inspiration: BI recharges on short rest. 3rd-level spells unlocked.",
                "spell_slot_detail": "4 first-level, 3 second-level, 2 third-level",
            },
            6: {
                "features": ["Bard College Feature", "Countercharm"],
                "spell_slots_max": 10,
                "notes": "Countercharm: action to give you and nearby allies advantage on saves vs frightened/charmed.",
                "spell_slot_detail": "4 first-level, 3 second-level, 3 third-level",
            },
            7: {
                "features": [],
                "spell_slots_max": 11,
                "notes": "4th-level spell slots unlocked.",
                "spell_slot_detail": "4 first-level, 3 second-level, 3 third-level, 1 fourth-level",
            },
            8: {
                "features": ["Ability Score Improvement"],
                "spell_slots_max": 12,
                "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."],
                "spell_slot_detail": "4 first-level, 3 second-level, 3 third-level, 2 fourth-level",
            },
            9: {
                "features": ["Song of Rest (d8)"],
                "spell_slots_max": 14,
                "notes": "Song of Rest die increases to d8. 5th-level spell slots unlocked.",
                "spell_slot_detail": "4 first-level, 3 second-level, 3 third-level, 3 fourth-level, 1 fifth-level",
            },
            10: {
                "features": ["Bardic Inspiration (d10)", "Expertise (2 more)", "Magical Secrets"],
                "spell_slots_max": 15,
                "choices": [
                    "Choose 2 skills for Expertise.",
                    "Choose 2 spells from ANY class spell list (Magical Secrets)."
                ],
                "notes": "Bardic Inspiration die upgrades to d10. Magical Secrets: learn 2 spells from any class.",
                "spell_slot_detail": "4 first-level, 3 second-level, 3 third-level, 3 fourth-level, 2 fifth-level",
            },
        },
    },

    # -----------------------------------------------------------------------
    # Additional core classes (stubs — expand as needed)
    # -----------------------------------------------------------------------
    "Fighter": {
        "hit_die": 10,
        "hp_per_level": 6,
        "levels": {
            2: {"features": ["Action Surge (1 use)"], "notes": "Action Surge: once per short rest, take an extra action on your turn."},
            3: {"features": ["Martial Archetype"], "choices": ["Choose a Martial Archetype: Champion, Battle Master, Eldritch Knight"]},
            4: {"features": ["Ability Score Improvement"], "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."]},
            5: {"features": ["Extra Attack"], "notes": "Extra Attack: attack twice per Attack action."},
            6: {"features": ["Ability Score Improvement"], "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."]},
            7: {"features": ["Martial Archetype Feature"]},
            8: {"features": ["Ability Score Improvement"], "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."]},
            9: {"features": ["Indomitable (1 use)"], "notes": "Indomitable: reroll a failed saving throw (1/long rest)."},
            10: {"features": ["Martial Archetype Feature"]},
        },
    },
    "Wizard": {
        "hit_die": 6,
        "hp_per_level": 4,
        "spellcasting_ability": "INT",
        "levels": {
            2: {"features": ["Arcane Tradition"], "spell_slots_max": 3, "choices": ["Choose an Arcane Tradition (school of magic)."]},
            3: {"features": [], "spell_slots_max": 6, "spell_slot_detail": "4 first-level, 2 second-level"},
            4: {"features": ["Ability Score Improvement"], "spell_slots_max": 7, "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."]},
            5: {"features": [], "spell_slots_max": 9, "spell_slot_detail": "4 first-level, 3 second-level, 2 third-level"},
            6: {"features": ["Arcane Tradition Feature"], "spell_slots_max": 10},
            7: {"features": [], "spell_slots_max": 11},
            8: {"features": ["Ability Score Improvement"], "spell_slots_max": 12, "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."]},
            9: {"features": [], "spell_slots_max": 14},
            10: {"features": ["Arcane Tradition Feature"], "spell_slots_max": 15},
        },
    },
    "Cleric": {
        "hit_die": 8,
        "hp_per_level": 5,
        "spellcasting_ability": "WIS",
        "levels": {
            2: {"features": ["Channel Divinity (1 use)", "Turn Undead"], "spell_slots_max": 3},
            3: {"features": [], "spell_slots_max": 6, "spell_slot_detail": "4 first-level, 2 second-level"},
            4: {"features": ["Ability Score Improvement"], "spell_slots_max": 7, "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."]},
            5: {"features": ["Destroy Undead (CR 1/2)"], "spell_slots_max": 9},
            6: {"features": ["Channel Divinity (2 uses)", "Divine Domain Feature"], "spell_slots_max": 10},
            7: {"features": [], "spell_slots_max": 11},
            8: {"features": ["Ability Score Improvement", "Destroy Undead (CR 1)", "Divine Domain Feature"], "spell_slots_max": 12, "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."]},
            9: {"features": [], "spell_slots_max": 14},
            10: {"features": ["Divine Intervention"], "spell_slots_max": 15},
        },
    },
    "Ranger": {
        "hit_die": 10,
        "hp_per_level": 6,
        "spellcasting_ability": "WIS",
        "levels": {
            2: {"features": ["Fighting Style", "Spellcasting"], "spell_slots_max": 2, "choices": ["Choose a Fighting Style: Archery (+2 ranged attack), Defense (+1 AC), Dueling (+2 one-handed melee), Two-Weapon Fighting (add ability mod to off-hand damage)"]},
            3: {"features": ["Ranger Archetype", "Primeval Awareness"], "spell_slots_max": 3, "choices": ["Choose a Ranger Archetype: Hunter, Beast Master"]},
            4: {"features": ["Ability Score Improvement"], "spell_slots_max": 3, "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."]},
            5: {"features": ["Extra Attack"], "spell_slots_max": 6, "spell_slot_detail": "4 first-level, 2 second-level"},
            6: {"features": ["Favored Enemy Improvement", "Natural Explorer Improvement"], "spell_slots_max": 6},
            7: {"features": ["Ranger Archetype Feature"], "spell_slots_max": 7},
            8: {"features": ["Ability Score Improvement", "Land's Stride"], "spell_slots_max": 7, "choices": ["ASI: +2 to one ability or +1 to two (max 20). Or take a feat."]},
            9: {"features": [], "spell_slots_max": 9, "spell_slot_detail": "4 first-level, 3 second-level, 2 third-level"},
            10: {"features": ["Natural Explorer Improvement", "Hide in Plain Sight"], "spell_slots_max": 9},
        },
    },
}


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------

def _extract_con_mod(body: str) -> int:
    """Extract CON modifier from the stats table in the character sheet body."""
    match = re.search(r'\|\s*CON\s*\|\s*\d+\s*\|\s*([+-]\d+)\s*\|', body)
    if match:
        return int(match.group(1))
    return 0


def _add_features_to_body(body: str, features: List[str]) -> str:
    """Append new features to the '## Abilities & Features' section."""
    marker = "## Abilities & Features"
    idx = body.find(marker)
    if idx == -1:
        logger.warning("Could not find 'Abilities & Features' section in body")
        return body

    # Find where the feature list ends (next ## section or end of body)
    list_start = idx + len(marker)
    next_section = body.find("\n## ", list_start)
    if next_section == -1:
        next_section = len(body)

    existing_block = body[list_start:next_section]

    new_lines = []
    for feat in features:
        if feat and f"- {feat}" not in existing_block:
            new_lines.append(f"- {feat}")

    if not new_lines:
        return body

    insert_text = "\n".join(new_lines)
    # Insert before the next section, after existing content
    before = body[:next_section].rstrip()
    after = body[next_section:]
    return before + "\n" + insert_text + "\n" + after


def _add_session_note(body: str, note: str) -> str:
    """Append a note to the '## Session Notes' section."""
    marker = "## Session Notes"
    idx = body.find(marker)
    if idx == -1:
        return body

    # Find end of the header line
    newline = body.find("\n", idx)
    if newline == -1:
        return body + "\n" + note

    insert_at = newline + 1
    # Skip the placeholder line if present
    rest = body[insert_at:]
    if rest.startswith("_Running notes"):
        next_nl = rest.find("\n")
        if next_nl != -1:
            insert_at += next_nl + 1
        else:
            # Placeholder is the last line with no trailing newline
            return body + "\n\n" + note + "\n"

    return body[:insert_at] + note + "\n" + body[insert_at:]


# ---------------------------------------------------------------------------
# Core Functions
# ---------------------------------------------------------------------------

def calculate_level_up(char_class: str, current_level: int, con_mod: int) -> Optional[Dict[str, Any]]:
    """Calculate mechanical changes for a level-up.

    Args:
        char_class: Character's class name.
        current_level: Current level (advances to current_level + 1).
        con_mod: Constitution modifier for HP.

    Returns:
        Dict of changes, or None if class/level not in tables.
    """
    new_level = current_level + 1

    if new_level > 20:
        logger.warning(f"Cannot level beyond 20 (current: {current_level})")
        return None

    class_data = CLASS_PROGRESSION.get(char_class)
    if not class_data:
        logger.warning(f"No progression data for class: {char_class}")
        return None

    level_data = class_data.get("levels", {}).get(new_level)
    if not level_data:
        logger.warning(f"No data for {char_class} level {new_level}")
        return None

    hp_gain = max(1, class_data["hp_per_level"] + con_mod)

    changes = {
        "new_level": new_level,
        "hp_gain": hp_gain,
        "proficiency_bonus": PROFICIENCY_BONUS.get(new_level, 2),
        "features": [f for f in level_data.get("features", []) if f],
        "choices": level_data.get("choices", []),
        "notes": level_data.get("notes", ""),
    }

    if "spell_slots_max" in level_data:
        changes["spell_slots_max"] = level_data["spell_slots_max"]
    if "lay_on_hands_pool" in level_data:
        changes["lay_on_hands_pool"] = level_data["lay_on_hands_pool"]
    if "spell_slot_detail" in level_data:
        changes["spell_slot_detail"] = level_data["spell_slot_detail"]

    return changes


def apply_level_up(vault, char_name: str, session_number: int = 0) -> Optional[Dict[str, Any]]:
    """Apply a level-up to a character in the vault.

    Updates frontmatter (level, HP, slots, resources), adds features to body,
    and logs the level-up in Session Notes.

    Args:
        vault: VaultManager instance.
        char_name: Character name to level up.
        session_number: Current session number for the log entry.

    Returns:
        Summary dict for the guide prompt, or None on failure.
    """
    for fpath in vault.list_files(vault.PARTY):
        fm, body = vault.read_file(fpath)
        if fm.get("name", "").lower() != char_name.lower():
            continue

        char_class = fm.get("class", "")
        current_level = fm.get("level", 1)
        con_mod = _extract_con_mod(body)
        old_hp_max = fm.get("hp_max", 0)

        changes = calculate_level_up(char_class, current_level, con_mod)
        if not changes:
            return None

        # --- Update frontmatter ---
        fm["level"] = changes["new_level"]
        fm["hp_max"] = old_hp_max + changes["hp_gain"]
        fm["hp_current"] = fm["hp_max"]  # Full heal on level-up
        fm["spell_slots_used"] = 0  # Fresh slots

        if "spell_slots_max" in changes:
            fm["spell_slots_max"] = changes["spell_slots_max"]
        if "lay_on_hands_pool" in changes:
            fm["lay_on_hands_pool"] = changes["lay_on_hands_pool"]

        # --- Update body: add new features ---
        if changes["features"]:
            body = _add_features_to_body(body, changes["features"])

        # --- Add session note ---
        session_tag = f" (Session {session_number})" if session_number else ""
        note_lines = [f"### Leveled up to Level {changes['new_level']}{session_tag}"]
        if changes["features"]:
            note_lines.append(f"- New: {', '.join(changes['features'])}")
        note_lines.append(f"- HP: {old_hp_max} -> {fm['hp_max']}")
        if changes["choices"]:
            note_lines.append(f"- Pending choices: {len(changes['choices'])}")
        body = _add_session_note(body, "\n".join(note_lines))

        # --- Write back ---
        vault.write_file(fpath, fm, body)
        logger.info(f"Level up: {char_name} -> Level {changes['new_level']} "
                     f"(HP {old_hp_max}->{fm['hp_max']}, CON mod {con_mod:+d})")

        return {
            "name": char_name,
            "class": char_class,
            "new_level": changes["new_level"],
            "hp_gain": changes["hp_gain"],
            "new_hp_max": fm["hp_max"],
            "con_mod": con_mod,
            "features": changes["features"],
            "choices": changes["choices"],
            "notes": changes["notes"],
            "proficiency_bonus": changes["proficiency_bonus"],
            "spell_slots_max": changes.get("spell_slots_max"),
            "spell_slot_detail": changes.get("spell_slot_detail"),
            "lay_on_hands_pool": changes.get("lay_on_hands_pool"),
        }

    logger.warning(f"Character not found for level-up: {char_name}")
    return None


def build_guide_prompt(summaries: List[Dict[str, Any]]) -> str:
    """Build a Gemini prompt to generate player-friendly level-up guides.

    Args:
        summaries: List of dicts from apply_level_up().

    Returns:
        Prompt string for Gemini.
    """
    char_blocks = []
    for s in summaries:
        block = f"**{s['name']}** -- {s['class']} Level {s['new_level']}\n"
        block += f"- HP increased by {s['hp_gain']} (CON mod {s['con_mod']:+d}) -> new max: {s['new_hp_max']}\n"
        block += f"- Proficiency bonus: +{s['proficiency_bonus']}\n"

        if s["features"]:
            block += f"- New features: {', '.join(s['features'])}\n"

        if s.get("spell_slots_max") is not None:
            block += f"- Spell slots: {s['spell_slots_max']} total"
            if s.get("spell_slot_detail"):
                block += f" ({s['spell_slot_detail']})"
            block += "\n"

        if s.get("lay_on_hands_pool"):
            block += f"- Lay on Hands pool: {s['lay_on_hands_pool']} HP\n"

        if s["notes"]:
            block += f"- Details: {s['notes']}\n"

        if s["choices"]:
            block += "- **CHOICES NEEDED:**\n"
            for choice in s["choices"]:
                block += f"  - {choice}\n"

        char_blocks.append(block)

    return (
        "You are a D&D 5e Dungeon Master announcing a milestone level-up to your players in Discord.\n\n"
        "Write an exciting announcement for each character. For each one:\n"
        "1. A brief in-character flavor line celebrating their growth (1 sentence, tie it to their personality or recent events)\n"
        "2. Explain each new feature in plain, practical terms -- what it does and when to use it in combat/exploration\n"
        "3. If there are CHOICES to make, highlight them with a warning emoji so the player knows to decide before next session\n"
        "4. One quick tactical tip for using the new abilities effectively\n\n"
        "Format rules:\n"
        "- Use Discord markdown (**bold**, *italic*, > quotes)\n"
        "- Use the character's name as a header (## Name)\n"
        "- Keep each character section under 900 characters\n"
        "- Separate characters with a line of dashes (---)\n"
        "- Write for players who may be new to D&D -- no jargon without explanation\n"
        "- Be enthusiastic but informative\n\n"
        "Character data:\n\n" + "\n".join(char_blocks)
    )
