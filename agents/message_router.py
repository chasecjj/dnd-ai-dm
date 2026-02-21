"""
MessageRouterAgent — Secretary agent that classifies and routes Discord messages.

Determines which agents need to be invoked to minimize unnecessary API calls.
Uses the `system_instruction` parameter for stable identity.
"""

import json
import logging
from typing import Dict, Any
from enum import Enum
from google import genai
from tools.context_assembler import ContextAssembler

logger = logging.getLogger('MessageRouter')


class MessageType(Enum):
    """Classification of incoming messages."""
    GAME_ACTION = "game_action"          # "I cast Fireball at the troll"
    NARRATIVE_REQUEST = "narrative_request"  # "Tell me about my backstory" / flashbacks / lore
    GAME_QUESTION = "game_question"      # "What's in front of me?"
    OUT_OF_GAME = "out_of_game"          # "Can you give me a synopsis?"
    CASUAL_CHAT = "casual_chat"          # "lol nice"
    COMMAND = "command"                  # "!setup ..."


class AgentRoute:
    """Defines which agents should handle a message."""
    def __init__(
        self,
        message_type: MessageType,
        needs_board_monitor: bool = False,
        needs_rules_lawyer: bool = False,
        needs_storyteller: bool = False,
        direct_response: bool = False,
    ):
        self.message_type = message_type
        self.needs_board_monitor = needs_board_monitor
        self.needs_rules_lawyer = needs_rules_lawyer
        self.needs_storyteller = needs_storyteller
        self.direct_response = direct_response

    def __repr__(self):
        agents = []
        if self.needs_board_monitor:
            agents.append("BoardMonitor")
        if self.needs_rules_lawyer:
            agents.append("RulesLawyer")
        if self.needs_storyteller:
            agents.append("Storyteller")
        if self.direct_response:
            agents.append("DirectResponse")
        return f"AgentRoute({self.message_type.value}, agents=[{', '.join(agents)}])"


# Stable classifier identity — goes in system_instruction
CLASSIFIER_IDENTITY = """You are a message classifier for a D&D Discord bot. Your ONLY job is to classify
incoming player messages into exactly one category and return a JSON response.

Categories:
- "game_action": The player is performing an in-game action OR requesting a narrative scene.
  This includes: attacking, casting spells, moving, interacting with objects/NPCs in-character,
  AND requests for flashbacks, backstory scenes, lore exploration, roleplay moments, or any
  request that should produce immersive narrative prose (even if phrased as a request to the DM).
  Examples: "I swing my sword at the goblin", "I cast Fireball", "I search the chest",
  "Tell me about my character's past", "I want to learn about my religion",
  "Can we do a flashback to how I met my companion?", "I pray to my god",
  "Describe the scene where I first took my oath".
- "game_question": The player is asking about the current game state or spatial information.
  Examples: "Where is the goblin?", "Can I see the door?", "How far am I from the troll?"
- "out_of_game": The player is asking a purely mechanical/meta question that needs a short
  factual answer, NOT a narrative scene. Examples: "Can you give me a synopsis?",
  "What level am I?", "How does concentration work?", "What happened last session?",
  "What are my spell slots?"
- "casual_chat": The message is casual conversation not directed at the DM or game.
  Examples: "lol", "brb", "nice", "gg".

IMPORTANT: If the player asks for a scene, story, flashback, backstory, lore exploration,
or anything that would benefit from immersive narrative prose, classify as "game_action"
even if they phrase it as a question to the DM. Only use "out_of_game" for short factual answers.

You MUST respond with ONLY a JSON object:
{"type": "<category>", "reason": "<one-line explanation>"}
"""


class MessageRouterAgent:
    """Secretary agent that classifies and routes incoming Discord messages."""

    def __init__(self, client, context_assembler: ContextAssembler, model_id: str = "gemini-2.0-flash"):
        self.client = client
        self.context = context_assembler
        self.model_id = model_id

    async def classify_message(self, message_content: str) -> Dict[str, Any]:
        """Classify a message into a type category."""
        logger.info(f"Classifying message: {message_content}")

        # Quick heuristic checks for obvious cases (avoids API call)
        lower = message_content.lower().strip()

        # Very short messages are usually casual
        if len(lower) <= 5 and not any(kw in lower for kw in ["cast", "move", "hit", "use", "look"]):
            result = {"type": "casual_chat", "reason": "Very short message, likely casual"}
            logger.info(f"Heuristic classification: {result}")
            return result

        # Narrative/lore/backstory requests should always go to the Storyteller
        narrative_keywords = [
            "flashback", "backstory", "my past", "my religion", "my oath",
            "my beliefs", "how i became", "tell me about my", "learn more about my",
            "describe the scene", "roleplay", "act as if", "in character",
            "my faction", "my god", "my patron", "my history", "my training",
        ]
        if any(kw in lower for kw in narrative_keywords):
            result = {"type": "narrative_request", "reason": "Narrative/backstory request — needs Storyteller"}
            logger.info(f"Heuristic classification: {result}")
            return result

        # Use the LLM for ambiguous messages
        if self.client:
            try:
                response = await self.client.aio.models.generate_content(
                    model=self.model_id,
                    contents=f'Message to classify: "{message_content}"\n\nRespond with JSON only.',
                    config=genai.types.GenerateContentConfig(
                        system_instruction=CLASSIFIER_IDENTITY,
                        temperature=0.0,  # Deterministic classification
                    )
                )
                text = response.text.strip()

                # Extract JSON from possible markdown wrapping
                if "```json" in text:
                    text = text.split("```json")[1].split("```")[0].strip()
                elif "```" in text:
                    text = text.split("```")[1].split("```")[0].strip()

                result = json.loads(text)
                logger.info(f"LLM classification: {result}")
                return result

            except Exception as e:
                logger.error(f"Classification failed, defaulting to game_action: {e}")
                return {"type": "game_action", "reason": f"Classification error, defaulting: {e}"}
        else:
            return {"type": "game_action", "reason": "No model connected, defaulting to game_action"}

    def build_route(self, classification: Dict[str, Any]) -> AgentRoute:
        """Convert a classification result into an agent routing plan."""
        msg_type_str = classification.get("type", "game_action")

        try:
            msg_type = MessageType(msg_type_str)
        except ValueError:
            logger.warning(f"Unknown message type '{msg_type_str}', defaulting to game_action")
            msg_type = MessageType.GAME_ACTION

        if msg_type == MessageType.GAME_ACTION:
            return AgentRoute(
                message_type=msg_type,
                needs_board_monitor=True,
                needs_rules_lawyer=True,
                needs_storyteller=True,
            )
        elif msg_type == MessageType.NARRATIVE_REQUEST:
            # Backstory, flashbacks, lore exploration — Storyteller only, no mechanics
            return AgentRoute(
                message_type=msg_type,
                needs_board_monitor=False,
                needs_rules_lawyer=False,
                needs_storyteller=True,
            )
        elif msg_type == MessageType.GAME_QUESTION:
            return AgentRoute(
                message_type=msg_type,
                needs_board_monitor=True,
                needs_rules_lawyer=False,
                needs_storyteller=True,
            )
        elif msg_type == MessageType.OUT_OF_GAME:
            return AgentRoute(
                message_type=msg_type,
                direct_response=True,
            )
        elif msg_type == MessageType.CASUAL_CHAT:
            return AgentRoute(
                message_type=msg_type,
            )
        else:
            return AgentRoute(
                message_type=MessageType.GAME_ACTION,
                needs_board_monitor=True,
                needs_rules_lawyer=True,
                needs_storyteller=True,
            )

    async def route(self, message_content: str) -> AgentRoute:
        """Full routing pipeline: classify then build route."""
        classification = await self.classify_message(message_content)
        route = self.build_route(classification)
        logger.info(f"Routed message -> {route}")
        return route

    async def generate_direct_response(self, message_content: str) -> str:
        """Generate a direct response for out-of-game questions using vault context."""
        logger.info(f"Generating direct response for: {message_content}")
        if not self.client:
            return "I'm having trouble connecting right now. Try again in a moment."

        # Use vault context instead of hardcoded campaign data
        vault_context = self.context.build_storyteller_context()

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=f"""## Current World State
{vault_context}

---

Player's out-of-game question: {message_content}

Answer concisely and helpfully. Stay in character as a friendly DM.""",
                config=genai.types.GenerateContentConfig(
                    system_instruction="You are a helpful D&D Dungeon Master assistant. Answer out-of-game questions concisely using the provided world state. Be friendly and informative.",
                    temperature=0.5,
                )
            )
            return response.text
        except Exception as e:
            logger.error(f"Direct response generation failed: {e}")
            return "I'm having trouble thinking right now. Try again in a moment."


if __name__ == "__main__":
    print("Message Router Agent initialized.")
