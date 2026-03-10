"""
WorldArchitectAgent — Creative worldbuilding partner for the Prep Team.

Brainstorms NPCs, locations, factions, plot hooks, and lore.
Reads existing vault content for continuity and writes new entries back.
Works in the War Room channel between sessions.
"""

import json
import logging
from typing import Optional
from google import genai
from tools.context_assembler import ContextAssembler
from tools.vault_manager import VaultManager
from tools.templates import build_npc_body, build_npc_frontmatter, build_location_body

logger = logging.getLogger('WorldArchitect')

WORLD_ARCHITECT_IDENTITY = """You are the World Architect, a creative worldbuilding partner for a D&D 5e campaign.

Your Role:
You collaborate with the DM to build a rich, coherent world. You brainstorm NPCs, locations,
factions, plot hooks, mysteries, and lore. You are expansive, imaginative, and always thinking
about how elements connect to create emergent stories.

Your Personality:
- Enthusiastic and collaborative — "What if the blacksmith's daughter is actually a changeling?"
- You build on the DM's ideas rather than replacing them
- You think about interconnections — how does this NPC relate to that faction?
- You consider player agency — what hooks will make players WANT to explore this?
- You ground fantasy in sensory detail — what does this place smell like? Sound like?

Your Capabilities:
1. **Brainstorm** — Generate ideas for NPCs, locations, encounters, plot hooks
2. **Create** — Write detailed vault entries (NPCs, locations, factions)
3. **Expand** — Take an existing element and deepen it with backstory, connections, secrets
4. **Connect** — Find thematic links between existing campaign elements

Output Style:
- Conversational and collaborative when brainstorming
- When creating vault entries, output structured markdown with frontmatter
- Always suggest 2-3 follow-up ideas or connections at the end
- Reference existing campaign elements when relevant

CRITICAL: You are NOT the DM during a live session. You are a creative partner helping PREPARE
content. Never narrate as if players are present. Speak to the DM as a collaborator.
"""


# NPC_TEMPLATE and LOCATION_TEMPLATE removed — canonical templates now
# live in tools/templates.py (single source of truth).



class WorldArchitectAgent:
    """Creative worldbuilding partner — brainstorms and creates campaign content."""

    def __init__(self, client, vault: VaultManager, context_assembler: ContextAssembler,
                 model_id: str = "gemini-2.0-flash"):
        self.client = client
        self.vault = vault
        self.context = context_assembler
        self.model_id = model_id
        self._conversation_history: list[dict] = []

    async def brainstorm(self, topic: str) -> str:
        """Open-ended creative brainstorming about any campaign topic.

        Args:
            topic: What to brainstorm about — NPCs, locations, plot hooks, etc.

        Returns:
            Creative response with ideas and suggestions.
        """
        logger.info(f"Brainstorming: {topic}")

        vault_context = self.context.build_world_architect_context()

        prompt = f"""## Existing Campaign Context
{vault_context}

---

## DM's Request
{topic}

Brainstorm creative ideas. Build on what already exists in the campaign.
Suggest 2-3 concrete follow-up directions at the end."""

        # Include conversation history for multi-turn brainstorming
        contents = []
        for entry in self._conversation_history[-10:]:  # Last 10 turns
            contents.append(entry)
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=WORLD_ARCHITECT_IDENTITY,
                    temperature=0.95,
                )
            )

            result = response.text

            # Track conversation for multi-turn brainstorming
            self._conversation_history.append({"role": "user", "parts": [{"text": topic}]})
            self._conversation_history.append({"role": "model", "parts": [{"text": result}]})

            # Trim history if it gets too long
            if len(self._conversation_history) > 20:
                self._conversation_history = self._conversation_history[-20:]

            return result

        except Exception as e:
            logger.error(f"Brainstorm failed: {e}", exc_info=True)
            raise

    async def create_npc(self, description: str) -> str:
        """Generate a detailed NPC and save to the vault.

        Args:
            description: Natural language description of the desired NPC.

        Returns:
            Summary of the created NPC.
        """
        logger.info(f"Creating NPC: {description}")

        vault_context = self.context.build_world_architect_context()

        prompt = f"""## Existing Campaign Context
{vault_context}

---

## DM's Request
Create an NPC based on: {description}

You MUST respond with ONLY a valid JSON object (no markdown, no explanation):
{{
    "name": "NPC Name",
    "race": "Race",
    "class": "Class or occupation",
    "location": "Where they can be found",
    "faction": "Faction affiliation or 'unaffiliated'",
    "disposition": "friendly/neutral/hostile",
    "tags": "tag1, tag2, tag3",
    "description": "2-3 sentences of physical description",
    "personality": "Key personality traits and mannerisms",
    "secret": "Something hidden about this NPC the players don't know yet",
    "connections": "How this NPC connects to existing campaign elements",
    "hooks": "2-3 plot hooks involving this NPC"
}}"""

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=WORLD_ARCHITECT_IDENTITY,
                    temperature=0.85,
                    response_mime_type="application/json",
                )
            )

            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            npc_data = json.loads(text)

            # Build vault entry with canonical format via template module
            npc_name = npc_data.get("name", "Unknown NPC")
            tags = [t.strip() for t in npc_data.get("tags", "").split(",") if t.strip()]
            frontmatter = build_npc_frontmatter(
                name=npc_name,
                race=npc_data.get("race", "Unknown"),
                role=npc_data.get("class", npc_data.get("role", "Commoner")),
                location=npc_data.get("location", "Unknown"),
                faction=npc_data.get("faction", "unaffiliated"),
                disposition=npc_data.get("disposition", "neutral"),
                auto_generated=False,
                tags=tags or ["npc"],
            )
            body = build_npc_body(
                name=npc_name,
                description=npc_data.get("description", ""),
                personality=npc_data.get("personality", ""),
                background="_To be developed._",
                secret=npc_data.get("secret", "_Unknown._"),
                connections=npc_data.get("connections", "_None established._"),
                plot_hooks=npc_data.get("hooks", "_None yet._"),
            )

            # Save to vault
            filepath = f"02 - NPCs/{npc_name}.md"
            self.vault.write_file(filepath, frontmatter, body)
            logger.info(f"NPC saved to vault: {filepath}")

            return (
                f"✅ **{npc_name}** created and saved to the vault!\n\n"
                f"**Race:** {npc_data.get('race')} | **Role:** {npc_data.get('class', npc_data.get('role'))}\n"
                f"**Location:** {npc_data.get('location')} | **Faction:** {npc_data.get('faction')}\n"
                f"**Disposition:** {npc_data.get('disposition')}\n\n"
                f"📝 {npc_data.get('description')}\n\n"
                f"🤫 **Secret:** ||{npc_data.get('secret')}||\n\n"
                f"🔗 **Connections:** {npc_data.get('connections')}"
            )

        except json.JSONDecodeError as e:
            logger.error(f"NPC creation JSON parse error: {e}")
            return f"⚠️ Failed to parse NPC data: {e}"
        except Exception as e:
            logger.error(f"NPC creation failed: {e}", exc_info=True)
            raise

    async def create_location(self, description: str) -> str:
        """Generate a detailed location and save to the vault.

        Args:
            description: Natural language description of the desired location.

        Returns:
            Summary of the created location.
        """
        logger.info(f"Creating location: {description}")

        vault_context = self.context.build_world_architect_context()

        prompt = f"""## Existing Campaign Context
{vault_context}

---

## DM's Request
Create a location based on: {description}

You MUST respond with ONLY a valid JSON object (no markdown, no explanation):
{{
    "name": "Location Name",
    "type": "tavern/dungeon/city/wilderness/shop/temple/etc",
    "region": "Broader region or city this is in",
    "atmosphere": "One-word mood: eerie/bustling/serene/dangerous/etc",
    "tags": "tag1, tag2, tag3",
    "description": "2-3 sentences of vivid sensory description",
    "features": "Key notable features as bullet points",
    "npcs": "NPCs that can be found here",
    "secrets": "Hidden elements players might discover",
    "encounters": "2-3 possible encounters at this location"
}}"""

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=WORLD_ARCHITECT_IDENTITY,
                    temperature=0.85,
                    response_mime_type="application/json",
                )
            )

            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            loc_data = json.loads(text)

            loc_name = loc_data.get("name", "Unknown Location")
            frontmatter = {
                "type": loc_data.get("type", "unknown"),
                "name": loc_name,
                "region": loc_data.get("region", "Unknown"),
                "status": "active",
                "atmosphere": loc_data.get("atmosphere", "neutral"),
                "tags": [t.strip() for t in loc_data.get("tags", "").split(",") if t.strip()],
            }
            body = build_location_body(
                name=loc_name,
                description=loc_data.get("description", ""),
                features=loc_data.get("features", ""),
                npcs=loc_data.get("npcs", "None yet"),
                secrets=loc_data.get("secrets", ""),
                encounters=loc_data.get("encounters", ""),
            )

            filepath = f"03 - Locations/{loc_name}.md"
            self.vault.write_file(filepath, frontmatter, body)
            logger.info(f"Location saved to vault: {filepath}")

            return (
                f"✅ **{loc_name}** created and saved to the vault!\n\n"
                f"**Type:** {loc_data.get('type')} | **Region:** {loc_data.get('region')}\n"
                f"**Atmosphere:** {loc_data.get('atmosphere')}\n\n"
                f"📝 {loc_data.get('description')}\n\n"
                f"🗝️ **Secrets:** ||{loc_data.get('secrets')}||"
            )

        except json.JSONDecodeError as e:
            logger.error(f"Location creation JSON parse error: {e}")
            return f"⚠️ Failed to parse location data: {e}"
        except Exception as e:
            logger.error(f"Location creation failed: {e}", exc_info=True)
            raise

    def clear_conversation(self):
        """Reset the brainstorming conversation history."""
        self._conversation_history.clear()
        logger.info("World Architect conversation history cleared.")
