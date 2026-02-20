"""
Foundry VTT Client — Three Hats REST API Relay (Async)

Connects to a Foundry VTT world through the Three Hats relay server.
All requests go through the relay (not directly to Foundry).

Architecture:
  Your Bot  --(REST/HTTP)-->  Relay Server  --(WebSocket)-->  Foundry VTT + Module

Requires:
  - FOUNDRY_API_KEY: Your relay API key
  - FOUNDRY_RELAY_URL: Relay server URL (default: public relay)
  - FOUNDRY_CLIENT_ID: Your world's client ID (auto-discovered if not set)

All public methods are async. Callers must `await` every call.
"""

import os
import math
import random
import asyncio
import logging
from typing import Optional, Dict, Any, List

import aiohttp

from agents.tools.foundry_errors import (
    FoundryError,
    FoundryConnectionError,
    FoundryTimeoutError,
    FoundryRateLimitError,
    FoundryOfflineError,
    FoundryNotFoundError,
    FoundryAuthError,
)
from tools.rate_limiter import foundry_limiter

logger = logging.getLogger('FoundryClient')


class FoundryClient:
    """Async client for the Foundry VTT REST API relay.

    Usage:
        client = FoundryClient()
        await client.connect()      # creates aiohttp session, discovers clientId
        actors = await client.search_actors("Goblin")
        await client.close()        # cleans up the TCP session
    """

    def __init__(self):
        self.api_key = os.getenv('FOUNDRY_API_KEY')
        self.relay_url = os.getenv(
            'FOUNDRY_RELAY_URL',
            'https://foundryvtt-rest-api-relay.fly.dev'
        ).rstrip('/')
        self.client_id = os.getenv('FOUNDRY_CLIENT_ID')
        self._connected = False
        self._session: Optional[aiohttp.ClientSession] = None

        # Retry settings
        self.max_retries = 3
        self.base_delay = 1.0  # seconds; doubles each retry (1, 2, 4)

        # Lock for fallback token placement (read-modify-write serialization)
        self._token_lock = asyncio.Lock()

        if not self.api_key:
            logger.warning("FOUNDRY_API_KEY not set — Foundry integration disabled.")

    # ------------------------------------------------------------------
    # Internal HTTP layer
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'x-api-key': self.api_key or '',
        }

    async def _raise_for_status(self, resp: aiohttp.ClientResponse) -> None:
        """Map HTTP status codes to specific Foundry error types."""
        if resp.status < 400:
            return
        body = await resp.text()
        if resp.status in (401, 403):
            raise FoundryAuthError(f"Auth failed ({resp.status}): {body}")
        elif resp.status == 404:
            raise FoundryNotFoundError(f"Not found ({resp.status}): {body}")
        elif resp.status == 429:
            raise FoundryRateLimitError(f"Rate limited ({resp.status}): {body}")
        elif resp.status >= 500:
            raise FoundryConnectionError(f"Server error ({resp.status}): {body}")
        else:
            raise FoundryError(f"HTTP {resp.status}: {body}")

    async def _raw_request(
        self,
        method: str,
        path: str,
        body: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: int = 15,
        inject_client_id: bool = True,
    ) -> Any:
        """Execute a single HTTP request (no retry).

        Returns whatever JSON the relay sends — usually a dict, but
        some endpoints (e.g. /clients) return a list.
        """
        session = self._session
        if session is None or session.closed:
            raise FoundryConnectionError("No active aiohttp session — call connect() first.")

        url = f"{self.relay_url}{path}"
        params = dict(params or {})
        if inject_client_id and self.client_id and 'clientId' not in params:
            params['clientId'] = self.client_id

        client_timeout = aiohttp.ClientTimeout(total=timeout)
        headers = self._headers()

        try:
            if method == 'GET':
                async with session.get(url, headers=headers, params=params,
                                       timeout=client_timeout) as resp:
                    await self._raise_for_status(resp)
                    return await resp.json()
            elif method == 'POST':
                async with session.post(url, headers=headers, json=body or {},
                                        params=params, timeout=client_timeout) as resp:
                    await self._raise_for_status(resp)
                    return await resp.json()
            elif method == 'PUT':
                async with session.put(url, headers=headers, json=body or {},
                                       params=params, timeout=client_timeout) as resp:
                    await self._raise_for_status(resp)
                    return await resp.json()
            elif method == 'DELETE':
                async with session.delete(url, headers=headers, params=params,
                                          timeout=client_timeout) as resp:
                    await self._raise_for_status(resp)
                    return await resp.json()
            else:
                raise ValueError(f"Unsupported HTTP method: {method}")

        except aiohttp.ClientError as e:
            raise FoundryConnectionError(f"Network error: {e}") from e
        except asyncio.TimeoutError as e:
            raise FoundryTimeoutError(f"Request timed out after {timeout}s: {path}") from e

    async def _request(
        self,
        method: str,
        path: str,
        body: Optional[Dict] = None,
        params: Optional[Dict] = None,
        timeout: int = 15,
        inject_client_id: bool = True,
    ) -> Dict[str, Any]:
        """HTTP request with rate limiting, auto-reconnect, and retry."""
        await self._ensure_connected()
        await foundry_limiter.acquire()

        last_error: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                return await self._raw_request(
                    method, path, body=body, params=params,
                    timeout=timeout, inject_client_id=inject_client_id,
                )
            except (FoundryConnectionError, FoundryTimeoutError, FoundryRateLimitError) as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    delay = self.base_delay * (2 ** attempt) + random.uniform(0, 0.5)
                    logger.warning(
                        f"Foundry request failed (attempt {attempt + 1}/{self.max_retries}), "
                        f"retrying in {delay:.1f}s: {e}"
                    )
                    await asyncio.sleep(delay)
            # Non-retryable errors (NotFound, Auth) propagate immediately

        raise last_error  # type: ignore[misc]

    async def _ensure_connected(self) -> None:
        """Reconnect transparently if the connection dropped."""
        if self._connected and self._session and not self._session.closed:
            return
        logger.info("Foundry connection lost, attempting reconnect...")
        success = await self.connect()
        if not success:
            raise FoundryOfflineError("Could not reconnect to Foundry relay.")

    # Shorthand wrappers matching the old API
    async def _get(self, path: str, params: Optional[Dict] = None,
                   timeout: int = 15) -> Dict[str, Any]:
        return await self._request('GET', path, params=params, timeout=timeout)

    async def _post(self, path: str, body: Optional[Dict] = None,
                    params: Optional[Dict] = None,
                    timeout: int = 15) -> Dict[str, Any]:
        return await self._request('POST', path, body=body, params=params, timeout=timeout)

    async def _put(self, path: str, body: Optional[Dict] = None,
                   params: Optional[Dict] = None,
                   timeout: int = 15) -> Dict[str, Any]:
        return await self._request('PUT', path, body=body, params=params, timeout=timeout)

    async def _delete(self, path: str, params: Optional[Dict] = None,
                      timeout: int = 15) -> Dict[str, Any]:
        return await self._request('DELETE', path, params=params, timeout=timeout)

    # ------------------------------------------------------------------
    # Connection & Discovery
    # ------------------------------------------------------------------

    async def get_clients(self) -> List[Dict]:
        """
        List all connected Foundry worlds.
        Does NOT require clientId. Bypasses auto-reconnect to avoid loops.
        """
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        await foundry_limiter.acquire()
        return await self._raw_request(
            'GET', '/clients', timeout=10, inject_client_id=False,
        )

    async def connect(self) -> bool:
        """
        Validate the connection and auto-discover clientId if not set.
        Creates the aiohttp session if needed.
        Returns True if a Foundry world is reachable.
        """
        if not self.api_key:
            logger.error("Cannot connect: FOUNDRY_API_KEY not set.")
            return False

        # Create session if needed
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()

        try:
            clients = await self.get_clients()
            if not clients:
                logger.warning("No Foundry worlds connected to the relay.")
                return False

            # Auto-discover clientId if not set
            if not self.client_id:
                if isinstance(clients, list) and len(clients) > 0:
                    self.client_id = clients[0].get('clientId') or clients[0].get('id')
                elif isinstance(clients, dict):
                    for key, val in clients.items():
                        if isinstance(val, list) and len(val) > 0:
                            self.client_id = val[0].get('clientId') or val[0].get('id')
                            break

                if self.client_id:
                    logger.info(f"Auto-discovered Foundry clientId: {self.client_id}")
                else:
                    logger.warning("Could not auto-discover clientId from response.")
                    logger.debug(f"Clients response: {clients}")
                    return False

            self._connected = True
            logger.info(f"Connected to Foundry relay at {self.relay_url} "
                        f"(client: {self.client_id})")
            return True

        except FoundryError as e:
            logger.error(f"Failed to connect to Foundry relay: {e}")
            return False
        except aiohttp.ClientError as e:
            logger.error(f"Failed to connect to Foundry relay: {e}")
            return False

    async def close(self) -> None:
        """Shut down the aiohttp session cleanly."""
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None
        self._connected = False
        logger.info("Foundry client closed.")

    @property
    def is_connected(self) -> bool:
        return self._connected and bool(self.api_key) and bool(self.client_id)

    async def health_check(self) -> Dict[str, Any]:
        """Check relay + Foundry connectivity. Returns a status dict."""
        result: Dict[str, Any] = {
            'relay_reachable': False,
            'foundry_connected': False,
            'client_id': self.client_id,
        }
        try:
            # Ensure session exists for the check
            if self._session is None or self._session.closed:
                self._session = aiohttp.ClientSession()
            clients = await self._raw_request(
                'GET', '/clients', timeout=10, inject_client_id=False,
            )
            result['relay_reachable'] = True
            result['foundry_connected'] = bool(clients)
            result['connected_worlds'] = len(clients) if isinstance(clients, list) else 0
        except FoundryConnectionError:
            pass  # relay_reachable stays False
        except Exception as e:
            result['error'] = str(e)
        return result

    # ------------------------------------------------------------------
    # Entity Operations (CRUD)
    # ------------------------------------------------------------------

    async def get_entity(self, uuid: str) -> Dict[str, Any]:
        """
        Get an entity by UUID.
        Works for any entity type (Actor, Item, Scene, JournalEntry, etc.)
        """
        return await self._get('/get', params={'uuid': uuid})

    async def get_selected(self, get_actor: bool = False) -> Dict[str, Any]:
        """Get the currently selected token (or its actor)."""
        params: Dict[str, Any] = {'selected': 'true'}
        if get_actor:
            params['actor'] = 'true'
        return await self._get('/get', params=params)

    async def create_entity(self, entity_type: str, data: Dict[str, Any],
                            folder: Optional[str] = None) -> Dict[str, Any]:
        """
        Create a new entity.
        entity_type: Actor, Item, Scene, JournalEntry, RollTable, Macro, etc.
        data: The entity data (name, type, img, system data, etc.)
        """
        body: Dict[str, Any] = {
            'entityType': entity_type,
            'data': data,
        }
        if folder:
            body['folder'] = folder
        return await self._post('/create', body=body)

    async def update_entity(self, uuid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing entity by UUID."""
        return await self._put('/update', body={'data': data},
                               params={'uuid': uuid})

    async def delete_entity(self, uuid: str) -> Dict[str, Any]:
        """Delete an entity by UUID."""
        return await self._delete('/delete', params={'uuid': uuid})

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    async def search(self, query: str,
                     filter_type: Optional[str] = None) -> Dict[str, Any]:
        """
        Search for entities in the Foundry world.
        Requires Quick Insert module in Foundry.

        filter_type: Simple filter like "Actor", "Item", "Scene", "JournalEntry"
                     or property-based: "key:value,key2:value2"
        """
        params: Dict[str, str] = {'query': query}
        if filter_type:
            params['filter'] = filter_type
        return await self._get('/search', params=params)

    # ------------------------------------------------------------------
    # World Structure
    # ------------------------------------------------------------------

    async def get_structure(self, types: Optional[List[str]] = None,
                            path: Optional[str] = None,
                            recursive: bool = True,
                            include_data: bool = False) -> Dict[str, Any]:
        """
        Get the folder/entity structure of the world.

        types: Filter by type — Scene, Actor, Item, JournalEntry,
               RollTable, Cards, Macro, Playlist
        path: Folder path to start from (None = root)
        recursive: Walk down folder tree
        include_data: Include full entity data vs just UUIDs/names
        """
        params: Dict[str, Any] = {
            'recursive': str(recursive).lower(),
            'includeEntityData': str(include_data).lower(),
        }
        if types:
            params['types'] = ','.join(types)
        if path:
            params['path'] = path
        return await self._get('/structure', params=params)

    # ------------------------------------------------------------------
    # D&D 5e Specific
    # ------------------------------------------------------------------

    async def get_actor_details(self, actor_uuid: str,
                                details: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get detailed D&D 5e actor info.

        details: List of detail categories to retrieve:
                 "resources", "items", "spells", "features",
                 "attributes", "abilities", "skills", etc.
        """
        if details is None:
            details = ["resources", "attributes", "items", "spells", "features"]

        return await self._get('/dnd5e/get-actor-details', params={
            'actorUuid': actor_uuid,
            'details': ','.join(details),
        })

    async def modify_hp(self, uuid: str, amount: int,
                        increase: bool = True) -> Dict[str, Any]:
        """Increase or decrease an entity's HP."""
        path = '/increase' if increase else '/decrease'
        return await self._post(path, body={
            'attribute': 'system.attributes.hp.value',
            'amount': abs(amount),
        }, params={'uuid': uuid})

    async def kill_entity(self, uuid: str) -> Dict[str, Any]:
        """Mark an entity as dead (HP=0, dead status, combat tracker)."""
        return await self._post('/kill', params={'uuid': uuid})

    async def give_item(self, to_uuid: str, item_name: str,
                        from_uuid: Optional[str] = None,
                        quantity: int = 1) -> Dict[str, Any]:
        """Give an item to an entity."""
        body: Dict[str, Any] = {
            'toUuid': to_uuid,
            'itemName': item_name,
            'quantity': quantity,
        }
        if from_uuid:
            body['fromUuid'] = from_uuid
        return await self._post('/give', body=body)

    async def remove_item(self, actor_uuid: str,
                          item_name: str,
                          quantity: int = 1) -> Dict[str, Any]:
        """Remove an item from an entity."""
        return await self._post('/remove', body={
            'actorUuid': actor_uuid,
            'itemName': item_name,
            'quantity': quantity,
        })

    async def use_ability(self, actor_uuid: str,
                          ability_name: str,
                          target_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Use an ability (generic — spell, feature, or item)."""
        body: Dict[str, Any] = {
            'actorUuid': actor_uuid,
            'abilityName': ability_name,
        }
        if target_uuid:
            body['targetUuid'] = target_uuid
        return await self._post('/dnd5e/use-ability', body=body)

    async def cast_spell(self, actor_uuid: str,
                         spell_name: str,
                         target_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Cast a spell."""
        body: Dict[str, Any] = {
            'actorUuid': actor_uuid,
            'abilityName': spell_name,
        }
        if target_uuid:
            body['targetUuid'] = target_uuid
        return await self._post('/dnd5e/use-spell', body=body)

    async def modify_xp(self, actor_uuid: str, amount: int) -> Dict[str, Any]:
        """Add or remove XP from an actor."""
        return await self._post('/dnd5e/modify-experience', body={
            'actorUuid': actor_uuid,
            'amount': amount,
        })

    # ------------------------------------------------------------------
    # Encounter / Combat
    # ------------------------------------------------------------------

    async def get_encounters(self) -> Dict[str, Any]:
        """Get all active encounters."""
        return await self._get('/encounters')

    async def start_encounter(self, token_uuids: Optional[List[str]] = None,
                              start_with_players: bool = False,
                              roll_npc: bool = True) -> Dict[str, Any]:
        """Start a new combat encounter."""
        body: Dict[str, Any] = {
            'startWithPlayers': start_with_players,
            'rollNPC': roll_npc,
        }
        if token_uuids:
            body['tokens'] = token_uuids
        return await self._post('/start-encounter', body=body)

    async def next_turn(self, encounter_id: Optional[str] = None) -> Dict[str, Any]:
        """Advance to the next turn."""
        body: Dict[str, Any] = {}
        if encounter_id:
            body['encounter'] = encounter_id
        return await self._post('/next-turn', body=body)

    async def next_round(self, encounter_id: Optional[str] = None) -> Dict[str, Any]:
        """Advance to the next round."""
        body: Dict[str, Any] = {}
        if encounter_id:
            body['encounter'] = encounter_id
        return await self._post('/next-round', body=body)

    async def end_encounter(self, encounter_id: Optional[str] = None) -> Dict[str, Any]:
        """End an encounter."""
        body: Dict[str, Any] = {}
        if encounter_id:
            body['encounter'] = encounter_id
        return await self._post('/end-encounter', body=body)

    async def add_to_encounter(self, uuids: Optional[List[str]] = None,
                               roll_initiative: bool = True,
                               encounter_id: Optional[str] = None) -> Dict[str, Any]:
        """Add tokens to the current encounter."""
        body: Dict[str, Any] = {'rollInitiative': roll_initiative}
        if uuids:
            body['uuids'] = uuids
        if encounter_id:
            body['encounter'] = encounter_id
        return await self._post('/add-to-encounter', body=body)

    # ------------------------------------------------------------------
    # Game State Summary
    # ------------------------------------------------------------------

    async def get_game_state_summary(self) -> str:
        """
        Build a text summary of the current game state for use by AI agents.
        Pulls actors, active scene, and encounters.
        """
        if not self.is_connected:
            return "(Foundry VTT not connected)"

        parts = []

        try:
            structure = await self.get_structure(
                types=['Actor', 'Scene'],
                include_data=False,
                recursive=True,
            )
            parts.append(f"**World Structure:** {_summarize_structure(structure)}")
        except Exception as e:
            parts.append(f"(Could not fetch world structure: {e})")

        try:
            encounters = await self.get_encounters()
            if encounters:
                parts.append(f"**Active Encounters:** {encounters}")
            else:
                parts.append("**Active Encounters:** None")
        except Exception as e:
            parts.append(f"(Could not fetch encounters: {e})")

        return '\n'.join(parts)

    # ------------------------------------------------------------------
    # Dice Rolling
    # ------------------------------------------------------------------

    async def roll_dice(self, formula: str,
                        show_in_chat: bool = False) -> Dict[str, Any]:
        """
        Roll dice using Foundry's dice engine.

        formula: Any Foundry dice formula — 1d20+5, 4d6kh3, 8d6, etc.
        show_in_chat: If True, display the roll in Foundry chat.
        Returns dict with 'total', 'formula', 'dice', 'isCritical', 'isFumble'.
        """
        body: Dict[str, Any] = {'formula': formula}
        if show_in_chat:
            body['chatMessage'] = True
        result = await self._post('/roll', body=body)

        roll_data = result.get('data', {}).get('roll', {})
        return {
            'total': roll_data.get('total', 0),
            'formula': roll_data.get('formula', formula),
            'dice': roll_data.get('dice', []),
            'isCritical': roll_data.get('isCritical', False),
            'isFumble': roll_data.get('isFumble', False),
            'timestamp': roll_data.get('timestamp'),
            'raw': roll_data,
        }

    # ------------------------------------------------------------------
    # Search Helpers
    # ------------------------------------------------------------------

    async def search_actors(self, query: str) -> List[Dict[str, Any]]:
        """Search for actors (monsters, NPCs, PCs) by name."""
        result = await self.search(query, filter_type='Actor')
        return result.get('results', [])

    async def search_scenes(self, query: str) -> List[Dict[str, Any]]:
        """Search for scenes (battlemaps) by name."""
        result = await self.search(query, filter_type='Scene')
        return result.get('results', [])

    async def search_items(self, query: str) -> List[Dict[str, Any]]:
        """Search for items (weapons, armor, potions, etc.) by name."""
        result = await self.search(query, filter_type='Item')
        return result.get('results', [])

    # ------------------------------------------------------------------
    # World Actors & Scenes
    # ------------------------------------------------------------------

    async def get_world_actors(self) -> List[Dict[str, Any]]:
        """Get all actors that exist in the world (not just compendiums)."""
        r = await self.get_structure(
            types=['Actor'], recursive=True, include_data=False
        )
        return r.get('data', {}).get('entities', {}).get('actors', [])

    async def get_world_scenes(self) -> List[Dict[str, Any]]:
        """Get all scenes in the world (not compendiums)."""
        r = await self.get_structure(
            types=['Scene'], recursive=True, include_data=False
        )
        return r.get('data', {}).get('entities', {}).get('scenes', [])

    # ------------------------------------------------------------------
    # Stat Block Formatting
    # ------------------------------------------------------------------

    async def get_actor_stat_block(self, uuid: str) -> Dict[str, Any]:
        """
        Fetch an actor by UUID and format as a readable D&D stat block.
        Works for both world actors AND compendium actors.
        """
        raw = await self.get_entity(uuid)
        data = raw.get('data', {})
        system = data.get('system', {})

        # Ability scores
        abilities = {}
        for ab in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
            ab_data = system.get('abilities', {}).get(ab, {})
            val = ab_data.get('value', 10)
            mod = math.floor((val - 10) / 2)
            abilities[ab] = {'value': val, 'mod': mod}

        # HP
        hp_data = system.get('attributes', {}).get('hp', {})
        hp = {
            'current': hp_data.get('value', 0),
            'max': hp_data.get('max', 0),
            'formula': hp_data.get('formula', ''),
        }

        # AC
        ac_data = system.get('attributes', {}).get('ac', {})
        ac = ac_data.get('flat') or ac_data.get('value', 10)

        # Movement
        movement = system.get('attributes', {}).get('movement', {})

        # Senses
        senses = system.get('attributes', {}).get('senses', {})

        # Details (CR, type, etc.)
        details = system.get('details', {})

        # Items (embedded items in the actor — spells, features, equipment)
        items_list = data.get('items', [])
        spells = []
        features = []
        equipment = []
        for item in items_list:
            item_type = item.get('type', '')
            item_name = item.get('name', 'Unknown')
            if item_type == 'spell':
                level = item.get('system', {}).get('level', 0)
                spells.append({'name': item_name, 'level': level})
            elif item_type in ('feat', 'feature'):
                features.append(item_name)
            elif item_type in ('weapon', 'equipment', 'consumable',
                               'tool', 'loot', 'container', 'armor'):
                equipment.append(item_name)

        # Sort spells by level
        spells.sort(key=lambda s: s['level'])

        return {
            'name': data.get('name', 'Unknown'),
            'type': data.get('type', 'npc'),
            'img': data.get('img', ''),
            'uuid': uuid,
            'abilities': abilities,
            'hp': hp,
            'ac': ac,
            'movement': movement,
            'senses': senses,
            'details': details,
            'spells': spells,
            'features': features,
            'equipment': equipment,
            'cr': details.get('cr', details.get('level', '?')),
        }

    # ------------------------------------------------------------------
    # Token Operations — uses embedded document creation (no race condition)
    # ------------------------------------------------------------------

    async def get_scene_tokens(self, scene_uuid: str) -> List[Dict[str, Any]]:
        """Get all tokens placed on a scene."""
        scene = await self.get_entity(scene_uuid)
        return scene.get('data', {}).get('tokens', [])

    async def _build_token_data(
        self,
        actor_uuid: str,
        x: int,
        y: int,
        name: Optional[str] = None,
        hidden: bool = False,
    ) -> Dict[str, Any]:
        """Build token data dict from an actor's prototype token."""
        actor_data = (await self.get_entity(actor_uuid)).get('data', {})
        actor_id = actor_data.get('_id', '')
        token_name = name or actor_data.get('name', 'Unknown')
        token_img = actor_data.get('img', 'icons/svg/mystery-man.svg')
        proto = actor_data.get('prototypeToken', {})

        return {
            'name': token_name,
            'actorId': actor_id,
            'x': x,
            'y': y,
            'width': proto.get('width', 1),
            'height': proto.get('height', 1),
            'texture': proto.get('texture', {'src': token_img}),
            'disposition': proto.get('disposition', -1),
            'hidden': hidden,
            'actorLink': proto.get('actorLink', False),
            'bar1': proto.get('bar1', {'attribute': 'attributes.hp'}),
            'displayBars': 40,   # Show on hover
            'displayName': 30,   # Show on hover
        }

    async def place_token_on_scene(
        self,
        scene_uuid: str,
        actor_uuid: str,
        x: int = 1000,
        y: int = 1000,
        name: Optional[str] = None,
        hidden: bool = False,
    ) -> Dict[str, Any]:
        """
        Place an actor as a token on a scene.

        Uses embedded document creation via parentUuid to avoid the
        read-modify-write race condition. Falls back to array-append
        with a lock if the relay doesn't support parentUuid.
        """
        token_data = await self._build_token_data(actor_uuid, x, y, name, hidden)

        # Primary approach: create as embedded document (no race condition)
        try:
            return await self._post('/create', body={
                'entityType': 'Token',
                'parentUuid': scene_uuid,
                'data': token_data,
            })
        except FoundryError as e:
            logger.warning(
                f"Embedded token creation failed, falling back to array-append: {e}"
            )
            # Fallback: read-modify-write with a lock to prevent self-racing
            async with self._token_lock:
                existing_tokens = await self.get_scene_tokens(scene_uuid)
                existing_tokens.append(token_data)
                return await self.update_entity(scene_uuid, {'tokens': existing_tokens})

    async def place_tokens_on_scene(
        self,
        scene_uuid: str,
        placements: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Place multiple tokens on a scene.

        placements: List of dicts with keys:
            - actor_uuid: str (world actor UUID)
            - x: int (pixel position)
            - y: int (pixel position)
            - name: Optional[str]
            - hidden: bool (default False)
        """
        results = []
        for p in placements:
            result = await self.place_token_on_scene(
                scene_uuid,
                p['actor_uuid'],
                x=p.get('x', 1000),
                y=p.get('y', 1000),
                name=p.get('name'),
                hidden=p.get('hidden', False),
            )
            results.append(result)
        return results

    # ------------------------------------------------------------------
    # Compendium Import
    # ------------------------------------------------------------------

    async def import_compendium_actor(
        self, compendium_uuid: str, name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Import an actor from a compendium into the world.
        Returns the create result with the new world actor UUID.

        compendium_uuid: e.g. "Compendium.dnd5e.monsters.TjWQOgI3A4UAl7lC"
        """
        raw = await self.get_entity(compendium_uuid)
        data = raw.get('data', {})

        create_data = {
            'name': name or data.get('name', 'Unknown'),
            'type': data.get('type', 'npc'),
            'img': data.get('img', ''),
            'system': data.get('system', {}),
        }

        # Copy items (spells, features, equipment)
        items = data.get('items', [])
        if items:
            create_data['items'] = items

        return await self.create_entity('Actor', create_data)

    async def import_compendium_scene(
        self, compendium_uuid: str, name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Import a scene from a compendium into the world.
        Returns the create result with the new world scene UUID.
        """
        raw = await self.get_entity(compendium_uuid)
        data = raw.get('data', {})

        create_data = {
            'name': name or data.get('name', 'Unknown'),
            'active': False,
            'navigation': True,
            'width': data.get('width', 4000),
            'height': data.get('height', 3000),
            'padding': data.get('padding', 0.25),
            'background': data.get('background', {}),
            'grid': data.get('grid', {'size': 100}),
            'tokens': [],  # Start fresh without pre-placed tokens
            'lights': data.get('lights', []),
            'walls': data.get('walls', []),
            'drawings': data.get('drawings', []),
            'templates': data.get('templates', []),
            'sounds': data.get('sounds', []),
            'notes': data.get('notes', []),
        }

        return await self.create_entity('Scene', create_data)

    # ------------------------------------------------------------------
    # Scene Lighting / Day-Night
    # ------------------------------------------------------------------

    async def update_scene_lighting(
        self,
        scene_uuid: str,
        darkness: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Update the darkness level of a scene.
        0.0 = full daylight, 1.0 = pitch black night.
        """
        return await self.update_entity(scene_uuid, {
            'environment': {'darknessLevel': darkness}
        })

    async def activate_scene(self, scene_uuid: str) -> Dict[str, Any]:
        """Activate a scene (makes it the main displayed scene for all players)."""
        return await self.update_entity(scene_uuid, {
            'active': True,
            'navigation': True,
        })

    # ------------------------------------------------------------------
    # Macro Execution
    # ------------------------------------------------------------------

    async def execute_macro(self, macro_name: str,
                            args: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Execute a Foundry macro by name via the /macro endpoint.
        Used for Tagger queries, FXMaster effects, and custom automation.
        """
        body: Dict[str, Any] = {'name': macro_name}
        if args:
            body['args'] = args
        return await self._post('/macro', body=body)

    # ------------------------------------------------------------------
    # Playlist Control
    # ------------------------------------------------------------------

    async def get_playlists(self) -> List[Dict[str, Any]]:
        """Get all playlists in the world with their playing status."""
        r = await self.get_structure(
            types=['Playlist'], recursive=True, include_data=True
        )
        # Collect from both world playlists and compendium packs
        playlists = r.get('data', {}).get('entities', {}).get('playlists', [])
        return playlists

    async def play_playlist(self, playlist_uuid: str) -> Dict[str, Any]:
        """Start playing a playlist."""
        return await self.update_entity(playlist_uuid, {'playing': True})

    async def stop_playlist(self, playlist_uuid: str) -> Dict[str, Any]:
        """Stop a playing playlist."""
        return await self.update_entity(playlist_uuid, {'playing': False})

    async def stop_all_playlists(self) -> List[Dict[str, Any]]:
        """Stop all currently playing playlists."""
        playlists = await self.get_playlists()
        results = []
        for p in playlists:
            if p.get('playing'):
                r = await self.stop_playlist(p.get('uuid', ''))
                results.append(r)
        return results

    # ------------------------------------------------------------------
    # Playlist Info (legacy helper)
    # ------------------------------------------------------------------

    async def get_playlist_info(self) -> List[Dict[str, Any]]:
        """Get available playlist compendium packs."""
        r = await self.get_structure(
            types=['Playlist'], recursive=True, include_data=False
        )
        packs = r.get('data', {}).get('compendiumPacks', {})
        playlists = r.get('data', {}).get('entities', {}).get('playlists', [])

        result = []
        for name, pack in packs.items():
            tracks = pack.get('entities', [])
            result.append({
                'name': name,
                'uuid': pack.get('uuid', ''),
                'track_count': len(tracks),
                'tracks': [t.get('name', '?') for t in tracks],
            })
        for p in playlists:
            result.append({
                'name': p.get('name', 'Unknown'),
                'uuid': p.get('uuid', ''),
                'track_count': 0,
                'tracks': [],
            })
        return result


# ------------------------------------------------------------------
# Stat Block Formatter (for Discord embeds)
# ------------------------------------------------------------------

def format_stat_block_text(stat: Dict[str, Any]) -> str:
    """Format a stat block dict (from get_actor_stat_block) into readable text."""
    ab = stat.get('abilities', {})
    ab_line = ' | '.join(
        f"**{a.upper()}** {ab[a]['value']} ({ab[a]['mod']:+d})"
        for a in ['str', 'dex', 'con', 'int', 'wis', 'cha']
        if a in ab
    )

    hp = stat.get('hp', {})
    hp_str = f"{hp.get('current', '?')}/{hp.get('max', '?')}"
    if hp.get('formula'):
        hp_str += f" ({hp['formula']})"

    mv = stat.get('movement', {})
    speed_parts = []
    if mv.get('walk') and mv['walk'] != '0':
        speed_parts.append(f"{mv['walk']} ft.")
    for mode in ['fly', 'swim', 'climb', 'burrow']:
        if mv.get(mode) and mv[mode] != '0':
            speed_parts.append(f"{mode} {mv[mode]} ft.")
    speed_str = ', '.join(speed_parts) if speed_parts else '30 ft.'

    lines = [
        f"## {stat.get('name', 'Unknown')}",
        f"*{stat.get('type', 'npc').title()}* | CR {stat.get('cr', '?')}",
        "",
        f"**AC** {stat.get('ac', '?')} | **HP** {hp_str} | **Speed** {speed_str}",
        "",
        ab_line,
    ]

    features = stat.get('features', [])
    if features:
        lines.append("")
        lines.append("**Features:** " + ', '.join(features[:10]))

    spells = stat.get('spells', [])
    if spells:
        lines.append("")
        lines.append("**Spells:**")
        by_level: Dict[int, list] = {}
        for s in spells:
            lvl = s.get('level', 0)
            by_level.setdefault(lvl, []).append(s['name'])
        for lvl in sorted(by_level.keys()):
            label = "Cantrips" if lvl == 0 else f"Level {lvl}"
            lines.append(f"  {label}: {', '.join(by_level[lvl])}")

    equipment = stat.get('equipment', [])
    if equipment:
        lines.append("")
        lines.append("**Equipment:** " + ', '.join(equipment[:10]))

    return '\n'.join(lines)

def _summarize_structure(data: Any) -> str:
    """Turn a structure response into a readable summary."""
    if isinstance(data, dict):
        counts: Dict[str, int] = {}
        _count_entities(data, counts)
        if counts:
            return ', '.join(f"{count} {etype}s" for etype, count in counts.items())
        return str(data)[:500]
    return str(data)[:500]


def _count_entities(node: Any, counts: Dict[str, int]) -> None:
    """Recursively count entities in a structure tree."""
    if isinstance(node, dict):
        etype = node.get('type') or node.get('documentName')
        if etype:
            counts[etype] = counts.get(etype, 0) + 1
        for val in node.values():
            _count_entities(val, counts)
    elif isinstance(node, list):
        for item in node:
            _count_entities(item, counts)


# ------------------------------------------------------------------
# Backward-compatible alias
# ------------------------------------------------------------------
FoundryVTTTool = FoundryClient
