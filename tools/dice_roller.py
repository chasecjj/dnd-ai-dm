"""
Dice Roller — Pure Python dice parser and roller.

Handles standard D&D formulas: XdY, XdY+Z, XdY-Z, plain integers.
Returns a schema compatible with foundry_client.roll_dice() so either
source can be used interchangeably.

Used as a fallback when Foundry VTT is not connected.
"""

import random
import re
import logging
from typing import Dict, Any, List

logger = logging.getLogger("DiceRoller")

# Pattern: optional count, 'd', faces, optional modifier
_DICE_RE = re.compile(
    r"^"
    r"(?P<count>\d+)?"          # optional count (default 1)
    r"d"
    r"(?P<faces>\d+)"           # faces (required)
    r"(?P<mod_sign>[+-])?"      # optional modifier sign
    r"(?P<mod_val>\d+)?"        # optional modifier value
    r"$",
    re.IGNORECASE,
)


def parse_and_roll(formula: str) -> Dict[str, Any]:
    """Parse a dice formula and roll it.

    Supports:
        '1d20+5'  → roll 1d20, add 5
        '2d6+3'   → roll 2d6, add 3
        '1d20-2'  → roll 1d20, subtract 2
        '4d6'     → roll 4d6
        'd20'     → roll 1d20
        '5'       → flat modifier (total=5)

    Returns schema matching foundry_client.roll_dice():
        {
            "total": int,
            "formula": str,
            "dice": [{"faces": int, "results": [{"result": int, "active": True}]}],
            "isCritical": bool,
            "isFumble": bool,
        }
    """
    formula = formula.strip()

    # Handle plain integer (flat modifier, no dice)
    try:
        flat = int(formula)
        return {
            "total": flat,
            "formula": formula,
            "dice": [],
            "isCritical": False,
            "isFumble": False,
        }
    except ValueError:
        pass

    match = _DICE_RE.match(formula)
    if not match:
        logger.warning(f"Could not parse dice formula: {formula}, returning 10")
        return {
            "total": 10,
            "formula": formula,
            "dice": [],
            "isCritical": False,
            "isFumble": False,
        }

    count = int(match.group("count") or "1")
    faces = int(match.group("faces"))
    mod_sign = match.group("mod_sign") or "+"
    mod_val = int(match.group("mod_val") or "0")
    modifier = mod_val if mod_sign == "+" else -mod_val

    # Roll the dice
    rolls = [random.randint(1, faces) for _ in range(count)]
    raw_total = sum(rolls)
    total = raw_total + modifier

    # Critical/fumble detection (only for single d20 rolls)
    is_critical = count == 1 and faces == 20 and rolls[0] == 20
    is_fumble = count == 1 and faces == 20 and rolls[0] == 1

    return {
        "total": total,
        "formula": formula,
        "dice": [
            {
                "faces": faces,
                "results": [{"result": r, "active": True} for r in rolls],
            }
        ],
        "isCritical": is_critical,
        "isFumble": is_fumble,
    }


def format_roll_detail(formula: str, result: Dict[str, Any]) -> str:
    """Format a roll result into a human-readable detail string.

    Example: '1d20+5: [14]+5 = 19' or '2d6+3: [4, 2]+3 = 9'
    """
    dice = result.get("dice", [])
    total = result["total"]

    if not dice:
        return f"{formula} = {total}"

    die_group = dice[0]
    rolls = [r["result"] for r in die_group.get("results", [])]
    rolls_str = ", ".join(str(r) for r in rolls)

    # Extract modifier from formula
    mod_match = re.search(r"([+-]\d+)$", formula)
    mod_str = mod_match.group(1) if mod_match else ""

    return f"{formula}: [{rolls_str}]{mod_str} = {total}"
