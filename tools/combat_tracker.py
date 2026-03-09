"""
Combat Tracker — Manages initiative order, round tracking, and monster turns.

Integrates with the scene classifier (combat_started/combat_ended) and the
auto-batch resolve flow. Lightweight in-memory state — resets on bot restart.
"""

import logging
import re
from dataclasses import dataclass, field
from typing import Optional

from tools.dice_roller import parse_and_roll

logger = logging.getLogger("CombatTracker")


@dataclass
class Combatant:
    name: str
    initiative: int
    dex_mod: int = 0
    is_player: bool = True


class CombatTracker:
    """Tracks initiative, rounds, and turn order during combat."""

    def __init__(self):
        self.in_combat: bool = False
        self.combatants: list[Combatant] = []
        self.current_round: int = 0
        self.acted_this_round: set[str] = set()
        self.monsters_desc: str = ""  # narrative description of enemies

    def start_combat(self, party_members: list[dict], monsters_desc: str = "enemies") -> str:
        """Roll initiative for all party members and a monster group.

        Args:
            party_members: List of dicts from vault.get_party_state() with 'frontmatter' and 'body'.
            monsters_desc: Description of the enemy group (from scene classifier or narrative).

        Returns:
            Formatted initiative order string for posting to the channel.
        """
        self.in_combat = True
        self.current_round = 1
        self.acted_this_round = set()
        self.combatants = []
        self.monsters_desc = monsters_desc

        # Roll initiative for each party member using their DEX modifier
        for member in party_members:
            name = member['frontmatter'].get('name', 'Unknown')
            dex_mod = self._extract_dex_mod(member.get('body', ''))
            roll = parse_and_roll(f"1d20+{dex_mod}" if dex_mod >= 0 else f"1d20{dex_mod}")
            self.combatants.append(Combatant(
                name=name,
                initiative=roll["total"],
                dex_mod=dex_mod,
                is_player=True,
            ))

        # Roll initiative for the enemy group (flat 1d20 — no stat block)
        enemy_roll = parse_and_roll("1d20")
        self.combatants.append(Combatant(
            name=monsters_desc,
            initiative=enemy_roll["total"],
            dex_mod=0,
            is_player=False,
        ))

        # Sort by initiative (descending), DEX mod as tiebreaker
        self.combatants.sort(key=lambda c: (c.initiative, c.dex_mod), reverse=True)

        logger.info(f"Combat started! {len(self.combatants)} combatants, round {self.current_round}")

        return self._format_initiative_order()

    def record_player_action(self, character_name: str):
        """Mark a player as having acted this round."""
        if not self.in_combat:
            return
        self.acted_this_round.add(character_name)
        logger.debug(f"Combat: {character_name} acted ({len(self.acted_this_round)}/{self._player_count()} players)")

    def all_players_acted(self) -> bool:
        """Check if all players have acted this round."""
        if not self.in_combat:
            return False
        player_names = {c.name for c in self.combatants if c.is_player}
        return player_names.issubset(self.acted_this_round)

    def monsters_go_first(self) -> bool:
        """Check if any enemy has higher initiative than ALL players.

        Returns True if the top combatant in the initiative order is an enemy.
        """
        if not self.combatants:
            return False
        return not self.combatants[0].is_player

    def advance_round(self) -> str:
        """Move to the next combat round. Returns a round header string."""
        self.current_round += 1
        self.acted_this_round = set()
        header = f"**--- Round {self.current_round} ---**"
        logger.info(f"Combat: advancing to round {self.current_round}")
        return header

    def end_combat(self) -> str:
        """Clear combat state. Returns a summary string."""
        rounds = self.current_round
        self.in_combat = False
        self.combatants = []
        self.current_round = 0
        self.acted_this_round = set()
        self.monsters_desc = ""
        logger.info(f"Combat ended after {rounds} rounds")
        return f"**Combat ended** after {rounds} round{'s' if rounds != 1 else ''}."

    def get_monster_turn_prompt(self) -> str:
        """Build a hidden prompt injection for the Storyteller to narrate the monster turn.

        Appended to player_input, telling the Storyteller to weave enemy actions
        into the narrative. The instruction itself must NOT appear in the output.
        """
        return (
            f"\n\n[DM INSTRUCTION — DO NOT print this text or any heading like 'MONSTER TURN'. "
            f"This is a hidden directive. After resolving the players' actions, seamlessly "
            f"narrate the {self.monsters_desc}'s turn as part of the same scene. "
            f"The enemies attack, cast spells, reposition, or use abilities. "
            f"Be specific about targets and effects. Make combat feel dangerous. "
            f"End by prompting the players for their next actions. "
            f"Combat round: {self.current_round}.]"
        )

    def get_monster_first_prompt(self) -> str:
        """Build a standalone prompt for when monsters act BEFORE players.

        Used when enemies have higher initiative — generates a monster-only turn
        at the start of the round, before players post their actions.
        """
        return (
            f"[DM INSTRUCTION — DO NOT print this text or any heading. "
            f"Combat round {self.current_round}. The {self.monsters_desc} act first this round "
            f"(higher initiative). Narrate what the enemies do — they attack, cast spells, "
            f"reposition, or use abilities. Be specific about which player characters they "
            f"target and what effects their actions have. Describe damage, near-misses, and "
            f"tactical movement. End by describing the situation the players now face and "
            f"prompting them to respond.]"
        )

    def _player_count(self) -> int:
        return sum(1 for c in self.combatants if c.is_player)

    def _format_initiative_order(self) -> str:
        """Format the initiative order for Discord."""
        lines = [f"**Initiative Order — Round {self.current_round}**"]
        for i, c in enumerate(self.combatants, 1):
            marker = "Player" if c.is_player else "Enemy"
            lines.append(f"`{i}.` **{c.name}** -- {c.initiative} [{marker}]")
        return "\n".join(lines)

    @staticmethod
    def _extract_dex_mod(body: str) -> int:
        """Parse the DEX modifier from a character sheet markdown body.

        Looks for a stats table row like: | DEX  | 14    | +2  |
        """
        match = re.search(r'\|\s*DEX\s*\|\s*\d+\s*\|\s*([+-]?\d+)\s*\|', body)
        if match:
            return int(match.group(1))
        return 0
