"""
CampaignPlannerAgent — Session planning and campaign pacing for the Prep Team.

Structures session outlines, tracks narrative arcs, anticipates player choices,
and suggests branching paths. Works in the War Room channel between sessions.
"""

import json
import logging
from typing import Optional
from google import genai
from tools.context_assembler import ContextAssembler
from tools.vault_manager import VaultManager

logger = logging.getLogger('CampaignPlanner')

CAMPAIGN_PLANNER_IDENTITY = """You are the Campaign Planner, a strategic session-planning partner for a D&D 5e campaign.

Your Role:
You help the DM plan upcoming sessions, structure narrative arcs, and anticipate player choices.
You think in terms of dramatic pacing, player agency, and memorable moments.

Your Personality:
- Strategic and organized — you think about story beats, tension curves, and player engagement
- You anticipate player choices — "If the party goes left, prepare X. If right, prepare Y."
- You structure sessions with clear acts: Hook → Rising Action → Climax → Resolution
- You track long-term plot threads and remind the DM of unresolved hooks
- You balance combat, roleplay, and exploration

Your Capabilities:
1. **Plan Sessions** — Create structured outlines with acts, encounters, and branching paths
2. **Suggest Hooks** — Generate narrative hooks based on unresolved quests and player backstories
3. **Review Arcs** — Analyze the campaign's narrative trajectory and suggest pacing adjustments
4. **Track Threads** — Identify dangling plot threads that need resolution

Output Style:
- Clear, structured markdown with headers and bullet points
- Use encounter difficulty estimates (Easy/Medium/Hard/Deadly)
- Include "If/Then" branches for player choice
- End with preparation checklist (maps needed, NPCs to prep, music cues)

CRITICAL: You are NOT the DM during a live session. You are a planning partner helping PREPARE.
Never narrate as if players are present. Speak to the DM as a collaborator.
"""

SESSION_PLAN_TEMPLATE = """---
session_number: {session_num}
planned_date: TBD
status: planned
location: {location}
estimated_duration: {duration}
tags: [session-plan]
---

## Hook
{hook}

## Act 1 — {act1_title}
{act1}

## Act 2 — {act2_title}
{act2}

## Act 3 — {act3_title}
{act3}

## Branching Paths
{branches}

## Preparation Checklist
{checklist}
"""


class CampaignPlannerAgent:
    """Strategic session planner — structures outlines, tracks arcs, anticipates choices."""

    def __init__(self, client, vault: VaultManager, context_assembler: ContextAssembler,
                 model_id: str = "gemini-2.0-flash"):
        self.client = client
        self.vault = vault
        self.context = context_assembler
        self.model_id = model_id
        self._conversation_history: list[dict] = []

    async def plan_session(self, notes: str, session_num: Optional[int] = None) -> str:
        """Create a structured session plan.

        Args:
            notes: DM's notes or ideas for the session.
            session_num: Optional session number. Auto-detects if not provided.

        Returns:
            Formatted session plan.
        """
        if session_num is None:
            session_num = self.context.current_session + 1

        logger.info(f"Planning session {session_num}: {notes}")

        vault_context = self.context.build_campaign_planner_context()

        prompt = f"""## Campaign Context
{vault_context}

---

## Session {session_num} Planning
The DM's notes/ideas: {notes}

Create a structured session plan. Include:
1. A compelling **Hook** to start the session
2. **Three acts** with clear beats (exploration, roleplay, combat mix)
3. **Branching paths** — anticipate 2-3 player choices and prepare for each
4. **Preparation checklist** — maps, NPCs, music cues, tokens needed

Consider the party's current state, active quests, and unresolved plot threads.
Format as clear markdown with headers."""

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=CAMPAIGN_PLANNER_IDENTITY,
                    temperature=0.7,
                )
            )

            result = response.text

            # Track conversation
            self._conversation_history.append({"role": "user", "parts": [{"text": notes}]})
            self._conversation_history.append({"role": "model", "parts": [{"text": result}]})

            return f"📋 **Session {session_num} Plan**\n\n{result}"

        except Exception as e:
            logger.error(f"Session planning failed: {e}", exc_info=True)
            raise

    async def suggest_hooks(self) -> str:
        """Generate narrative hooks based on unresolved quests and campaign state.

        Returns:
            List of suggested plot hooks.
        """
        logger.info("Generating plot hooks")

        vault_context = self.context.build_campaign_planner_context()

        prompt = f"""## Campaign Context
{vault_context}

---

Analyze the campaign state and suggest 3-5 compelling plot hooks.

For each hook:
- **Hook Name** — a catchy title
- **Source** — where this connects to (unresolved quest, NPC backstory, faction conflict)
- **Setup** — how to introduce this to the players
- **Escalation** — what happens if the players ignore it
- **Reward** — what the players gain from pursuing it

Prioritize hooks that connect to existing campaign threads."""

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=CAMPAIGN_PLANNER_IDENTITY,
                    temperature=0.8,
                )
            )
            return f"🎣 **Plot Hook Suggestions**\n\n{response.text}"

        except Exception as e:
            logger.error(f"Hook suggestion failed: {e}", exc_info=True)
            raise

    async def review_arc(self) -> str:
        """Review the campaign's narrative trajectory and suggest pacing adjustments.

        Returns:
            Arc analysis and pacing recommendations.
        """
        logger.info("Reviewing campaign arc")

        vault_context = self.context.build_campaign_planner_context()

        prompt = f"""## Full Campaign Context
{vault_context}

---

Analyze the campaign's narrative arc so far. Consider:

1. **Pacing** — Is the story moving too fast or too slow? Are there lulls?
2. **Tension Curve** — Are stakes escalating appropriately?
3. **Unresolved Threads** — What plot threads are dangling? Which need attention?
4. **Character Arcs** — Are the PCs' personal stories being advanced?
5. **Balance** — Is there a good mix of combat, roleplay, and exploration?

Provide specific, actionable recommendations for the next 2-3 sessions."""

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=prompt,
                config=genai.types.GenerateContentConfig(
                    system_instruction=CAMPAIGN_PLANNER_IDENTITY,
                    temperature=0.6,
                )
            )
            return f"📊 **Campaign Arc Review**\n\n{response.text}"

        except Exception as e:
            logger.error(f"Arc review failed: {e}", exc_info=True)
            raise

    async def process_request(self, user_input: str) -> str:
        """General planning conversation — for messages routed here by the prep router.

        Args:
            user_input: The DM's planning message.

        Returns:
            Planning response.
        """
        logger.info(f"Planning conversation: {user_input}")

        vault_context = self.context.build_campaign_planner_context()

        prompt = f"""## Campaign Context
{vault_context}

---

## DM's Message
{user_input}

Respond as a strategic planning partner. Be specific and actionable."""

        contents = []
        for entry in self._conversation_history[-10:]:
            contents.append(entry)
        contents.append({"role": "user", "parts": [{"text": prompt}]})

        try:
            response = await self.client.aio.models.generate_content(
                model=self.model_id,
                contents=contents,
                config=genai.types.GenerateContentConfig(
                    system_instruction=CAMPAIGN_PLANNER_IDENTITY,
                    temperature=0.7,
                )
            )

            result = response.text
            self._conversation_history.append({"role": "user", "parts": [{"text": user_input}]})
            self._conversation_history.append({"role": "model", "parts": [{"text": result}]})

            if len(self._conversation_history) > 20:
                self._conversation_history = self._conversation_history[-20:]

            return result

        except Exception as e:
            logger.error(f"Planning conversation failed: {e}", exc_info=True)
            raise

    def clear_conversation(self):
        """Reset the planning conversation history."""
        self._conversation_history.clear()
        logger.info("Campaign Planner conversation history cleared.")
