"""
PrepRouterAgent — Routes War Room messages to the correct Prep Team agent.

Classifies DM messages as worldbuilding, session planning, scene setup, or general questions.
Only activates in the War Room channel.
"""

import json
import logging
from typing import Dict, Any
from enum import Enum
from google import genai
from tools.context_assembler import ContextAssembler

logger = logging.getLogger('PrepRouter')


class PrepIntent(Enum):
    """Classification of prep-channel messages."""
    WORLDBUILDING = "worldbuilding"
    SESSION_PLANNING = "session_planning"
    SCENE_SETUP = "scene_setup"
    NPC_CREATE = "npc_create"
    LOCATION_CREATE = "location_create"
    GENERAL_QUESTION = "general_question"


PREP_CLASSIFIER_IDENTITY = """You are a message classifier for a D&D campaign prep channel (the "War Room").
Your ONLY job is to classify the DM's messages into exactly one category and return a JSON response.

Categories:
- "worldbuilding": The DM wants to brainstorm, explore ideas, discuss lore, expand existing elements,
  or creatively develop the campaign world. This is the DEFAULT for creative/exploratory messages.
  Examples: "What if there's a secret cult?", "Tell me more about the Zhentarim", "I need ideas for a villain"

- "npc_create": The DM explicitly wants to CREATE a specific NPC and save it.
  Examples: "Create an NPC tavern keeper", "Make a mysterious wizard", "I need a new quest giver"

- "location_create": The DM explicitly wants to CREATE a specific location and save it.
  Examples: "Create a haunted forest", "Make a black market bazaar", "Build a dungeon entrance"

- "session_planning": The DM wants to plan a session, discuss pacing, structure encounters,
  or organize the campaign timeline.
  Examples: "Let's plan session 5", "What should happen next session?", "I need encounter ideas for level 3"

- "scene_setup": The DM wants to set up something in Foundry VTT — build a scene, place tokens,
  configure an encounter on the virtual tabletop.
  Examples: "Set up a forest battle map", "Place 3 goblins", "Prepare the tavern scene in Foundry"

- "general_question": The DM asks an out-of-game question about rules, tools, or the system.
  Examples: "How does concentration work?", "What's the CR for a young dragon?"

You MUST respond with ONLY a JSON object:
{"intent": "<category>", "reason": "<one-line explanation>"}
"""


class PrepRoute:
    """Defines which prep agent should handle the message."""

    def __init__(self, intent: PrepIntent, reason: str = ""):
        self.intent = intent
        self.reason = reason

    def __repr__(self):
        return f"PrepRoute(intent={self.intent.value}, reason={self.reason})"


class PrepRouterAgent:
    """Routes War Room messages to the correct prep agent."""

    def __init__(self, client, context_assembler: ContextAssembler,
                 model_id: str = "gemini-2.0-flash"):
        self.client = client
        self.context = context_assembler
        self.model_id = model_id

    async def classify(self, message_content: str) -> Dict[str, Any]:
        """Classify a prep message into an intent category.

        Args:
            message_content: The DM's message.

        Returns:
            Dict with 'intent' and 'reason'.
        """
        if not self.client:
            return {"intent": "worldbuilding", "reason": "No model — default to worldbuilding"}

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=message_content,
                config=genai.types.GenerateContentConfig(
                    system_instruction=PREP_CLASSIFIER_IDENTITY,
                    temperature=0.1,
                )
            )

            text = response.text.strip()
            if "```json" in text:
                text = text.split("```json")[1].split("```")[0].strip()
            elif "```" in text:
                text = text.split("```")[1].split("```")[0].strip()

            result = json.loads(text)
            logger.info(f"Prep classification: {result}")
            return result

        except json.JSONDecodeError:
            logger.warning("Failed to parse prep classification — defaulting to worldbuilding")
            return {"intent": "worldbuilding", "reason": "Parse error — default"}
        except Exception as e:
            logger.error(f"Prep classification failed: {e}", exc_info=True)
            return {"intent": "worldbuilding", "reason": f"Error: {e}"}

    async def route(self, message_content: str) -> PrepRoute:
        """Classify and build a route for a prep message.

        Args:
            message_content: The DM's message.

        Returns:
            PrepRoute indicating which agent should handle it.
        """
        classification = await self.classify(message_content)
        intent_str = classification.get("intent", "worldbuilding")
        reason = classification.get("reason", "")

        try:
            intent = PrepIntent(intent_str)
        except ValueError:
            logger.warning(f"Unknown prep intent '{intent_str}' — defaulting to worldbuilding")
            intent = PrepIntent.WORLDBUILDING

        route = PrepRoute(intent=intent, reason=reason)
        logger.info(f"Prep route: {route}")
        return route
