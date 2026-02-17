"""
Foundry VTT Client — Three Hats REST API Relay

Connects to a Foundry VTT world through the Three Hats relay server.
All requests go through the relay (not directly to Foundry).

Architecture:
  Your Bot  --(REST)-->  Relay Server  --(WebSocket)-->  Foundry VTT + Module

Requires:
  - FOUNDRY_API_KEY: Your relay API key
  - FOUNDRY_RELAY_URL: Relay server URL (default: public relay)
  - FOUNDRY_CLIENT_ID: Your world's client ID (auto-discovered if not set)
"""

import os
import math
import logging
import requests
from typing import Optional, Dict, Any, List

logger = logging.getLogger('FoundryClient')


class FoundryClient:
    """Client for the Foundry VTT REST API relay."""

    def __init__(self):
        self.api_key = os.getenv('FOUNDRY_API_KEY')
        self.relay_url = os.getenv(
            'FOUNDRY_RELAY_URL',
            'https://foundryvtt-rest-api-relay.fly.dev'
        ).rstrip('/')
        self.client_id = os.getenv('FOUNDRY_CLIENT_ID')
        self._connected = False

        if not self.api_key:
            logger.warning("FOUNDRY_API_KEY not set — Foundry integration disabled.")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _headers(self) -> Dict[str, str]:
        return {
            'Content-Type': 'application/json',
            'x-api-key': self.api_key or '',
        }

    def _get(self, path: str, params: Optional[Dict] = None,
             timeout: int = 15) -> Dict[str, Any]:
        """
        Send a GET request to the relay.
        Automatically injects clientId into query params.
        """
        url = f"{self.relay_url}{path}"
        params = dict(params or {})
        if self.client_id and 'clientId' not in params:
            params['clientId'] = self.client_id

        resp = requests.get(url, headers=self._headers(),
                            params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def _post(self, path: str, body: Optional[Dict] = None,
              params: Optional[Dict] = None,
              timeout: int = 15) -> Dict[str, Any]:
        """
        Send a POST request to the relay.
        Automatically injects clientId into query params.
        """
        url = f"{self.relay_url}{path}"
        params = dict(params or {})
        if self.client_id and 'clientId' not in params:
            params['clientId'] = self.client_id

        resp = requests.post(url, headers=self._headers(),
                             json=body or {}, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def _put(self, path: str, body: Optional[Dict] = None,
             params: Optional[Dict] = None,
             timeout: int = 15) -> Dict[str, Any]:
        """Send a PUT request to the relay."""
        url = f"{self.relay_url}{path}"
        params = dict(params or {})
        if self.client_id and 'clientId' not in params:
            params['clientId'] = self.client_id

        resp = requests.put(url, headers=self._headers(),
                            json=body or {}, params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    def _delete(self, path: str, params: Optional[Dict] = None,
                timeout: int = 15) -> Dict[str, Any]:
        """Send a DELETE request to the relay."""
        url = f"{self.relay_url}{path}"
        params = dict(params or {})
        if self.client_id and 'clientId' not in params:
            params['clientId'] = self.client_id

        resp = requests.delete(url, headers=self._headers(),
                               params=params, timeout=timeout)
        resp.raise_for_status()
        return resp.json()

    # ------------------------------------------------------------------
    # Connection & Discovery
    # ------------------------------------------------------------------

    def get_clients(self) -> List[Dict]:
        """
        List all connected Foundry worlds.
        Does NOT require clientId.
        """
        url = f"{self.relay_url}/clients"
        resp = requests.get(url, headers=self._headers(), timeout=10)
        resp.raise_for_status()
        return resp.json()

    def connect(self) -> bool:
        """
        Validate the connection and auto-discover clientId if not set.
        Returns True if a Foundry world is reachable.
        """
        if not self.api_key:
            logger.error("Cannot connect: FOUNDRY_API_KEY not set.")
            return False

        try:
            clients = self.get_clients()
            if not clients:
                logger.warning("No Foundry worlds connected to the relay.")
                return False

            # Auto-discover clientId if not set
            if not self.client_id:
                # Use the first connected client
                if isinstance(clients, list) and len(clients) > 0:
                    self.client_id = clients[0].get('clientId') or clients[0].get('id')
                elif isinstance(clients, dict):
                    # Some responses may be a dict with client list
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

        except requests.RequestException as e:
            logger.error(f"Failed to connect to Foundry relay: {e}")
            return False

    @property
    def is_connected(self) -> bool:
        return self._connected and bool(self.api_key) and bool(self.client_id)

    # ------------------------------------------------------------------
    # Entity Operations (CRUD)
    # ------------------------------------------------------------------

    def get_entity(self, uuid: str) -> Dict[str, Any]:
        """
        Get an entity by UUID.
        Works for any entity type (Actor, Item, Scene, JournalEntry, etc.)
        """
        return self._get('/get', params={'uuid': uuid})

    def get_selected(self, get_actor: bool = False) -> Dict[str, Any]:
        """Get the currently selected token (or its actor)."""
        params: Dict[str, Any] = {'selected': 'true'}
        if get_actor:
            params['actor'] = 'true'
        return self._get('/get', params=params)

    def create_entity(self, entity_type: str, data: Dict[str, Any],
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
        return self._post('/create', body=body)

    def update_entity(self, uuid: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Update an existing entity by UUID."""
        return self._put('/update', body={'data': data},
                         params={'uuid': uuid})

    def delete_entity(self, uuid: str) -> Dict[str, Any]:
        """Delete an entity by UUID."""
        return self._delete('/delete', params={'uuid': uuid})

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str,
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
        return self._get('/search', params=params)

    # ------------------------------------------------------------------
    # World Structure
    # ------------------------------------------------------------------

    def get_structure(self, types: Optional[List[str]] = None,
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
        return self._get('/structure', params=params)

    # ------------------------------------------------------------------
    # D&D 5e Specific
    # ------------------------------------------------------------------

    def get_actor_details(self, actor_uuid: str,
                          details: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Get detailed D&D 5e actor info.

        details: List of detail categories to retrieve:
                 "resources", "items", "spells", "features",
                 "attributes", "abilities", "skills", etc.
        """
        if details is None:
            details = ["resources", "attributes", "items", "spells", "features"]

        return self._get('/dnd5e/get-actor-details', params={
            'actorUuid': actor_uuid,
            'details': ','.join(details),
        })

    def modify_hp(self, uuid: str, amount: int,
                  increase: bool = True) -> Dict[str, Any]:
        """Increase or decrease an entity's HP."""
        path = '/increase' if increase else '/decrease'
        return self._post(path, body={
            'attribute': 'system.attributes.hp.value',
            'amount': abs(amount),
        }, params={'uuid': uuid})

    def kill_entity(self, uuid: str) -> Dict[str, Any]:
        """Mark an entity as dead (HP=0, dead status, combat tracker)."""
        return self._post('/kill', params={'uuid': uuid})

    def give_item(self, to_uuid: str, item_name: str,
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
        return self._post('/give', body=body)

    def remove_item(self, actor_uuid: str,
                    item_name: str,
                    quantity: int = 1) -> Dict[str, Any]:
        """Remove an item from an entity."""
        return self._post('/remove', body={
            'actorUuid': actor_uuid,
            'itemName': item_name,
            'quantity': quantity,
        })

    def use_ability(self, actor_uuid: str,
                    ability_name: str,
                    target_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Use an ability (generic — spell, feature, or item)."""
        body: Dict[str, Any] = {
            'actorUuid': actor_uuid,
            'abilityName': ability_name,
        }
        if target_uuid:
            body['targetUuid'] = target_uuid
        return self._post('/dnd5e/use-ability', body=body)

    def cast_spell(self, actor_uuid: str,
                   spell_name: str,
                   target_uuid: Optional[str] = None) -> Dict[str, Any]:
        """Cast a spell."""
        body: Dict[str, Any] = {
            'actorUuid': actor_uuid,
            'abilityName': spell_name,
        }
        if target_uuid:
            body['targetUuid'] = target_uuid
        return self._post('/dnd5e/use-spell', body=body)

    def modify_xp(self, actor_uuid: str, amount: int) -> Dict[str, Any]:
        """Add or remove XP from an actor."""
        return self._post('/dnd5e/modify-experience', body={
            'actorUuid': actor_uuid,
            'amount': amount,
        })

    # ------------------------------------------------------------------
    # Encounter / Combat
    # ------------------------------------------------------------------

    def get_encounters(self) -> Dict[str, Any]:
        """Get all active encounters."""
        return self._get('/encounters')

    def start_encounter(self, token_uuids: Optional[List[str]] = None,
                        start_with_players: bool = False,
                        roll_npc: bool = True) -> Dict[str, Any]:
        """Start a new combat encounter."""
        body: Dict[str, Any] = {
            'startWithPlayers': start_with_players,
            'rollNPC': roll_npc,
        }
        if token_uuids:
            body['tokens'] = token_uuids
        return self._post('/start-encounter', body=body)

    def next_turn(self, encounter_id: Optional[str] = None) -> Dict[str, Any]:
        """Advance to the next turn."""
        body: Dict[str, Any] = {}
        if encounter_id:
            body['encounter'] = encounter_id
        return self._post('/next-turn', body=body)

    def next_round(self, encounter_id: Optional[str] = None) -> Dict[str, Any]:
        """Advance to the next round."""
        body: Dict[str, Any] = {}
        if encounter_id:
            body['encounter'] = encounter_id
        return self._post('/next-round', body=body)

    def end_encounter(self, encounter_id: Optional[str] = None) -> Dict[str, Any]:
        """End an encounter."""
        body: Dict[str, Any] = {}
        if encounter_id:
            body['encounter'] = encounter_id
        return self._post('/end-encounter', body=body)

    def add_to_encounter(self, uuids: Optional[List[str]] = None,
                         roll_initiative: bool = True,
                         encounter_id: Optional[str] = None) -> Dict[str, Any]:
        """Add tokens to the current encounter."""
        body: Dict[str, Any] = {'rollInitiative': roll_initiative}
        if uuids:
            body['uuids'] = uuids
        if encounter_id:
            body['encounter'] = encounter_id
        return self._post('/add-to-encounter', body=body)

    # ------------------------------------------------------------------
    # Convenience: Snapshot of current game state
    # ------------------------------------------------------------------

    def get_game_state_summary(self) -> str:
        """
        Build a text summary of the current game state for use by AI agents.
        Pulls actors, active scene, and encounters.
        """
        if not self.is_connected:
            return "(Foundry VTT not connected)"

        parts = []

        try:
            # Get world structure — actors and scenes
            structure = self.get_structure(
                types=['Actor', 'Scene'],
                include_data=False,
                recursive=True,
            )
            parts.append(f"**World Structure:** {_summarize_structure(structure)}")
        except Exception as e:
            parts.append(f"(Could not fetch world structure: {e})")

        try:
            encounters = self.get_encounters()
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

    def roll_dice(self, formula: str,
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
        result = self._post('/roll', body=body)

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

    def search_actors(self, query: str) -> List[Dict[str, Any]]:
        """Search for actors (monsters, NPCs, PCs) by name."""
        result = self.search(query, filter_type='Actor')
        return result.get('results', [])

    def search_scenes(self, query: str) -> List[Dict[str, Any]]:
        """Search for scenes (battlemaps) by name."""
        result = self.search(query, filter_type='Scene')
        return result.get('results', [])

    def search_items(self, query: str) -> List[Dict[str, Any]]:
        """Search for items (weapons, armor, potions, etc.) by name."""
        result = self.search(query, filter_type='Item')
        return result.get('results', [])

    # ------------------------------------------------------------------
    # World Actors
    # ------------------------------------------------------------------

    def get_world_actors(self) -> List[Dict[str, Any]]:
        """Get all actors that exist in the world (not just compendiums)."""
        r = self.get_structure(
            types=['Actor'], recursive=True, include_data=False
        )
        return r.get('data', {}).get('entities', {}).get('actors', [])

    # ------------------------------------------------------------------
    # Stat Block Formatting
    # ------------------------------------------------------------------

    def get_actor_stat_block(self, uuid: str) -> Dict[str, Any]:
        """
        Fetch an actor by UUID and format as a readable D&D stat block.
        Works for both world actors AND compendium actors.
        """
        raw = self.get_entity(uuid)
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
    # Token Operations
    # ------------------------------------------------------------------

    def get_scene_tokens(self, scene_uuid: str) -> List[Dict[str, Any]]:
        """Get all tokens placed on a scene."""
        scene = self.get_entity(scene_uuid)
        return scene.get('data', {}).get('tokens', [])

    def place_token_on_scene(
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
        Uses the update_entity approach to append to the scene's tokens array.

        scene_uuid: UUID of the scene (e.g. "Scene.rnYku67Y2KTEMhH9")
        actor_uuid: UUID of the actor to place (world actors only, e.g. "Actor.xxxxx")
        x, y: Position in pixels on the scene canvas
        """
        actor_data = self.get_entity(actor_uuid).get('data', {})
        actor_id = actor_data.get('_id', '')
        token_name = name or actor_data.get('name', 'Unknown')
        token_img = actor_data.get('img', 'icons/svg/mystery-man.svg')

        # Use prototypeToken data for proper rendering
        proto = actor_data.get('prototypeToken', {})

        token_data = {
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

        # Append to existing tokens and update the scene
        existing_tokens = self.get_scene_tokens(scene_uuid)
        existing_tokens.append(token_data)
        return self.update_entity(scene_uuid, {'tokens': existing_tokens})

    def place_tokens_on_scene(
        self,
        scene_uuid: str,
        placements: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Place multiple tokens on a scene in one update.

        placements: List of dicts with keys:
            - actor_uuid: str (world actor UUID)
            - x: int (pixel position)
            - y: int (pixel position)
            - name: Optional[str]
            - hidden: bool (default False)
        """
        existing_tokens = self.get_scene_tokens(scene_uuid)

        for p in placements:
            actor_data = self.get_entity(p['actor_uuid']).get('data', {})
            actor_id = actor_data.get('_id', '')
            proto = actor_data.get('prototypeToken', {})
            token_img = actor_data.get('img', 'icons/svg/mystery-man.svg')

            token_data = {
                'name': p.get('name') or actor_data.get('name', 'Unknown'),
                'actorId': actor_id,
                'x': p.get('x', 1000),
                'y': p.get('y', 1000),
                'width': proto.get('width', 1),
                'height': proto.get('height', 1),
                'texture': proto.get('texture', {'src': token_img}),
                'disposition': proto.get('disposition', -1),
                'hidden': p.get('hidden', False),
                'actorLink': proto.get('actorLink', False),
                'bar1': proto.get('bar1', {'attribute': 'attributes.hp'}),
                'displayBars': 40,
                'displayName': 30,
            }
            existing_tokens.append(token_data)

        return self.update_entity(scene_uuid, {'tokens': existing_tokens})

    def import_compendium_actor(
        self, compendium_uuid: str, name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Import an actor from a compendium into the world.
        Returns the create result with the new world actor UUID.

        compendium_uuid: e.g. "Compendium.dnd5e.monsters.TjWQOgI3A4UAl7lC"
        """
        raw = self.get_entity(compendium_uuid)
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

        return self.create_entity('Actor', create_data)

    def import_compendium_scene(
        self, compendium_uuid: str, name: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Import a scene from a compendium into the world.
        Returns the create result with the new world scene UUID.
        """
        raw = self.get_entity(compendium_uuid)
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

        return self.create_entity('Scene', create_data)

    # ------------------------------------------------------------------
    # Scene Lighting / Day-Night
    # ------------------------------------------------------------------

    def update_scene_lighting(
        self,
        scene_uuid: str,
        darkness: float = 0.0,
    ) -> Dict[str, Any]:
        """
        Update the darkness level of a scene.
        0.0 = full daylight, 1.0 = pitch black night.
        """
        return self.update_entity(scene_uuid, {
            'environment': {'darknessLevel': darkness}
        })

    def get_world_scenes(self) -> List[Dict[str, Any]]:
        """Get all scenes in the world (not compendiums)."""
        r = self.get_structure(
            types=['Scene'], recursive=True, include_data=False
        )
        return r.get('data', {}).get('entities', {}).get('scenes', [])

    # ------------------------------------------------------------------
    # Playlist Info
    # ------------------------------------------------------------------

    def get_playlist_info(self) -> List[Dict[str, Any]]:
        """
        Get available playlist compendium packs.
        Note: The REST API relay does not support playing/stopping playlists,
        but we can list what's available.
        """
        r = self.get_structure(
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
        # Count entity types
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
