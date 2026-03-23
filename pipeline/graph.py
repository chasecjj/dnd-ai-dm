"""
Game Table Pipeline — Compiled LangGraph graph.

Replaces the if/else chain in _handle_game_table() with a stateful
directed graph where each node is a discrete agent wrapper and each
edge is a routing decision.

Usage:
    pipeline = build_game_pipeline(agents_dict)
    result = await pipeline.ainvoke(initial_state)
"""

import time
import logging
from functools import partial, wraps
from typing import Dict, Any

from tools.pipeline_metrics import pipeline_metrics

from pipeline.state import GameState
from pipeline.nodes.router_node import router_node
from pipeline.nodes.board_monitor_node import board_monitor_node
from pipeline.nodes.rules_node import rules_node
from pipeline.nodes.storyteller_node import storyteller_node
from pipeline.nodes.scene_sync_node import scene_sync_node
from pipeline.nodes.chronicler_node import chronicler_node
from pipeline.nodes.mood_node import mood_node

logger = logging.getLogger("pipeline.graph")

# ---------------------------------------------------------------------------
# Lazy LangGraph import — allows the rest of the codebase to load even if
# LangGraph is not installed. The build function will raise a clear error.
# ---------------------------------------------------------------------------
try:
    from langgraph.graph import StateGraph, END
    HAS_LANGGRAPH = True
except ImportError:
    HAS_LANGGRAPH = False
    StateGraph = None  # type: ignore[assignment,misc]
    END = None  # type: ignore[assignment]


def _route_after_router(state: dict) -> str:
    """Conditional edge after the router node.

    Decides whether to stop (casual/direct) or continue to the pipeline.
    """
    if state.get("error"):
        return "end"
    if state.get("message_type") == "casual_chat":
        return "end"
    if state.get("direct_response"):
        return "end"
    # All game-action paths go through mood assessment first
    return "mood"


def _route_after_mood(state: dict) -> str:
    """Conditional edge after the mood node — dispatches using original routing flags."""
    if state.get("needs_board_monitor"):
        return "board"
    if state.get("needs_rules_lawyer"):
        return "rules"
    if state.get("needs_storyteller"):
        return "storyteller"
    return "end"


def _route_after_board(state: dict) -> str:
    """After board monitor, go to rules or storyteller."""
    if state.get("needs_rules_lawyer"):
        return "rules"
    if state.get("needs_storyteller"):
        return "storyteller"
    return "end"


def _timed_node(name: str, fn):
    """Wrap an async node function with per-node latency tracking."""
    @wraps(fn)
    async def wrapper(state, **kwargs):
        start = time.monotonic()
        result = await fn(state, **kwargs)
        pipeline_metrics.record_node(name, time.monotonic() - start)
        return result
    return wrapper


def build_game_pipeline(agents: Dict[str, Any]):
    """Build and compile the Game Table LangGraph pipeline.

    Args:
        agents: Dict with keys matching agent names. Expected keys:
            message_router, board_monitor, rules_lawyer, storyteller,
            chronicler, context_assembler, gemini_client, model_id

    Returns:
        A compiled LangGraph Pregel object (call .ainvoke(state)).
    """
    if not HAS_LANGGRAPH:
        raise ImportError(
            "LangGraph is not installed. Run: pip install langgraph langchain-core"
        )

    # Bind agents into node functions via partial application, wrapped with timing
    _router = _timed_node("router", partial(router_node, message_router=agents["message_router"]))
    _mood = _timed_node("mood", partial(mood_node, mood_agent=agents["mood_agent"]))
    _board = _timed_node("board", partial(board_monitor_node, board_monitor=agents["board_monitor"],
                     vault_manager=agents.get("vault_manager"),
                     state_manager=agents.get("state_manager")))
    _rules = _timed_node("rules", partial(rules_node, rules_lawyer=agents["rules_lawyer"], context_assembler=agents["context_assembler"]))
    _story = _timed_node("storyteller", partial(storyteller_node, storyteller=agents["storyteller"]))
    _scene = _timed_node("scene_sync", partial(
        scene_sync_node,
        storyteller=agents["storyteller"],
        gemini_client=agents["gemini_client"],
        model_id=agents["model_id"],
    ))
    _chron = _timed_node("chronicler", partial(
        chronicler_node,
        chronicler=agents["chronicler"],
        context_assembler=agents["context_assembler"],
        storyteller=agents["storyteller"],
        vault_manager=agents.get("vault_manager"),
        foundry_client=agents.get("foundry_client"),
    ))

    # Build the graph
    graph = StateGraph(GameState)

    graph.add_node("router", _router)
    graph.add_node("mood", _mood)
    graph.add_node("board", _board)
    graph.add_node("rules", _rules)
    graph.add_node("storyteller", _story)
    graph.add_node("scene_sync", _scene)
    graph.add_node("chronicler", _chron)

    # Entry point
    graph.set_entry_point("router")

    # Conditional edges from router
    graph.add_conditional_edges(
        "router",
        _route_after_router,
        {
            "mood": "mood",
            "end": END,
        },
    )

    # Conditional edges from mood
    graph.add_conditional_edges(
        "mood",
        _route_after_mood,
        {
            "board": "board",
            "rules": "rules",
            "storyteller": "storyteller",
            "end": END,
        },
    )

    # Conditional edges from board monitor
    graph.add_conditional_edges(
        "board",
        _route_after_board,
        {
            "rules": "rules",
            "storyteller": "storyteller",
            "end": END,
        },
    )

    # Linear edges: rules → storyteller → scene_sync → chronicler → END
    graph.add_edge("rules", "storyteller")
    graph.add_edge("storyteller", "scene_sync")
    graph.add_edge("scene_sync", "chronicler")
    graph.add_edge("chronicler", END)

    compiled = graph.compile()
    logger.info("Game pipeline compiled successfully.")
    return compiled
