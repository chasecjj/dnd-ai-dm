"""
Board Monitor Agent — Live Foundry VTT Game State

Queries the real Foundry world via the REST API relay to answer
spatial, status, and state questions. Feeds live context into
the Rules Lawyer and Storyteller pipeline.
"""

import logging
from typing import Optional
from agents.tools.foundry_tool import FoundryClient

logger = logging.getLogger('BoardMonitor')


class BoardMonitorAgent:
    def __init__(self, client, foundry: Optional[FoundryClient] = None):
        self.ai_client = client
        self.foundry = foundry or FoundryClient()

    async def get_board_context(self, query: str = "") -> str:
        """
        Pull a snapshot of the current game state from Foundry.
        Returns a text block for injection into the agent pipeline.
        """
        if not self.foundry.is_connected:
            return "(Foundry VTT not connected — no live board data)"

        parts = []

        # 1. Active encounters / combat state
        try:
            encounters = await self.foundry.get_encounters()
            if encounters:
                parts.append(f"**Active Combat:** {_format_encounters(encounters)}")
        except Exception as e:
            logger.debug(f"Could not fetch encounters: {e}")

        # 2. Active scene info — name, dimensions, and tokens on the board
        try:
            scenes = await self.foundry.get_world_scenes()
            active = [s for s in scenes if s.get('active')]
            if active:
                scene = active[0]
                scene_uuid = scene.get('uuid')
                scene_name = scene.get('name', 'Unknown')
                parts.append(f"**Active Scene:** {scene_name}")

                if scene_uuid:
                    tokens = await self.foundry.get_scene_tokens(scene_uuid)
                    if tokens:
                        token_lines = []
                        for t in tokens:
                            name = t.get('name', '?')
                            x, y = t.get('x', 0), t.get('y', 0)
                            hidden = " (hidden)" if t.get('hidden') else ""
                            token_lines.append(f"{name} at ({x},{y}){hidden}")
                        parts.append(f"**Tokens on Scene:** {', '.join(token_lines)}")
                    else:
                        parts.append("**Tokens on Scene:** None")
        except Exception as e:
            logger.debug(f"Could not fetch scene info: {e}")

        # 3. If the query mentions a character/NPC, try to look them up
        if query:
            try:
                search_results = await self.foundry.search(query, filter_type="Actor")
                if search_results:
                    actors = _extract_actors(search_results)
                    if actors:
                        for actor in actors[:2]:  # Limit to 2 lookups
                            uuid = actor.get('uuid')
                            if uuid:
                                try:
                                    details = await self.foundry.get_actor_details(uuid)
                                    parts.append(
                                        f"**{actor.get('name', 'Unknown')}:** "
                                        f"{_format_actor_details(details)}"
                                    )
                                except Exception as e:
                                    logger.debug(f"Could not get actor details for {uuid}: {e}")
            except Exception as e:
                logger.debug(f"Search failed for '{query}': {e}")

        # 4. Quick world overview if we have nothing specific
        if not parts:
            try:
                structure = await self.foundry.get_structure(
                    types=['Actor', 'Scene'],
                    include_data=False,
                )
                parts.append(f"**World Overview:** {_format_structure(structure)}")
            except Exception as e:
                logger.debug(f"Could not fetch structure: {e}")

        if not parts:
            return "(Foundry VTT connected but no relevant board data found)"

        return '\n'.join(parts)

    async def process_request(self, user_input: str) -> str:
        """
        Main entry point — called by the bot orchestrator.
        Returns board context as a text string.
        """
        logger.info(f"Board Monitor processing: {user_input[:80]}...")
        return await self.get_board_context(user_input)


# ------------------------------------------------------------------
# Formatters — turn raw API responses into readable text
# ------------------------------------------------------------------

def _format_encounters(data) -> str:
    """Format encounter data into readable text."""
    if isinstance(data, list):
        if not data:
            return "No active encounters"
        lines = []
        for enc in data:
            if isinstance(enc, dict):
                name = enc.get('name', 'Unnamed')
                round_num = enc.get('round', '?')
                turn = enc.get('turn', '?')
                combatants = enc.get('combatants', [])
                lines.append(
                    f"  • {name} — Round {round_num}, Turn {turn} "
                    f"({len(combatants)} combatants)"
                )
            else:
                lines.append(f"  • {enc}")
        return '\n'.join(lines)
    return str(data)[:300]


def _extract_actors(search_data) -> list:
    """Pull actor entries from search results."""
    if isinstance(search_data, list):
        return [r for r in search_data if isinstance(r, dict)]
    if isinstance(search_data, dict):
        for key in ('results', 'data', 'items', 'entities'):
            if key in search_data and isinstance(search_data[key], list):
                return search_data[key]
        return [search_data]
    return []


def _format_actor_details(data) -> str:
    """Format actor details into a concise summary."""
    if not isinstance(data, dict):
        return str(data)[:300]

    parts = []

    attrs = data.get('attributes', data.get('system', {}).get('attributes', {}))
    if isinstance(attrs, dict):
        hp = attrs.get('hp', {})
        if isinstance(hp, dict):
            parts.append(f"HP: {hp.get('value', '?')}/{hp.get('max', '?')}")
        ac = attrs.get('ac', {})
        if isinstance(ac, dict):
            parts.append(f"AC: {ac.get('value', '?')}")

    abilities = data.get('abilities', data.get('system', {}).get('abilities', {}))
    if isinstance(abilities, dict):
        ab_parts = []
        for ab_key in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
            ab = abilities.get(ab_key, {})
            if isinstance(ab, dict):
                ab_parts.append(f"{ab_key.upper()}: {ab.get('value', '?')}")
        if ab_parts:
            parts.append(' | '.join(ab_parts))

    items = data.get('items', [])
    if isinstance(items, list) and items:
        parts.append(f"{len(items)} items in inventory")

    spells = data.get('spells', [])
    if isinstance(spells, list) and spells:
        parts.append(f"{len(spells)} spells known")

    if not parts:
        return str(data)[:300]

    return ' | '.join(parts)


def _format_structure(data) -> str:
    """Summarize world structure."""
    if isinstance(data, dict):
        counts = {}
        _count_types(data, counts)
        if counts:
            return ', '.join(f"{ct} {tp}(s)" for tp, ct in counts.items())
    return str(data)[:300]


def _count_types(node, counts):
    """Recursively count entity types."""
    if isinstance(node, dict):
        t = node.get('type') or node.get('documentName')
        if t:
            counts[t] = counts.get(t, 0) + 1
        for v in node.values():
            _count_types(v, counts)
    elif isinstance(node, list):
        for item in node:
            _count_types(item, counts)
