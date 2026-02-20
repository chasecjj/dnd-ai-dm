"""
Game Table Pipeline — Compiled LangGraph graph.

Replaces the if/else chain in _handle_game_table() with a stateful
directed graph where each node is a discrete agent wrapper and each
edge is a routing decision.

Usage:
    pipeline = build_game_pipeline(agents_dict)
    result = await pipeline.ainvoke(initial_state)
"""

import logging
from functools import partial
from typing import Dict, Any

from pipeline.state import GameState
from pipeline.nodes.router_node import router_node
from pipeline.nodes.board_monitor_node import board_monitor_node
from pipeline.nodes.rules_node import rules_node
from pipeline.nodes.storyteller_node import storyteller_node
from pipeline.nodes.scene_sync_node import scene_sync_node
from pipeline.nodes.chronicler_node import chronicler_node

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

    # Bind agents into node functions via partial application
    _router = partial(router_node, message_router=agents["message_router"])
    _board = partial(board_monitor_node, board_monitor=agents["board_monitor"],
                     vault_manager=agents.get("vault_manager"),
                     state_manager=agents.get("state_manager"))
    _rules = partial(rules_node, rules_lawyer=agents["rules_lawyer"], context_assembler=agents["context_assembler"])
    _story = partial(storyteller_node, storyteller=agents["storyteller"])
    _scene = partial(
        scene_sync_node,
        storyteller=agents["storyteller"],
        gemini_client=agents["gemini_client"],
        model_id=agents["model_id"],
    )
    _chron = partial(
        chronicler_node,
        chronicler=agents["chronicler"],
        context_assembler=agents["context_assembler"],
        storyteller=agents["storyteller"],
        vault_manager=agents.get("vault_manager"),
        foundry_client=agents.get("foundry_client"),
    )

    # Build the graph
    graph = StateGraph(GameState)

    graph.add_node("router", _router)
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
