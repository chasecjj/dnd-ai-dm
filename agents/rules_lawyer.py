"""
RulesLawyerAgent — Strict D&D 5e referee and mechanics validator.

Reads party state from the vault via ContextAssembler for accurate rulings.
Uses the `system_instruction` parameter for stable identity.

Two-phase design:
  1. pre_analyze() — Quick pass: identifies what rolls an action needs (no resolution)
  2. process_request() — Full adjudication, optionally using actual dice results
"""

import json
import logging
from typing import Dict, Any, Optional
from google import genai
from tools.context_assembler import ContextAssembler

logger = logging.getLogger('RulesLawyer')

# Stable identity prompt — goes in system_instruction
RULES_LAWYER_IDENTITY = """You are the Rules Lawyer, a strict but fair D&D 5e referee.

Your Responsibilities:
1. Validate player actions against the 5e rules.
2. Calculate damage, verify ranges, check casting times, spell slots, and class features.
3. Track resource usage (spell slots, Lay on Hands, Hit Dice, etc.).
4. Output a structured JSON object with your ruling.

CRITICAL RULES:
- A Paladin's Lay on Hands is an ACTION (or Bonus Action with certain feats), NOT a free action.
- Spell slots are consumed when a spell is cast. Track remaining slots.
- Attacks of Opportunity only trigger when a creature leaves melee range WITHOUT Disengaging.
- Concentration spells end if a new concentration spell is cast.
- Always check if the character actually HAS the ability/spell they're trying to use.

You MUST output ONLY a valid JSON object with these keys:
{
  "valid": true/false,
  "mechanic_used": "Name of ability/spell/attack",
  "result": "Mechanical outcome description",
  "resource_cost": "What was spent (e.g., '1 spell slot', 'Lay on Hands 5 HP')",
  "state_changes": {
    "hp_current": null,
    "spell_slots_used": null,
    "conditions_add": [],
    "conditions_remove": []
  }
}

Use null for state_changes fields that didn't change. Only include changes that actually occurred.
"""


PRE_ANALYZE_IDENTITY = """You are the Rules Lawyer doing a quick pre-pass on a player action.

Your ONLY job: identify what D&D 5e dice roll(s) this action requires.

Output ONLY a valid JSON object:
{
  "needs_roll": true/false,
  "rolls": [
    {"roll_type": "Attack", "formula": "1d20+5", "dc": null},
    {"roll_type": "Damage", "formula": "1d8+3", "dc": null}
  ],
  "reasoning": "Brief explanation of why these checks are needed"
}

Rules:
- If the action is purely narrative (talking, looking, walking), needs_roll = false and rolls = [].
- For ability checks, use the character's actual modifier from the party state.
- For attacks, include the attack roll AND the damage roll as separate entries. Set dc = null for both (DM adjudicates hit/miss).
- For saves, set the appropriate DC based on the situation.
- Order rolls logically: attack before damage, ability check before follow-up.
- Most actions need 1 roll. Attacks need 2 (attack + damage). Some need 0.
"""


class RulesLawyerAgent:
    """Validates player actions against D&D 5e rules with vault-based state awareness."""

    def __init__(self, client, context_assembler: ContextAssembler, model_id: str = "gemini-2.0-flash"):
        self.client = client
        self.context = context_assembler
        self.model_id = model_id

    async def pre_analyze(self, player_input: str, character_name: Optional[str] = None) -> Dict[str, Any]:
        """Quick analysis: what roll(s) does this action require?

        This is a lightweight pass — no outcome resolution, just identifies needed dice.
        Used by the DM console to auto-prompt players for rolls.

        Returns:
            Dict with: needs_roll, roll_type, formula, dc, reasoning
        """
        logger.info(f"Pre-analyzing: {player_input[:80]}")

        rules_context = self.context.build_rules_lawyer_context()

        prompt = f"""## Current Party State
{rules_context}

## Action to Analyze
{f'[{character_name}]: ' if character_name else ''}{player_input}

What roll does this action need? Output JSON only."""

        if not self.client:
            return {"needs_roll": False, "reasoning": "Model not connected"}

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=PRE_ANALYZE_IDENTITY,
                    temperature=0.1,
                )
            )
            text = response.text.strip()

            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)
            logger.info(f"Pre-analysis result: {result}")
            return result

        except json.JSONDecodeError as e:
            logger.error(f"Pre-analysis JSON parse error: {e}")
            return {"needs_roll": False, "reasoning": f"Parse error: {e}"}
        except Exception as e:
            logger.error(f"Pre-analysis error: {e}", exc_info=True)
            return {"needs_roll": False, "reasoning": f"Error: {e}"}

    async def process_request(self, user_input: str, board_context: str = "", dice_results: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Validate a player action against the rules and current party state.

        Args:
            user_input: The raw player action text.
            board_context: Optional board state from Foundry VTT.
            dice_results: Optional dict of actual dice results from players.
                Format: {character_name: {"type": str, "result": int, "dc": int}}

        Returns:
            Dict with ruling: valid, mechanic_used, result, resource_cost, state_changes
        """
        logger.info(f"Validating action: {user_input}")

        # Build dynamic context — detailed party state for accuracy
        rules_context = self.context.build_rules_lawyer_context()

        # Build dice results section if available
        dice_section = ""
        if dice_results:
            dice_lines = []
            for char, roll_info in dice_results.items():
                rolls = roll_info.get("rolls", [])
                if rolls:
                    for r in rolls:
                        roll_type = r.get("type", "Check")
                        result = r.get("result", "?")
                        dc = r.get("dc")
                        dc_str = f" vs DC {dc}" if dc else ""
                        outcome = ""
                        if dc and isinstance(result, int):
                            outcome = " (SUCCESS)" if result >= dc else " (FAILURE)"
                        dice_lines.append(f"  {char}: {roll_type} = {result}{dc_str}{outcome}")
                else:
                    # Legacy single-roll format fallback
                    roll_type = roll_info.get("type", "Check")
                    result = roll_info.get("result", "?")
                    dc = roll_info.get("dc")
                    dc_str = f" vs DC {dc}" if dc else ""
                    outcome = ""
                    if dc and isinstance(result, int):
                        outcome = " (SUCCESS)" if result >= dc else " (FAILURE)"
                    dice_lines.append(f"  {char}: {roll_type} = {result}{dc_str}{outcome}")
            dice_section = "\n## Actual Dice Results (use these, do NOT invent rolls)\n" + "\n".join(dice_lines)

        prompt = f"""## Current Party State (from vault)
{rules_context}

## Board Context
{board_context if board_context else 'Not available'}
{dice_section}

---

## Player Action to Validate
{user_input}

Provide your ruling as a JSON object. Be precise about resource costs and state changes.{
    ' Use the actual dice results above — do not decide outcomes yourself.' if dice_results else ''
}"""
        
        if not self.client:
            return self._error_result("Model not connected.")
        
        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=RULES_LAWYER_IDENTITY,
                    temperature=0.1,  # Low temperature for precise mechanical rulings
                )
            )
            text = response.text.strip()
            
            # Extract JSON from possible markdown wrapping
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()
            
            result = json.loads(text)
            logger.info(f"Validation Result: {result}")
            return result
            
        except json.JSONDecodeError as e:
            logger.error(f"Rules Lawyer JSON parse error: {e}")
            return self._error_result(f"Could not parse ruling: {e}")
        except Exception as e:
            logger.error(f"Error in RulesLawyer: {e}", exc_info=True)
            return self._error_result(str(e))
    
    @staticmethod
    def _error_result(message: str) -> Dict[str, Any]:
        return {
            "valid": False,
            "mechanic_used": "Error",
            "result": f"Ruling error: {message}",
            "resource_cost": "none",
            "state_changes": {}
        }


if __name__ == "__main__":
    print("Rules Lawyer Agent initialized.")
