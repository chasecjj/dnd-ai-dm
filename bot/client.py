"""
D&D AI Dungeon Master — Discord Bot Client

This is the core bot setup, event handling, and message routing.
All !commands live in Cogs (bot/cogs/). The AI pipelines live here
as _handle_game_table() and _handle_war_room().

Replaces the old orchestration/bot.py god file.
"""

import os
import time
import asyncio
import logging
import traceback
from collections import deque
from contextlib import asynccontextmanager


@asynccontextmanager
async def _nullcontext():
    """Async no-op context manager (fallback when no processing lock exists)."""
    yield
import discord
from discord.ext import commands
from dotenv import load_dotenv

from google import genai

# Core utilities
from tools.campaign_manager import CampaignManager
from tools.vault_manager import VaultManager
from tools.context_assembler import ContextAssembler
from tools.reference_manager import ReferenceManager
from tools.rate_limiter import gemini_limiter
from tools.state_manager import StateManager
from tools.action_queue import ActionQueue, QueuedAction
from tools.player_identity import init_player_map, resolve_from_message_author, get_player_map
from tools.turn_collector import TurnCollector, PendingMessage
from tools.dice_roller import parse_and_roll, format_roll_detail
from tools.content_filter import filter_content
from tools.combat_tracker import CombatTracker
from tools.solo_session import SoloSessionManager
from tools.pipeline_metrics import pipeline_metrics
from agents.tools.foundry_tool import FoundryClient

# Agents — Live DM Team
from agents.board_monitor import BoardMonitorAgent
from agents.rules_lawyer import RulesLawyerAgent
from agents.storyteller import StorytellerAgent
from agents.foundry_architect import FoundryArchitectAgent
from agents.message_router import MessageRouterAgent, MessageType
from agents.chronicler import ChroniclerAgent
from agents.player_advisor import PlayerAdvisorAgent


# LangGraph pipeline
from pipeline.graph import build_game_pipeline

# Agents — Prep Team
from agents.world_architect import WorldArchitectAgent
from agents.campaign_planner import CampaignPlannerAgent
from agents.prep_router import PrepRouterAgent, PrepIntent
from agents.cartographer import CartographerAgent

logger = logging.getLogger("DND_Bot")

# ---------------------------------------------------------------------------
# Environment
# ---------------------------------------------------------------------------
load_dotenv()
DISCORD_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODERATOR_LOG_CHANNEL_ID = os.getenv("MODERATOR_LOG_CHANNEL_ID")
WAR_ROOM_CHANNEL_ID = os.getenv("WAR_ROOM_CHANNEL_ID")
GAME_TABLE_CHANNEL_ID = os.getenv("GAME_TABLE_CHANNEL_ID")

# Player-to-Character mapping
DM_DISCORD_USER_ID = os.getenv("DM_DISCORD_USER_ID")

PLAYER_MAP = {}
raw_map = os.getenv("PLAYER_MAP", "")
if raw_map:
    for pair in raw_map.split(","):
        pair = pair.strip()
        if ":" in pair:
            discord_name, char_name = pair.split(":", 1)
            PLAYER_MAP[discord_name.strip().lower()] = char_name.strip()

# Initialize centralized resolver (supports username, global_name, display_name, nick)
init_player_map(PLAYER_MAP)

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
if not os.path.exists("logs"):
    os.makedirs("logs")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.FileHandler("logs/dnd_bot.log", encoding="utf-8"),
        logging.StreamHandler(),
    ],
)

# ---------------------------------------------------------------------------
# Gemini Client
# ---------------------------------------------------------------------------
if not GEMINI_API_KEY:
    print("Error: GEMINI_API_KEY not found in environment.")
    gemini_client = None
else:
    gemini_client = genai.Client(api_key=GEMINI_API_KEY)

MODEL_ID = "gemini-2.5-flash"
MODEL_ID_HEAVY = "gemini-2.5-pro"

# ---------------------------------------------------------------------------
# Campaign Manager & Vault
# ---------------------------------------------------------------------------
campaign_manager = CampaignManager(root_dir=".")
campaign_manager.ensure_migration()

vault = VaultManager(vault_path="campaign_vault")
ref_manager = ReferenceManager()
state_manager = StateManager()  # async connect happens in on_ready
context_assembler = ContextAssembler(vault, reference_manager=ref_manager, state_manager=state_manager)
logger.info(f"ReferenceManager: {ref_manager.get_stats()}")

# ---------------------------------------------------------------------------
# Foundry VTT Connection (async connect happens in on_ready)
# ---------------------------------------------------------------------------
foundry_client = FoundryClient()

# ---------------------------------------------------------------------------
# Action Queue — DM Admin Console state
# ---------------------------------------------------------------------------
action_queue = ActionQueue()

# ---------------------------------------------------------------------------
# Turn Collector — Auto Mode batching window
# ---------------------------------------------------------------------------
turn_collector = TurnCollector(window_seconds=60, expected_players=len(PLAYER_MAP))

# Auto-roll toggle — when True, Auto Mode pre-analyzes actions and rolls dice automatically
auto_roll_enabled: bool = True

# ---------------------------------------------------------------------------
# Combat Tracker — Initiative, rounds, and monster turns
# ---------------------------------------------------------------------------
combat_tracker = CombatTracker()

# ---------------------------------------------------------------------------
# Solo Session Manager — 1-on-1 between-session adventures
# ---------------------------------------------------------------------------
solo_manager = SoloSessionManager()

# ---------------------------------------------------------------------------
# Agents — Live DM Team (Game Table channel)
# ---------------------------------------------------------------------------
board_monitor = BoardMonitorAgent(gemini_client, foundry=foundry_client)
rules_lawyer = RulesLawyerAgent(gemini_client, context_assembler, model_id=MODEL_ID)
storyteller = StorytellerAgent(gemini_client, context_assembler, model_id=MODEL_ID_HEAVY)
foundry_architect = FoundryArchitectAgent(gemini_client, foundry=foundry_client, model_id=MODEL_ID)
message_router = MessageRouterAgent(gemini_client, context_assembler, model_id=MODEL_ID)
chronicler = ChroniclerAgent(gemini_client, vault, context_assembler, model_id=MODEL_ID, storyteller=storyteller)
player_advisor = PlayerAdvisorAgent(gemini_client, context_assembler, vault, model_id=MODEL_ID)

# ---------------------------------------------------------------------------
# Agents — Prep Team (War Room channel)
# ---------------------------------------------------------------------------
world_architect = WorldArchitectAgent(gemini_client, vault, context_assembler, model_id=MODEL_ID)
campaign_planner = CampaignPlannerAgent(gemini_client, vault, context_assembler, model_id=MODEL_ID)
prep_router = PrepRouterAgent(gemini_client, context_assembler, model_id=MODEL_ID)
cartographer_agent = CartographerAgent(
    gemini_client,
    foundry=foundry_client,
    vault=vault,
    model_id=MODEL_ID,
    output_dir=os.path.join(vault.vault_path, "Assets", "Maps"),
)

# Set the starting location from the world clock / vault
_world_clock = vault.read_world_clock()
_start_location = _world_clock.get("current_location", "The Yawning Portal") if _world_clock else "The Yawning Portal"
storyteller.set_location(_start_location)
logger.info(f"Starting location: {_start_location}")

# ---------------------------------------------------------------------------
# LangGraph Pipeline — replaces the imperative if/else chain
# ---------------------------------------------------------------------------
game_pipeline = build_game_pipeline({
    "message_router": message_router,
    "board_monitor": board_monitor,
    "rules_lawyer": rules_lawyer,
    "storyteller": storyteller,
    "chronicler": chronicler,
    "context_assembler": context_assembler,
    "gemini_client": gemini_client,
    "model_id": MODEL_ID,
    "vault_manager": vault,
    "state_manager": state_manager,
    "foundry_client": foundry_client,
})
logger.info("LangGraph game pipeline built and compiled.")

# Track current session number
current_session = context_assembler.current_session

# Restore conversation memory from last checkpoint
context_assembler.load_checkpoint()
logger.info("Memory checkpoint loaded.")

# ---------------------------------------------------------------------------
# Discord Bot Instance
# ---------------------------------------------------------------------------
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents, help_command=None)

# ---------------------------------------------------------------------------
# Reliability: Message deduplication & pipeline serialization
# ---------------------------------------------------------------------------
_seen_messages: deque = deque(maxlen=1000)  # Bounded deque of recent message IDs
_pipeline_semaphore = asyncio.Semaphore(1)  # Serialize pipeline invocations


# ---------------------------------------------------------------------------
# Moderator Log Helper
# ---------------------------------------------------------------------------
async def send_to_moderator_log(content: str):
    """Send a message to the moderator log channel."""
    if not MODERATOR_LOG_CHANNEL_ID:
        logger.warning("MODERATOR_LOG_CHANNEL_ID not set — logging error locally only.")
        logger.error(content)
        return
    try:
        channel = bot.get_channel(int(MODERATOR_LOG_CHANNEL_ID))
        if channel is None:
            logger.warning(f"Could not find moderator log channel {MODERATOR_LOG_CHANNEL_ID}")
            logger.error(content)
            return
        for i in range(0, len(content), 1900):
            chunk = str(content)[i : i + 1900]
            await channel.send(f"```\n{chunk}\n```")
    except Exception as e:
        logger.error(f"Failed to send to moderator log: {e}")
        logger.error(content)


# ---------------------------------------------------------------------------
# Attach shared services to bot so cogs can access them via self.bot
# ---------------------------------------------------------------------------
bot.campaign_manager = campaign_manager
bot.vault = vault
bot.context_assembler = context_assembler
bot.state_manager = state_manager
bot.ref_manager = ref_manager
bot.foundry_client = foundry_client
bot.foundry_architect = foundry_architect
bot.gemini_client = gemini_client
bot.model_id = MODEL_ID
bot.storyteller = storyteller
bot.world_architect = world_architect
bot.campaign_planner = campaign_planner
bot.cartographer_agent = cartographer_agent
bot.send_to_moderator_log = send_to_moderator_log
bot.war_room_channel_id = WAR_ROOM_CHANNEL_ID
bot.resolve_character = resolve_from_message_author
bot.turn_collector = turn_collector
bot.action_queue = action_queue
bot.auto_roll_enabled = auto_roll_enabled
bot.player_advisor = player_advisor
bot.solo_manager = solo_manager
bot.pipeline_metrics = pipeline_metrics


# ---------------------------------------------------------------------------
# Scene Sync Helpers
# ---------------------------------------------------------------------------
def _build_architect_request(scene_changes: dict, narrative: str) -> str:
    """Translate scene classifier output into a natural-language FoundryArchitect request."""
    parts = []
    if scene_changes.get("combat_started"):
        monsters = scene_changes.get("monsters_introduced", [])
        if monsters:
            parts.append(f"Start a combat encounter with: {', '.join(monsters)}")
        else:
            parts.append("Start a combat encounter with the enemies described")
    if scene_changes.get("location_changed") and scene_changes.get("new_location"):
        parts.append(f"Scene change to: {scene_changes['new_location']}")
    if scene_changes.get("lighting_change") is not None:
        parts.append(f"Set scene darkness level to {scene_changes['lighting_change']}")
    if scene_changes.get("combat_ended"):
        parts.append("End the current combat encounter")
    if not parts:
        return ""
    request = ". ".join(parts)
    request += f"\n\nNarrative context: {str(narrative)[:500]}"
    return request


async def _run_architect_safe(request: str, channel):
    """Run FoundryArchitect in background with error handling."""
    status_msg = None
    try:
        status_msg = await channel.send("🗺️ *Updating the scene...*")
        await gemini_limiter.acquire()
        result = await foundry_architect.process_request(request)
        logger.info(f"FoundryArchitect result: {result}")
        if status_msg:
            try:
                await status_msg.edit(content="🗺️ *Scene updated!*")
            except Exception:
                pass
    except Exception as e:
        logger.error(f"FoundryArchitect background error: {e}", exc_info=True)
        if status_msg:
            try:
                await status_msg.edit(content="🗺️ *Scene update skipped — Foundry error logged.*")
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Game Table Pipeline — Driven by LangGraph
# ---------------------------------------------------------------------------
async def _handle_game_table(message, user_input: str):
    """Handle messages in the Game Table channel via the LangGraph pipeline.

    Flow: router → board_monitor → rules → storyteller → scene_sync → chronicler
    All agent calls happen inside LangGraph nodes. This function only handles
    Discord I/O (delivery, Foundry dispatch) after the pipeline finishes.
    """
    logger.info(
        f"[Game Table] {message.author}: {user_input} "
        f"(channel={message.channel.id}, is_thread={isinstance(message.channel, discord.Thread)})"
    )

    # Content filter — blocklist check before pipeline entry
    user_input, was_filtered = filter_content(user_input)
    if was_filtered:
        await send_to_moderator_log(
            f"[Content Filter] Filtered input from {message.author}:\n"
            f"Original: {message.content[:200]}"
        )

    # Resolve player identity (tries username, global_name, display_name, nick)
    character_name = resolve_from_message_author(message.author)
    if character_name:
        user_input = f"[{character_name}]: {user_input}"
        logger.info(f"Player identified: {message.author.name} -> {character_name}")

    # Track player action in combat
    if combat_tracker.in_combat and character_name:
        combat_tracker.record_player_action(character_name)

    # If in combat and monsters don't go first, append monster turn to player batch
    if combat_tracker.in_combat and not combat_tracker.monsters_go_first():
        user_input += combat_tracker.get_monster_turn_prompt()

    # Auto-roll dice if enabled (pre-analyze + roll before pipeline)
    dice_results = None
    if auto_roll_enabled and character_name:
        try:
            dice_results, roll_summary = await _auto_roll_for_actions(
                [(character_name, user_input)]
            )
            if roll_summary:
                await message.channel.send(f"\U0001f3b2 {' | '.join(roll_summary)}")
        except Exception as e:
            logger.warning(f"Auto-roll failed, continuing without dice: {e}")

    # Build the initial state and invoke the pipeline
    # Use per-character location if available, fall back to global
    current_loc = (
        storyteller.get_character_location(character_name)
        if character_name
        else storyteller._current_location
    )
    initial_state = {
        "player_input": user_input,
        "character_name": character_name,
        "session": current_session,
        "current_location": current_loc,
        "dice_results": dice_results,
    }

    # Pipeline invocation with single retry on failure
    result = None
    _pipeline_start = time.monotonic()
    for _attempt in range(2):
        try:
            async with _pipeline_semaphore:
                async with message.channel.typing():
                    result = await game_pipeline.ainvoke(initial_state)
            pipeline_metrics.record_request(
                time.monotonic() - _pipeline_start, is_solo=False, success=True
            )
            break  # Success
        except Exception as pipeline_err:
            if _attempt == 0:
                logger.warning(f"Pipeline attempt 1 failed, retrying: {pipeline_err}")
                await asyncio.sleep(1)
            else:
                pipeline_metrics.record_request(
                    time.monotonic() - _pipeline_start, is_solo=False,
                    success=False, error_type="pipeline_error",
                )
                logger.error(f"Pipeline failed after retry: {pipeline_err}", exc_info=True)
                await send_to_moderator_log(
                    f"[Game Table] Pipeline failed after retry for {message.author}:\n"
                    f"Input: {user_input[:200]}\n{traceback.format_exc()}"
                )
                await message.channel.send(
                    "*The DM pauses to collect their thoughts... "
                    "(Something went wrong behind the screen. Try again in a moment!)*"
                )
                return

    if result is None:
        return

    logger.info(f"Pipeline complete. Keys returned: {list(result.keys())}")

    # --- Discord I/O after pipeline ---
    try:
        # Direct response (out-of-game question answered by router)
        if result.get("direct_reply"):
            reply = result["direct_reply"]
            if len(reply) > 2000:
                for i in range(0, len(reply), 2000):
                    await message.channel.send(reply[i : i + 2000])
            else:
                await message.channel.send(reply)
            return

        # Casual chat — the router already decided to stop
        if result.get("message_type") == "casual_chat":
            logger.info("Casual chat detected — ignoring.")
            return

        # Narrative delivery
        narrative = result.get("narrative", "")
        if not narrative and not result.get("direct_reply") and result.get("message_type") != "casual_chat":
            narrative = "*The threads of fate tangle momentarily... (The DM fumbles with their notes. Try again!)*"
            logger.warning(f"Empty narrative returned for input: {user_input[:100]}")

        if narrative:
            await _send_chunked(message.channel, narrative)

            # Fire post-turn story hook (non-blocking)
            _ambient = bot.get_cog("Ambient")
            if _ambient:
                asyncio.create_task(_ambient.post_story_hook(message.channel, narrative))

        # Foundry VTT dispatch (runs AFTER delivery, non-blocking)
        scene_changes = result.get("scene_changes")
        if scene_changes and scene_changes.get("foundry_actions_needed"):
            if foundry_client.is_connected:
                architect_request = _build_architect_request(scene_changes, narrative)
                if architect_request:
                    asyncio.create_task(_run_architect_safe(architect_request, message.channel))
                    logger.info(f"FoundryArchitect dispatched: {str(architect_request)[:100]}...")
            else:
                logger.info("Scene change detected but Foundry not connected — skipping.")

        # --- Combat tracking: detect start/end from scene changes ---
        scene_changes_dict = result.get("scene_changes") or {}
        if scene_changes_dict.get("combat_started") and not combat_tracker.in_combat:
            party = vault.get_party_state()
            monsters_desc = ", ".join(scene_changes_dict.get("monsters_introduced", [])) or "enemies"
            init_order = combat_tracker.start_combat(party, monsters_desc)
            await message.channel.send(f"\u2694\ufe0f {init_order}")

            if combat_tracker.monsters_go_first():
                await _generate_monster_turn(message.channel)

        if scene_changes_dict.get("combat_ended") and combat_tracker.in_combat:
            end_msg = combat_tracker.end_combat()
            await message.channel.send(end_msg)

        # Advance combat round if all players acted
        if combat_tracker.in_combat and combat_tracker.all_players_acted():
            round_header = combat_tracker.advance_round()
            await message.channel.send(round_header)

            if combat_tracker.monsters_go_first():
                await _generate_monster_turn(message.channel)

        # Error surfacing (pipeline nodes log their own errors, but surface fatal ones)
        if result.get("error"):
            logger.error(f"Pipeline returned error: {result['error']}")

    except Exception as e:
        logger.error(f"Error delivering response: {e}", exc_info=True)
        await send_to_moderator_log(
            f"[on_message] Delivery error for {message.author}:\n"
            f"Content: {user_input[:200]}\n{traceback.format_exc()}"
        )


# ---------------------------------------------------------------------------
# Message Chunking Utility
# ---------------------------------------------------------------------------
async def _send_chunked(channel, text: str, limit: int = 1990):
    """Send text in chunks that respect word/line boundaries."""
    while len(text) > limit:
        # Prefer splitting at a newline, then a space
        split_at = text.rfind('\n', 0, limit)
        if split_at == -1:
            split_at = text.rfind(' ', 0, limit)
        if split_at == -1:
            split_at = limit  # No good break point, hard split
        await channel.send(text[:split_at])
        text = text[split_at:].lstrip()
    if text:
        await channel.send(text)


# ---------------------------------------------------------------------------
# Solo Session Pipeline Handler
# ---------------------------------------------------------------------------
async def _handle_solo_message(message, user_input: str):
    """Handle messages in a solo adventure thread.

    Reuses the game_pipeline but with solo-specific context:
    - Per-session history isolation (Phase 0.1)
    - Processing lock prevents concurrent corruption (Phase 0.2)
    - Oracle grading for graduated outcomes (Phase 1.3)
    - Chaos factor tension escalation (Phase 2.1)
    - Thread/NPC/faction post-processing (Phase 2.2-3.1)
    - Narrative directive coordination (Phase 2.4)
    """
    session = solo_manager.get_session(message.channel.id)
    if not session:
        return

    # Acquire per-session processing lock (Phase 0.2)
    processing_lock = solo_manager.get_processing_lock(message.channel.id)
    if processing_lock and processing_lock.locked():
        await message.channel.send(
            "*One moment — still weaving the threads of your last action...*"
        )
        return

    character_name = session.character_name
    logger.info(f"[Solo] {character_name}: {user_input}")

    async with processing_lock if processing_lock else _nullcontext():
        # Content filter
        user_input, was_filtered = filter_content(user_input)
        if was_filtered:
            await send_to_moderator_log(
                f"[Solo Filter] Filtered input from {message.author}: {message.content[:200]}"
            )

        # Get per-session history (Phase 0.1)
        session_history = solo_manager.get_history(message.channel.id)

        # --- Solo Inquiry Mode Detection ---
        # Hybrid trigger: explicit "DM:" prefix (deterministic, zero API cost)
        # + LLM classification fallback for untagged questions.
        is_inquiry = False
        inquiry_input = user_input
        dm_prefixes = ("dm:", "for the dm:", "dm,")
        lower_input = user_input.lower().strip()
        for prefix in dm_prefixes:
            if lower_input.startswith(prefix):
                is_inquiry = True
                inquiry_input = user_input[len(prefix):].strip()
                break

        # LLM fallback — classify untagged messages
        if not is_inquiry:
            try:
                await gemini_limiter.acquire()
                route = await message_router.route(user_input)
                if route.message_type in (MessageType.GAME_QUESTION, MessageType.OUT_OF_GAME):
                    is_inquiry = True
                    inquiry_msg_type = route.message_type
                else:
                    inquiry_msg_type = None
            except Exception as classify_err:
                logger.warning(f"Solo inquiry classification failed: {classify_err}")
                inquiry_msg_type = None
        else:
            # Explicit prefix — classify as game_question by default
            inquiry_msg_type = MessageType.GAME_QUESTION

        # --- Handle inquiry: no snapshot, no dice, no turn advance ---
        if is_inquiry:
            logger.info(f"[Solo Inquiry] {character_name}: {inquiry_input}")
            try:
                if inquiry_msg_type == MessageType.OUT_OF_GAME:
                    # Out-of-game meta question — use direct response handler
                    await gemini_limiter.acquire()
                    response_text = await message_router.generate_direct_response(inquiry_input)
                else:
                    # In-game question — direct LLM call, bypasses pipeline
                    # so no router reclassification, no chronicler, no story
                    # progression. Just an answer using vault context.
                    async with message.channel.typing():
                        response_text = await storyteller.answer_inquiry(
                            question=inquiry_input,
                            character_name=character_name,
                            location=session.current_location,
                            solo_history=session_history,
                        )

                if not response_text:
                    response_text = "The answer eludes you for now..."

                # Format as inquiry response (italic with bookmark emoji)
                formatted = f"\U0001f4d6 *{response_text.strip('*').strip()}*"
                await _send_chunked(message.channel, formatted)

                # Lightweight history entry so the DM remembers what was asked
                if session_history:
                    session_history.add_event(
                        f"[Inquiry] {inquiry_input} → {response_text[:200]}",
                        impact=3,
                        character=character_name,
                        location=session.current_location,
                        age_existing=False,
                    )
                session.touch()
            except Exception as inquiry_err:
                logger.error(f"Solo inquiry error: {inquiry_err}", exc_info=True)
                await message.channel.send(
                    "*The DM flips through their notes but can't find the answer right now...*"
                )
            return  # Don't advance the turn

        # --- Full turn flow (action/narrative) ---
        # Snapshot current state for undo (uses per-session history)
        history_snapshot = [
            {
                "text": e.text,
                "base_impact": e.base_impact,
                "turns_ago": e.turns_ago,
                "timestamp": e.timestamp,
                "character": e.character,
                "location": e.location,
            }
            for e in (session_history.entries if session_history else [])
        ]

        from tools.solo_session import SoloTurnSnapshot

        turn_number = session.turn_count
        session.push_snapshot(SoloTurnSnapshot(
            turn_number=turn_number,
            history_snapshot=history_snapshot,
            location_before=session.current_location,
            player_input=user_input,
            recent_narratives_snapshot=list(session.recent_narratives),
            scene_state_snapshot=dict(session.scene_state_data),
        ))

        # Auto-roll dice
        dice_results = None
        if auto_roll_enabled:
            try:
                dice_results, roll_summary = await _auto_roll_for_actions(
                    [(character_name, f"[{character_name}]: {user_input}")]
                )
                if roll_summary:
                    await message.channel.send(f"\U0001f3b2 {' | '.join(roll_summary)}")
            except Exception as e:
                logger.warning(f"Solo auto-roll failed: {e}")

        # Build initial state
        initial_state = {
            "player_input": f"[{character_name}]: {user_input}",
            "character_name": character_name,
            "session": session.session_number,
            "current_location": session.current_location,
            "dice_results": dice_results,
            "is_solo": True,
            "_solo_thread_id": message.channel.id,
        }

        # Pipeline invocation with retry
        result = None
        _pipeline_start = time.monotonic()
        for _attempt in range(2):
            try:
                async with _pipeline_semaphore:
                    async with message.channel.typing():
                        result = await game_pipeline.ainvoke(initial_state)
                pipeline_metrics.record_request(
                    time.monotonic() - _pipeline_start, is_solo=True, success=True
                )
                break
            except Exception as pipeline_err:
                if _attempt == 0:
                    logger.warning(f"Solo pipeline attempt 1 failed: {pipeline_err}")
                    await asyncio.sleep(1)
                else:
                    pipeline_metrics.record_request(
                        time.monotonic() - _pipeline_start, is_solo=True,
                        success=False, error_type="pipeline_error",
                    )
                    logger.error(f"Solo pipeline failed after retry: {pipeline_err}", exc_info=True)
                    await message.channel.send(
                        "*The threads of fate tangle momentarily... Try again in a moment!*"
                    )
                    return

        if result is None:
            return

        # Deliver narrative
        narrative = result.get("narrative", "")
        if not narrative:
            narrative = "*The moment passes quietly...*"

        await _send_chunked(message.channel, narrative)

        # Store narrative in snapshot for undo reference
        if session.last_snapshot:
            session.last_snapshot.narrative = narrative

        # Record exchange in per-session history for continuity
        if session_history:
            # Player action
            session_history.add_event(
                f"[Player] {user_input}",
                impact=5,
                character=character_name,
                location=session.current_location,
                age_existing=True,
            )
            # DM narrative (higher impact — this is what needs to persist)
            session_history.add_event(
                narrative[:500],
                impact=7,
                character=character_name,
                location=session.current_location,
                age_existing=False,
            )

        # Store full narrative in sliding window for continuity (Phase 2)
        session.push_narrative(turn_number, user_input, narrative)

        # Update session state
        await solo_manager.increment_turn(message.channel.id)

        # Track location changes from scene_changes
        scene_changes = result.get("scene_changes") or {}
        if scene_changes.get("location_changed") and scene_changes.get("new_location"):
            session.current_location = scene_changes["new_location"]
            storyteller.set_character_location(character_name, session.current_location)

        # Log turn to vault
        vault.append_to_solo_log(
            character_name=character_name,
            session_number=session.session_number,
            turn_number=turn_number,
            player_input=user_input,
            narrative=narrative,
            log_path=getattr(session, 'solo_log_path', None),
        )

        # --- Solo post-processing (Phases 2.1-3.1) ---
        await _solo_post_process(session, result, turn_number)

        if result.get("error"):
            logger.error(f"Solo pipeline error: {result['error']}")


async def _solo_post_process(session, pipeline_result: dict, turn_number: int):
    """Post-process pipeline results for solo-specific tracking.

    Updates chaos factor, extracts threads and NPCs from chronicler output,
    and adjusts session state. Non-blocking — errors are logged and swallowed.
    """
    try:
        from tools.solo_engine import ChaosTracker
        from tools.solo_world import (
            ThreadTracker, SoloNPCRegistry, FactionTracker,
            extract_threads_from_chronicler, extract_npcs_from_chronicler,
        )

        # Rebuild trackers from session state
        chaos = ChaosTracker(factor=session.chaos_factor)
        threads = ThreadTracker.from_list(session.active_threads)
        npcs = SoloNPCRegistry.from_list(session.encountered_npcs)
        factions = FactionTracker.from_list(session.factions)

        # Use actual chronicler output for assessment (populated by chronicler node)
        chronicler_data = pipeline_result.get("_chronicler_output") or {}
        # Also include scene_changes which flow separately through the pipeline
        if "scene_changes" not in chronicler_data:
            chronicler_data["scene_changes"] = pipeline_result.get("scene_changes") or {}

        # Chaos assessment — adjust factor based on what happened
        direction = chaos.assess_chronicler_output(chronicler_data)
        if direction != "none":
            chaos.adjust(direction)

        # Thread extraction — heuristic scan of narrative + chronicler output
        narrative = pipeline_result.get("narrative", "")
        thread_candidates = extract_threads_from_chronicler(
            chronicler_data, narrative, turn_number
        )
        for candidate in thread_candidates:
            threads.add_thread(candidate["title"], turn_number, candidate.get("priority", 5))
        threads.check_dormancy(turn_number)

        # NPC extraction from chronicler output
        npc_data = extract_npcs_from_chronicler(chronicler_data, turn_number)
        for npc in npc_data:
            npcs.register(
                name=npc["name"], turn=turn_number,
                disposition=npc.get("disposition", "neutral"),
                location=npc.get("location", ""),
                motivation=npc.get("motivation", ""),
            )

        # Faction tick
        factions.tick(turn_number)

        # Consequence tracking — scan narrative for consequence-related content
        # (prompt-first: consequences are managed by the LLM, we just track them)

        # Extract and store scene state from chronicler output (Phase 3)
        scene_state = chronicler_data.get("scene_state")
        if scene_state and isinstance(scene_state, dict):
            session.scene_state_data = scene_state

        # Write updated state back to session
        session.chaos_factor = chaos.factor
        session.active_threads = threads.to_list()
        session.encountered_npcs = npcs.to_list()
        session.factions = factions.to_list()

    except Exception as e:
        logger.warning(f"Solo post-processing error (non-blocking): {e}")


async def _solo_session_timeout_checker():
    """Background task: auto-end solo sessions idle >2 hours (Phase 3.2b).

    Runs every 30 minutes. Logs timeout to vault and moderator log.
    """
    await bot.wait_until_ready()
    while not bot.is_closed():
        try:
            timed_out = solo_manager.get_timed_out_sessions()
            for session in timed_out:
                logger.info(
                    f"Solo session timeout: {session.character_name} "
                    f"(thread={session.thread_id}, idle since {session.last_activity})"
                )
                # Log timeout in vault
                vault.append_to_solo_log(
                    character_name=session.character_name,
                    session_number=session.session_number,
                    turn_number=session.turn_count + 1,
                    player_input="[Session Timeout]",
                    narrative="*The adventure fades as the hero's attention wanders elsewhere...*",
                    log_path=getattr(session, 'solo_log_path', None),
                )
                # End the session
                await solo_manager.end_session(session.thread_id)
                # Notify moderator log
                try:
                    await send_to_moderator_log(
                        f"[Solo] {session.character_name}'s solo session auto-ended "
                        f"(timeout after {solo_manager.SESSION_TIMEOUT_HOURS}h idle, "
                        f"{session.turn_count} turns)"
                    )
                except Exception:
                    pass
        except Exception as e:
            logger.warning(f"Solo timeout checker error: {e}")

        await asyncio.sleep(1800)  # Check every 30 minutes


# ---------------------------------------------------------------------------
# Monster Turn Generator — Standalone enemy action when monsters go first
# ---------------------------------------------------------------------------
async def _generate_monster_turn(channel):
    """Generate a standalone monster turn via the Storyteller.

    Called when enemies have higher initiative and act before players.
    Sends the monster turn narrative directly to the channel.
    """
    if not combat_tracker.in_combat:
        return

    prompt = combat_tracker.get_monster_first_prompt()
    vault_context = context_assembler.build_storyteller_context(
        storyteller._current_location,
        new_locations=set(),
    )

    full_prompt = f"""## Current World State (from vault)
{vault_context}

---

## This Turn
**Monster Turn (enemies act first — higher initiative)**
{prompt}

Narrate the enemies' actions seamlessly. Do NOT include any headings or meta-text."""

    try:
        from agents.storyteller import STORYTELLER_IDENTITY
        from google import genai as _genai
        await gemini_limiter.acquire()
        async with channel.typing():
            response = await gemini_client.aio.models.generate_content(
                model=MODEL_ID,
                contents=full_prompt,
                config=_genai.types.GenerateContentConfig(
                    system_instruction=STORYTELLER_IDENTITY,
                    temperature=0.8,
                ),
            )
            narrative = response.text if response.text else ""

        if narrative:
            await _send_chunked(channel, narrative)
            # Record to history
            context_assembler.history.add_event(
                text=f"[Monster turn] {combat_tracker.monsters_desc} acted (round {combat_tracker.current_round}).",
                impact=5,
            )
            logger.info(f"Monster-first turn generated (round {combat_tracker.current_round})")
    except Exception as e:
        logger.error(f"Monster turn generation failed: {e}", exc_info=True)


# ---------------------------------------------------------------------------
# Batch Resolve — Called by the DM Admin Console's Resolve Turn button
# ---------------------------------------------------------------------------
async def _send_chunked(channel, text: str):
    """Send a long message in 2000-char chunks."""
    if len(text) <= 2000:
        await channel.send(text)
    else:
        for i in range(0, len(text), 2000):
            await channel.send(text[i : i + 2000])


async def _auto_roll_for_actions(actions_list):
    """Pre-analyze actions and auto-roll dice for Auto Mode.

    Args:
        actions_list: List of (character_name, user_input) tuples.

    Returns:
        (dice_results, summary_lines) — dice_results dict for pipeline state,
        summary_lines list for posting to channel. Both may be empty.
    """
    dice_results = {}
    summary_lines = []

    for char_name, user_input in actions_list:
        if not char_name:
            continue

        try:
            await gemini_limiter.acquire()
            pre_analysis = await rules_lawyer.pre_analyze(user_input, char_name)

            has_player_rolls = pre_analysis.get("rolls")
            has_target_saves = pre_analysis.get("target_saves")

            if not pre_analysis.get("needs_roll") or (not has_player_rolls and not has_target_saves):
                continue

            char_rolls = []
            char_summary_parts = []

            # --- Player rolls (ability checks, attacks, damage) ---
            for roll_spec in (pre_analysis.get("rolls") or []):
                roll_type = roll_spec.get("roll_type", "Check")
                formula = roll_spec.get("formula", "1d20")
                dc = roll_spec.get("dc")

                # Roll via Foundry if connected, else Python fallback
                if foundry_client.is_connected:
                    try:
                        result = await foundry_client.roll_dice(formula)
                    except Exception as e:
                        logger.warning(f"Foundry roll failed, using fallback: {e}")
                        result = parse_and_roll(formula)
                else:
                    result = parse_and_roll(formula)

                total = result["total"]
                detail = format_roll_detail(formula, result)
                is_crit = result.get("isCritical", False)
                is_fumble = result.get("isFumble", False)

                char_rolls.append({
                    "type": roll_type,
                    "result": total,
                    "dc": dc,
                })

                # Build display string
                crit_tag = " **NAT 20!**" if is_crit else (" **NAT 1!**" if is_fumble else "")
                dc_tag = ""
                if dc and isinstance(total, int):
                    passed = total >= dc
                    dc_tag = f" (DC {dc} {'✓' if passed else '✗'})"
                char_summary_parts.append(
                    f"{roll_type} `{formula}` = **{total}**{crit_tag}{dc_tag}"
                )

            # --- Target saves (monster/NPC rolls against player spell DC) ---
            for save_spec in (pre_analysis.get("target_saves") or []):
                save_type = save_spec.get("save_type", "Save")
                dc = save_spec.get("dc")
                reason = save_spec.get("reason", "")

                # Roll 1d20 for the target (no modifier — AI adjudicates contextually)
                result = parse_and_roll("1d20")
                total = result["total"]

                char_rolls.append({
                    "type": f"Target {save_type} Save",
                    "result": total,
                    "dc": dc,
                    "is_target_save": True,
                })

                # Build display string
                dc_tag = ""
                if dc and isinstance(total, int):
                    passed = total >= dc
                    dc_tag = f" DC {dc} {'✓' if passed else '✗'}"
                char_summary_parts.append(
                    f"Target {save_type} Save `1d20` = **{total}** ({dc_tag})" if dc_tag
                    else f"Target {save_type} Save `1d20` = **{total}**"
                )

            if char_rolls:
                dice_results[char_name] = {"rolls": char_rolls}
                summary_lines.append(f"**{char_name}**: {', '.join(char_summary_parts)}")

        except Exception as e:
            logger.error(f"Auto-roll failed for {char_name}: {e}", exc_info=True)

    return (dice_results if dice_results else None, summary_lines)


async def handle_batch_resolve(actions, game_table_channel):
    """Process a batch of curated actions through the pipeline.

    Called by AdminConsoleView.resolve_turn(). Accepts a list of QueuedAction
    objects that the DM has reviewed and approved.
    """
    from tools.action_queue import QueuedAction

    # Build combined input — one line per action with all context
    combined_parts = []
    dice_results = {}
    dm_context_parts = []

    for action in actions:
        prefix = f"[{action.character_name}]" if action.character_name else "[DM]"
        line = f"{prefix}: {action.player_input}"
        if action.resolved_rolls and action.character_name:
            roll_strs = []
            roll_data = []
            for roll in action.resolved_rolls:
                dc_str = f" vs DC {roll.dc}" if roll.dc else ""
                roll_strs.append(f"{roll.roll_type} {roll.detail}{dc_str}")
                roll_data.append({
                    "type": roll.roll_type,
                    "result": roll.result,
                    "dc": roll.dc,
                })
            line += f" [Rolls: {'; '.join(roll_strs)}]"
            dice_results[action.character_name] = {"rolls": roll_data}
        if action.dm_annotation:
            line += f" {{DM Note: {action.dm_annotation}}}"
            dm_context_parts.append(action.dm_annotation)
        combined_parts.append(line)

    # Include monster/NPC rolls in the batch context
    monster_rolls = await action_queue.flush_monster_rolls()
    for mr in monster_rolls:
        target_str = f" targeting {mr.target}" if mr.target else ""
        combined_parts.append(
            f"[{mr.monster_name}]: {mr.roll_type}{target_str} "
            f"[Roll: {mr.roll_type} {mr.detail}]"
        )
        dice_results[mr.monster_name] = {
            "rolls": [{"type": mr.roll_type, "result": mr.result, "dc": None}]
        }

    batched_input = "\n".join(combined_parts)
    is_batched = len(actions) > 1 or len(monster_rolls) > 0

    initial_state = {
        "player_input": batched_input,
        "character_name": actions[0].character_name if len(actions) == 1 and not monster_rolls else None,
        "session": current_session,
        "current_location": storyteller._current_location,
        "dm_context": "\n".join(dm_context_parts) if dm_context_parts else None,
        "dice_results": dice_results if dice_results else None,
        "is_batched": is_batched,
    }

    try:
        async with _pipeline_semaphore:
            async with game_table_channel.typing():
                result = await game_pipeline.ainvoke(initial_state)

        logger.info(f"Batch resolve complete. Keys: {list(result.keys())}")

        # Separate secret vs public actions
        secret_actions = [a for a in actions if a.is_secret]
        has_public = any(not a.is_secret for a in actions)

        # Deliver narrative
        narrative = result.get("narrative", "")
        if narrative:
            # Public narrative goes to game table
            if has_public:
                await _send_chunked(game_table_channel, narrative)

            # Secret action results go to each player's private thread
            for action in secret_actions:
                if action.private_thread_id:
                    try:
                        guild = game_table_channel.guild
                        thread = guild.get_thread(action.private_thread_id)
                        if thread:
                            secret_note = (
                                f"**[Secret Result for {action.character_name}]**\n"
                                f"_{action.player_input}_\n\n{narrative}"
                            )
                            await _send_chunked(thread, secret_note)
                    except Exception as e:
                        logger.error(f"Failed to send secret result: {e}")

            # Fire post-turn story hook (non-blocking)
            _ambient = bot.get_cog("Ambient")
            if _ambient and has_public:
                asyncio.create_task(_ambient.post_story_hook(game_table_channel, narrative))

        # Direct reply fallback
        if result.get("direct_reply"):
            await _send_chunked(game_table_channel, result["direct_reply"])

        # Scene sync (same as _handle_game_table)
        scene_changes = result.get("scene_changes")
        if scene_changes and scene_changes.get("foundry_actions_needed"):
            if foundry_client.is_connected:
                architect_request = _build_architect_request(scene_changes, narrative)
                if architect_request:
                    asyncio.create_task(_run_architect_safe(architect_request, game_table_channel))

        if result.get("error"):
            logger.error(f"Batch resolve pipeline error: {result['error']}")

        # Advance conversation history decay once per resolve (not per message)
        context_assembler.history.advance_turn()

        # Pipeline succeeded — clear the backup so restore_batch() is a no-op
        await action_queue.confirm_batch()

        # Post sync report to DM console
        sync_report = result.get("sync_report")
        if sync_report:
            admin_cog = bot.get_cog("Admin Console")
            if admin_cog:
                await admin_cog.post_sync_report(sync_report)

    except Exception as e:
        logger.error(f"Batch resolve error: {e}", exc_info=True)
        await send_to_moderator_log(f"[batch_resolve] Error:\n{traceback.format_exc()}")
        await game_table_channel.send(
            "\u26a0\ufe0f Something went wrong resolving the turn. The DM has been notified."
        )
        # Restore flushed actions back to queue so the DM can retry
        restored = await action_queue.restore_batch()
        if restored:
            logger.info(f"Restored {restored} actions to queue after pipeline failure")
            admin_cog = bot.get_cog("Admin Console")
            if admin_cog:
                await admin_cog.refresh_console()


# ---------------------------------------------------------------------------
# Auto-Batch Resolve — TurnCollector callback for Auto Mode
# ---------------------------------------------------------------------------
async def _resolve_auto_batch(pending_messages: list):
    """Resolve a batch of collected Auto Mode messages through the pipeline.

    Called by TurnCollector when the collection window expires.
    Similar to handle_batch_resolve() but without DM annotations or Foundry dispatch.
    """
    if not pending_messages:
        return

    game_table_channel = None

    # Find the game table channel from any pending message
    for pm in pending_messages:
        if hasattr(pm.message, "channel"):
            game_table_channel = pm.message.channel
            break

    if game_table_channel is None:
        logger.error("Auto-batch resolve: no channel found in pending messages")
        return

    # Clean up the status message
    if turn_collector.status_message:
        try:
            await turn_collector.status_message.delete()
        except Exception:
            pass
        turn_collector.status_message = None

    # Single message — just run the normal pipeline path
    if len(pending_messages) == 1:
        pm = pending_messages[0]
        await _handle_game_table(pm.message, pm.user_input)
        return

    # Multiple messages — build a batched pipeline call
    combined_parts = []
    for pm in pending_messages:
        prefix = f"[{pm.character_name}]" if pm.character_name else "[Unknown]"
        combined_parts.append(f"{prefix}: {pm.user_input}")

        # Track player actions in combat
        if combat_tracker.in_combat and pm.character_name:
            combat_tracker.record_player_action(pm.character_name)

    batched_input = "\n".join(combined_parts)

    # If in combat and monsters DON'T go first, append monster turn to player batch
    # (If monsters go first, their turn was already generated at round start)
    if combat_tracker.in_combat and not combat_tracker.monsters_go_first():
        batched_input += combat_tracker.get_monster_turn_prompt()

    logger.info(f"Auto-batch resolving {len(pending_messages)} messages:\n{batched_input}")

    # Auto-roll dice for all actions in the batch
    dice_results = None
    if auto_roll_enabled:
        actions_for_roll = [
            (pm.character_name, pm.user_input)
            for pm in pending_messages
            if pm.character_name
        ]
        if actions_for_roll:
            dice_results, roll_summary = await _auto_roll_for_actions(actions_for_roll)
            if roll_summary:
                await game_table_channel.send(f"\U0001f3b2 {' | '.join(roll_summary)}")

    initial_state = {
        "player_input": batched_input,
        "character_name": None,  # Multi-character batch
        "session": current_session,
        "current_location": storyteller._current_location,
        "is_batched": True,
        "dice_results": dice_results,
    }

    try:
        async with _pipeline_semaphore:
            async with game_table_channel.typing():
                result = await game_pipeline.ainvoke(initial_state)

        logger.info(f"Auto-batch resolve complete. Keys: {list(result.keys())}")

        # Direct response fallback
        if result.get("direct_reply"):
            await _send_chunked(game_table_channel, result["direct_reply"])
            return

        # Narrative delivery
        narrative = result.get("narrative", "")
        if narrative:
            await _send_chunked(game_table_channel, narrative)

            # Fire post-turn story hook (non-blocking)
            _ambient = bot.get_cog("Ambient")
            if _ambient:
                asyncio.create_task(_ambient.post_story_hook(game_table_channel, narrative))

        # --- Combat tracking: detect start/end from scene changes ---
        scene_changes = result.get("scene_changes") or {}
        if scene_changes.get("combat_started") and not combat_tracker.in_combat:
            party = vault.get_party_state()
            monsters_desc = ", ".join(scene_changes.get("monsters_introduced", [])) or "enemies"
            init_order = combat_tracker.start_combat(party, monsters_desc)
            await game_table_channel.send(f"\u2694\ufe0f {init_order}")

            # If monsters go first, generate their turn immediately
            if combat_tracker.monsters_go_first():
                await _generate_monster_turn(game_table_channel)

        if scene_changes.get("combat_ended") and combat_tracker.in_combat:
            end_msg = combat_tracker.end_combat()
            await game_table_channel.send(end_msg)

        # Advance combat round if all players acted
        if combat_tracker.in_combat and combat_tracker.all_players_acted():
            round_header = combat_tracker.advance_round()
            await game_table_channel.send(round_header)

            # If monsters go first in the new round, generate their turn now
            if combat_tracker.monsters_go_first():
                await _generate_monster_turn(game_table_channel)

        # Advance conversation history decay once per batch
        context_assembler.history.advance_turn()

        if result.get("error"):
            logger.error(f"Auto-batch pipeline error: {result['error']}")

    except Exception as e:
        logger.error(f"Auto-batch resolve error: {e}", exc_info=True)
        await send_to_moderator_log(f"[auto_batch_resolve] Error:\n{traceback.format_exc()}")
        await game_table_channel.send(
            "\u26a0\ufe0f Something went wrong resolving the turn. The DM has been notified."
        )


# Wire the callback
turn_collector._on_resolve = _resolve_auto_batch


# ---------------------------------------------------------------------------
# War Room Pipeline
# ---------------------------------------------------------------------------
async def _handle_war_room(message, user_input: str):
    """Handle messages in the War Room channel — Prep Team pipeline."""
    logger.info(f"[War Room] {message.author}: {user_input}")

    try:
        route = await prep_router.route(user_input)
        logger.info(f"[War Room] Routed as: {route}")

        async with message.channel.typing():
            if route.intent == PrepIntent.NPC_CREATE:
                response = await world_architect.create_npc(user_input)
            elif route.intent == PrepIntent.LOCATION_CREATE:
                response = await world_architect.create_location(user_input)
            elif route.intent == PrepIntent.SESSION_PLANNING:
                response = await campaign_planner.process_request(user_input)
            elif route.intent == PrepIntent.SCENE_SETUP:
                response = await foundry_architect.process_request(user_input)
            elif route.intent == PrepIntent.GENERAL_QUESTION:
                response = await message_router.generate_direct_response(user_input)
            else:  # WORLDBUILDING (default)
                response = await world_architect.brainstorm(user_input)

        if response:
            text_response = str(response)
            if len(text_response) > 2000:
                for i in range(0, len(text_response), 2000):
                    await message.channel.send(text_response[i : i + 2000])
            else:
                await message.channel.send(text_response)

    except Exception as e:
        logger.error(f"[War Room] Error: {e}", exc_info=True)
        await send_to_moderator_log(
            f"[War Room] Error from {message.author}:\n{user_input}\n{traceback.format_exc()}"
        )
        await message.channel.send("⚠️ Something went wrong in the War Room. Check the log.")


# ---------------------------------------------------------------------------
# Events
# ---------------------------------------------------------------------------
@bot.event
async def on_ready():
    logger.info(f"Logged in as {bot.user.name} ({bot.user.id})")
    logger.info(f"Vault path: {vault.vault_path}")
    logger.info(f"Current session: {current_session}")

    # Async-connect StateManager (MongoDB) — non-blocking, degrades gracefully
    if await state_manager.connect():
        logger.info("StateManager connected — DB-backed context active.")
        # Restore active solo sessions from MongoDB (Phase 2.0)
        solo_manager._state_manager = state_manager
        await solo_manager.restore_active()
    else:
        logger.warning("StateManager unavailable — running in vault-only mode.")

    # Start solo session timeout checker (Phase 3.2b)
    bot.loop.create_task(_solo_session_timeout_checker())

    # Async-connect Foundry VTT — non-blocking, degrades gracefully
    if foundry_client.api_key:
        if await foundry_client.connect():
            logger.info(f"Foundry VTT connected: client={foundry_client.client_id}")
        else:
            logger.warning("Foundry VTT connection failed — running without live board data.")
    else:
        logger.info("Foundry VTT disabled (no API key set).")

    # Register persistent views so admin console buttons survive restarts
    from bot.views.admin_views import AdminConsoleView
    admin_cog = bot.get_cog("Admin Console")
    if admin_cog:
        bot.add_view(AdminConsoleView(admin_cog))
        logger.info("Admin console persistent view registered.")

    # Sync slash commands (needed for /console)
    try:
        synced = await bot.tree.sync()
        logger.info(f"Synced {len(synced)} slash command(s).")
    except Exception as e:
        logger.error(f"Slash command sync failed: {e}")

    print("D&D AI System Online. Vault-backed state is active.")

    # First-run guidance — detect empty campaign state
    try:
        party = vault.get_party_state()
        if not party:
            print(
                "\n"
                "============================================================\n"
                "  FIRST-RUN SETUP NEEDED\n"
                "============================================================\n"
                "  No party members found in the vault.\n"
                "\n"
                "  To get started:\n"
                "  1. Type /console in any Discord channel to open the\n"
                "     DM Admin Console\n"
                "  2. If Foundry VTT is connected, use the Register button\n"
                "     (or !register <name>) to import characters\n"
                "  3. Or manually create .md files in\n"
                "     campaign_vault/01 - Party/\n"
                "\n"
                "  See docs/GETTING_STARTED.md for full instructions.\n"
                "============================================================\n"
            )
    except Exception:
        pass  # Don't let a guidance message break startup


@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Bot filter — ignore messages from other bots (MEE6, etc.)
    if message.author.bot:
        return

    # Message deduplication — Discord can re-deliver on gateway reconnections
    if message.id in _seen_messages:
        return
    _seen_messages.append(message.id)

    # Let commands go through the normal handler
    if message.content.startswith("!"):
        await bot.process_commands(message)
        return

    user_input = message.content
    channel_id = str(message.channel.id)

    # Content filter — apply to all non-command messages
    user_input, was_filtered = filter_content(user_input)
    if was_filtered:
        await send_to_moderator_log(
            f"[Content Filter] Filtered input from {message.author.name}: {message.content[:200]}"
        )

    # Check if this message is in the admin console thread
    admin_cog = bot.get_cog("Admin Console")
    is_console_thread = (
        isinstance(message.channel, discord.Thread)
        and admin_cog
        and admin_cog.is_console_thread(message.channel.id)
    )

    if is_console_thread:
        if admin_cog._is_ooc:
            await admin_cog.handle_ooc_message(message)
        else:
            # IC mode: treat as DM's action (queue or pipeline)
            character_name = resolve_from_message_author(message.author)
            if action_queue.is_queue_mode:
                action = QueuedAction(
                    discord_user_id=message.author.id,
                    discord_message_id=message.id,
                    channel_id=message.channel.id,
                    character_name=character_name,
                    player_input=user_input,
                )
                await action_queue.enqueue(action)
                try:
                    await message.add_reaction("\u23f3")
                except discord.HTTPException:
                    pass
                await admin_cog.refresh_console()
            else:
                await _handle_game_table(message, user_input)
        return  # Don't fall through to other handlers

    # Check if this is a solo adventure thread (before player thread check)
    is_solo_thread = (
        isinstance(message.channel, discord.Thread)
        and solo_manager.is_solo_thread(message.channel.id)
    )
    if is_solo_thread:
        await _handle_solo_message(message, user_input)
        return

    # Check if this message is in a player's private console thread
    is_player_thread = (
        isinstance(message.channel, discord.Thread)
        and action_queue.is_player_thread(message.channel.id)
    )

    # DM channel separation: DM messages in Game Table are forced in-character
    is_dm_user = DM_DISCORD_USER_ID and str(message.author.id) == str(DM_DISCORD_USER_ID)

    # --- Routing diagnostics ---
    logger.info(
        f"[ROUTING] channel_id={channel_id} thread={isinstance(message.channel, discord.Thread)} "
        f"is_player_thread={is_player_thread} author={message.author.name} "
        f"msg_id={message.id}"
    )

    if WAR_ROOM_CHANNEL_ID and channel_id == WAR_ROOM_CHANNEL_ID:
        await _handle_war_room(message, user_input)
    elif is_player_thread:
        # Player private thread — brainstorm mode with advisor
        logger.info(f"[ROUTING] → player_thread path for {message.author.name}")

        # Skip bot command messages — they're handled by PlayerCog (!craft, !commit)
        if user_input.startswith("!"):
            return

        ambient_cog = bot.get_cog("Ambient")
        if ambient_cog:
            ambient_cog.record_activity()

        if action_queue.is_queue_mode:
            # Queue mode: capture as secret action (existing behavior)
            character_name = resolve_from_message_author(message.author)
            action = QueuedAction(
                discord_user_id=message.author.id,
                discord_message_id=message.id,
                channel_id=message.channel.id,
                character_name=character_name,
                player_input=user_input,
                is_secret=True,
                private_thread_id=message.channel.id,
            )
            await action_queue.enqueue(action)
            try:
                await message.add_reaction("\u23f3")
            except discord.HTTPException:
                pass
            admin_cog = bot.get_cog("Admin Console")
            if admin_cog:
                await admin_cog.refresh_console()
        else:
            # Auto mode: brainstorm with Player Advisor
            character_name = resolve_from_message_author(message.author)
            if character_name and player_advisor.client:
                try:
                    await gemini_limiter.acquire()
                    async with message.channel.typing():
                        advice = await player_advisor.advise(
                            message.channel.id, character_name, user_input
                        )
                    await _send_chunked(message.channel, advice)
                except Exception as e:
                    logger.error(f"Player advisor error: {e}", exc_info=True)
                    await message.channel.send(
                        "I'm having trouble right now. Try pasting your action "
                        "directly into the Game Table!"
                    )
            else:
                # No character mapping — tell the player instead of falling through to pipeline
                logger.warning(
                    f"Player thread message from {message.author.name} but no character mapping "
                    f"(character_name={character_name}, advisor.client={bool(player_advisor.client)})"
                )
                await message.channel.send(
                    "I can't find your character sheet. Make sure you're in the "
                    "`PLAYER_MAP` and try `/whisper` again, or paste your action "
                    "directly into the Game Table."
                )
    elif GAME_TABLE_CHANNEL_ID and channel_id == GAME_TABLE_CHANNEL_ID:
        # Record activity for ambient idle detection
        ambient_cog = bot.get_cog("Ambient")
        if ambient_cog:
            ambient_cog.record_activity()

        # Queue mode: capture the action instead of running the pipeline
        if action_queue.is_queue_mode:
            character_name = resolve_from_message_author(message.author)
            action = QueuedAction(
                discord_user_id=message.author.id,
                discord_message_id=message.id,
                channel_id=message.channel.id,
                character_name=character_name,
                player_input=user_input,
            )
            await action_queue.enqueue(action)
            try:
                await message.add_reaction("\u23f3")
            except discord.HTTPException:
                pass
            admin_cog = bot.get_cog("Admin Console")
            if admin_cog:
                await admin_cog.refresh_console()
        elif turn_collector.enabled:
            # Auto Mode with collection window — batch messages before pipeline
            character_name = resolve_from_message_author(message.author)
            is_first = await turn_collector.collect(message, character_name, user_input)
            if is_first:
                # Window just opened — post a status message
                turn_collector.status_message = await message.channel.send(
                    f"\u23f3 *Collecting actions for {turn_collector.window_seconds}s... "
                    f"(1 player so far)*"
                )
            else:
                # Update existing status message with unique player count
                if turn_collector.status_message:
                    try:
                        players = turn_collector.unique_player_count
                        total = turn_collector.pending_count
                        count_str = f"{players} player{'s' if players != 1 else ''}"
                        if total > players:
                            count_str += f", {total} actions"
                        await turn_collector.status_message.edit(
                            content=(
                                f"\u23f3 *Collecting actions for {turn_collector.window_seconds}s... "
                                f"({count_str} so far)*"
                            )
                        )
                    except discord.HTTPException:
                        pass
        else:
            # Collection disabled — run pipeline immediately
            await _handle_game_table(message, user_input)
    else:
        # Guard: don't process thread messages through the pipeline
        # (unregistered whisper threads after bot restart, etc.)
        if isinstance(message.channel, discord.Thread):
            logger.debug(
                f"Ignoring thread message from {message.author.name} in "
                f"unregistered thread {message.channel.id} (parent={message.channel.parent_id})"
            )
            return
        await _handle_game_table(message, user_input)


# ---------------------------------------------------------------------------
# Cog Loading & Entry Point
# ---------------------------------------------------------------------------
async def load_cogs():
    """Load all Cog extensions."""
    await bot.load_extension("bot.cogs.dm_cog")
    await bot.load_extension("bot.cogs.foundry_cog")
    await bot.load_extension("bot.cogs.prep_cog")
    await bot.load_extension("bot.cogs.admin_cog")
    await bot.load_extension("bot.cogs.player_cog")
    await bot.load_extension("bot.cogs.sync_cog")
    await bot.load_extension("bot.cogs.ambient_cog")
    await bot.load_extension("bot.cogs.solo_cog")
    await bot.load_extension("bot.cogs.monitoring_cog")
    logger.info("All Cogs loaded.")


async def main():
    """Async entry point — load cogs then start the bot."""
    try:
        async with bot:
            await load_cogs()
            await bot.start(DISCORD_TOKEN)
    finally:
        await foundry_client.close()


def _acquire_lockfile() -> bool:
    """Acquire a PID lockfile to prevent multiple bot instances.

    Returns True if the lock was acquired (safe to start).
    Returns False if another instance is already running.
    Uses only stdlib — no psutil dependency.
    """
    import subprocess

    lockfile = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".bot.lock")

    if os.path.exists(lockfile):
        try:
            with open(lockfile, "r") as f:
                old_pid = int(f.read().strip())

            # Check if that PID is still a running bot process (Windows-only)
            try:
                result = subprocess.run(
                    ["powershell", "-Command",
                     f"(Get-CimInstance Win32_Process -Filter \"ProcessId={old_pid}\").CommandLine"],
                    capture_output=True, text=True, timeout=5,
                )
                cmdline = (result.stdout or "").lower()
                if "orchestration/main.py" in cmdline or "bot/client" in cmdline:
                    print(f"ERROR: Bot is already running (PID {old_pid}).")
                    print(f"  Kill it first:  taskkill /PID {old_pid} /F")
                    print(f"  Or delete the lockfile:  {lockfile}")
                    return False
            except (subprocess.TimeoutExpired, OSError):
                pass  # Can't check — assume stale

            # Stale lockfile — old process is gone or not the bot
            logger.info(f"Removing stale lockfile (PID {old_pid} no longer running)")
        except (ValueError, OSError):
            pass  # Corrupt lockfile — overwrite it

    # Write our PID
    try:
        with open(lockfile, "w") as f:
            f.write(str(os.getpid()))
    except OSError as e:
        logger.warning(f"Could not write lockfile: {e}")

    return True


def _release_lockfile():
    """Remove the PID lockfile on shutdown."""
    lockfile = os.path.join(os.path.dirname(os.path.dirname(__file__)), ".bot.lock")
    try:
        if os.path.exists(lockfile):
            with open(lockfile, "r") as f:
                stored_pid = int(f.read().strip())
            # Only remove if it's OUR lockfile
            if stored_pid == os.getpid():
                os.remove(lockfile)
    except (ValueError, OSError):
        pass


def run():
    """Synchronous entry point for scripts."""
    if not DISCORD_TOKEN:
        print("Error: DISCORD_BOT_TOKEN not found via os.getenv")
        return

    if not _acquire_lockfile():
        return

    try:
        asyncio.run(main())
    finally:
        _release_lockfile()
