"""
Foundry Architect Agent — Scene & Encounter Setup via Foundry VTT

Translates natural language encounter descriptions into real
Foundry VTT API calls through the relay.
"""

import logging
import json
from google import genai
from agents.tools.foundry_tool import FoundryClient
from typing import Optional

logger = logging.getLogger('FoundryArchitect')


class FoundryArchitectAgent:
    def __init__(self, client, foundry: Optional[FoundryClient] = None,
                 model_id="gemini-2.0-flash"):
        self.foundry = foundry or FoundryClient()
        self.ai_client = client
        self.model_id = model_id

        self.system_prompt = """
        You are the Foundry Architect, a specialized agent for configuring Foundry VTT.

        Your Goal:
        Translate natural language descriptions into a JSON plan of
        Foundry VTT actions. The system will execute these via the REST API.

        Available Actions:
        1. "search" — Find existing actors/items by name
           { "type": "search", "query": "Goblin", "filter": "Actor" }

        2. "create_actor" — Create a new Actor
           { "type": "create_actor", "name": "Goblin Ambusher", "actor_type": "npc", "img": "icons/svg/mystery-man.svg" }

        3. "create_item" — Create a new Item
           { "type": "create_item", "name": "Shortsword", "item_type": "weapon" }

        4. "give_item" — Give an item to an actor
           { "type": "give_item", "actor_name": "Goblin Ambusher", "item_name": "Shortsword" }

        5. "start_encounter" — Start a combat encounter
           { "type": "start_encounter", "roll_npc": true }

        6. "import_actor" — Import actor from compendium
           { "type": "import_actor", "compendium_uuid": "Compendium.dnd5e.monsters.TjWQOgI3A4UAl7lC" }

        7. "place_token" — Place an actor on the active scene
           { "type": "place_token", "actor_name": "Goblin Ambusher", "x": 1000, "y": 1000 }

        8. "set_darkness" — Change the scene lighting/darkness level
           { "type": "set_darkness", "darkness": 0.5 }
           Values: 0.0 = bright daylight, 0.3 = overcast/dim, 0.5 = twilight, 0.7 = dark, 1.0 = pitch black

        9. "end_encounter" — End the current combat encounter
           { "type": "end_encounter" }

        10. "activate_scene" — Activate a different scene by name
            { "type": "activate_scene", "scene_name": "Forest Path" }

        11. "execute_macro" — Run a Foundry macro (for Tagger, FXMaster, custom automation)
            { "type": "execute_macro", "macro_name": "Rain Effect" }

        12. "play_playlist" — Start playing a playlist by name
            { "type": "play_playlist", "playlist_name": "Forest Ambience" }

        13. "stop_playlist" — Stop all playing playlists
            { "type": "stop_playlist" }

        JSON Output Format:
        {
            "rationale": "Brief explanation of setup.",
            "actions": [ ... array of action objects ... ]
        }

        Rules:
        - Search for existing actors before creating new ones.
        - Use descriptive names for new actors.
        - Always respond with ONLY the JSON object.
        - For lighting changes, ALWAYS use the set_darkness action.
        - For scene changes, use activate_scene to find and activate the matching scene.
        - For ambient audio, use play_playlist with a descriptive name.
        """

    async def process_request(self, user_input: str) -> str:
        """
        Generate a setup plan and execute it using the FoundryClient.
        """
        logger.info(f"Architect received request: {user_input}")

        if not self.foundry.is_connected:
            if not await self.foundry.connect():
                return ("⚠️ **Foundry VTT is not connected.** "
                        "Make sure Foundry is running with the REST API module enabled.")

        if not self.ai_client:
            return "Error: Architect not connected to AI model."

        try:
            # 1. Generate Plan
            prompt = f"""
            System Prompt: {self.system_prompt}
            User Request: {user_input}

            Generate the JSON setup plan.
            """

            response = await self.ai_client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )

            plan = json.loads(response.text)
            logger.info(f"Generated Setup Plan: {plan}")

            # 2. Execute Plan
            execution_log = []
            context = {}  # Track created entities for cross-referencing

            for action in plan.get("actions", []):
                action_type = action.get("type")
                result = await self._execute_action(action_type, action, context)
                execution_log.append(result)

            summary = "\n".join(f"  • {r}" for r in execution_log)
            return (f"**🏗️ Architect Report**\n"
                    f"{plan.get('rationale', '')}\n\n"
                    f"**Execution Log:**\n{summary}")

        except Exception as e:
            logger.error(f"Architect execution failed: {e}", exc_info=True)
            return f"⚠️ Architect encountered an error: {e}"

    async def _execute_action(self, action_type: str, action: dict,
                              context: dict) -> str:
        """Execute a single action from the plan."""
        try:
            if action_type == "search":
                query = action.get("query", "")
                filter_type = action.get("filter")
                result = await self.foundry.search(query, filter_type=filter_type)
                context[f"search_{query}"] = result
                return f"🔍 Searched for '{query}': found results"

            elif action_type == "create_actor":
                name = action.get("name", "Unknown")
                data = {
                    "name": name,
                    "type": action.get("actor_type", "npc"),
                }
                if action.get("img"):
                    data["img"] = action["img"]

                result = await self.foundry.create_entity("Actor", data)
                if isinstance(result, dict):
                    uuid = result.get('uuid') or result.get('_id')
                    if uuid:
                        context[f"actor_{name}"] = uuid
                return f"✅ Created Actor '{name}'"

            elif action_type == "create_item":
                name = action.get("name", "Unknown")
                data = {
                    "name": name,
                    "type": action.get("item_type", "equipment"),
                }
                await self.foundry.create_entity("Item", data)
                return f"✅ Created Item '{name}'"

            elif action_type == "give_item":
                actor_name = action.get("actor_name", "")
                item_name = action.get("item_name", "")
                actor_uuid = context.get(f"actor_{actor_name}")
                if actor_uuid:
                    await self.foundry.give_item(actor_uuid, item_name)
                    return f"🎒 Gave '{item_name}' to '{actor_name}'"
                else:
                    return f"⚠️ Actor '{actor_name}' not found in context"

            elif action_type == "start_encounter":
                await self.foundry.start_encounter(
                    roll_npc=action.get("roll_npc", True),
                    start_with_players=action.get("start_with_players", False),
                )
                return "⚔️ Combat encounter started"

            elif action_type == "import_actor":
                uuid = action.get("compendium_uuid", "")
                name = action.get("name")
                result = await self.foundry.import_compendium_actor(uuid, name)

                if isinstance(result, dict):
                    new_uuid = result.get('uuid') or result.get('_id')
                    actor_name = result.get('name') or name or "Unknown"
                    if new_uuid:
                        context[f"actor_{actor_name}"] = new_uuid
                        context[uuid] = new_uuid

                return f"📥 Imported actor from {uuid}"

            elif action_type == "place_token":
                actor_name = action.get("actor_name", "")

                # Resolve actor UUID from context or search results
                actor_uuid = context.get(f"actor_{actor_name}")
                if not actor_uuid:
                    for key, val in context.items():
                        if key.startswith("search_") and isinstance(val, list):
                            for item in val:
                                if item.get('name') == actor_name:
                                    actor_uuid = item.get('uuid')
                                    break

                if not actor_uuid:
                    return f"⚠️ Actor '{actor_name}' not found for placement"

                # Use active scene or specified scene
                scene_uuid = action.get("scene_uuid")
                if not scene_uuid:
                    scenes = await self.foundry.get_world_scenes()
                    active = [s for s in scenes if s.get('active')]
                    if active:
                        scene_uuid = active[0]['uuid']
                    elif scenes:
                        scene_uuid = scenes[0]['uuid']

                if not scene_uuid:
                    return "⚠️ No active scene found for placement"

                x = action.get("x", 1000)
                y = action.get("y", 1000)

                await self.foundry.place_token_on_scene(scene_uuid, actor_uuid, x, y)
                return f"📍 Placed '{actor_name}' at ({x}, {y})"

            elif action_type == "set_darkness":
                darkness = action.get("darkness", 0.0)
                try:
                    darkness = max(0.0, min(1.0, float(darkness)))
                except (TypeError, ValueError):
                    darkness = 0.0

                scenes = await self.foundry.get_world_scenes()
                active = [s for s in scenes if s.get('active')]
                if active:
                    scene_uuid = active[0]['uuid']
                    await self.foundry.update_scene_lighting(scene_uuid, darkness=darkness)
                    return f"🌙 Set darkness to {darkness} on '{active[0].get('name', '?')}'"
                elif scenes:
                    scene_uuid = scenes[0]['uuid']
                    await self.foundry.update_scene_lighting(scene_uuid, darkness=darkness)
                    return f"🌙 Set darkness to {darkness} on '{scenes[0].get('name', '?')}'"
                else:
                    return "⚠️ No scenes found to adjust lighting"

            elif action_type == "end_encounter":
                encounter_id = action.get("encounter_id")
                await self.foundry.end_encounter(encounter_id=encounter_id)
                return "🏳️ Combat encounter ended"

            elif action_type == "activate_scene":
                scene_name = action.get("scene_name", "")
                if not scene_name:
                    return "⚠️ No scene name provided"

                scenes = await self.foundry.get_world_scenes()
                match = None
                for s in scenes:
                    if scene_name.lower() in s.get('name', '').lower():
                        match = s
                        break

                if match:
                    await self.foundry.activate_scene(match['uuid'])
                    return f"🗺️ Switched to scene '{match.get('name', '?')}'"
                else:
                    available = [s.get('name', '?') for s in scenes]
                    return f"⚠️ No scene matching '{scene_name}'. Available: {', '.join(available)}"

            elif action_type == "execute_macro":
                macro_name = action.get("macro_name", "")
                args = action.get("args")
                await self.foundry.execute_macro(macro_name, args)
                return f"⚙️ Executed macro '{macro_name}'"

            elif action_type == "play_playlist":
                playlist_name = action.get("playlist_name", "")
                playlists = await self.foundry.get_playlists()
                match = next(
                    (p for p in playlists
                     if playlist_name.lower() in p.get('name', '').lower()),
                    None
                )
                if match:
                    await self.foundry.play_playlist(match.get('uuid', ''))
                    return f"🎵 Playing playlist '{match.get('name', '?')}'"
                return f"⚠️ Playlist '{playlist_name}' not found"

            elif action_type == "stop_playlist":
                await self.foundry.stop_all_playlists()
                return "🔇 All playlists stopped"

            # Legacy alias
            elif action_type == "switch_scene":
                return await self._execute_action("activate_scene", action, context)

            else:
                return f"❓ Unknown action type: {action_type}"

        except Exception as e:
            return f"❌ Error executing {action_type}: {e}"
