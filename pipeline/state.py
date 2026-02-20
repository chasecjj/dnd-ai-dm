"""
GameState — The typed state that flows through every node in the LangGraph pipeline.

Each node reads from and writes to this state dict.
LangGraph automatically merges the returned partial state.
"""

from typing import TypedDict, Optional, List, Dict, Any


class GameState(TypedDict, total=False):
    """State flowing through the Game Table LangGraph pipeline.

    Fields:
        player_input:    Raw message from the Discord player.
        character_name:  Resolved character name (from PLAYER_MAP), or None.
        message_type:    Classification from the router (game_action, casual_chat, etc.).
        direct_response: If True, skip pipeline — reply directly.
        needs_board_monitor: Router flag.
        needs_rules_lawyer:  Router flag.
        needs_storyteller:   Router flag.
        board_context:   Output from BoardMonitor node.
        rules_ruling:    Structured JSON from RulesLawyer node.
        narrative:       Prose output from Storyteller node.
        scene_changes:   Output from SceneSync node (location change, combat, etc.).
        chronicler_done: Whether the Chronicler has processed this turn.
        session:         Current session number.
        current_location: Current in-game location.
        error:           If set, an error occurred at some node.
        direct_reply:    If set, this is a direct response to send (skipping pipeline).
    """
    player_input: str
    character_name: Optional[str]
    message_type: str
    direct_response: bool
    needs_board_monitor: bool
    needs_rules_lawyer: bool
    needs_storyteller: bool
    board_context: str
    rules_ruling: Optional[Dict[str, Any]]
    narrative: str
    scene_changes: Optional[Dict[str, Any]]
    chronicler_done: bool
    session: int
    current_location: str
    error: Optional[str]
    direct_reply: Optional[str]
    # Admin console fields — populated during batch resolve
    dm_context: Optional[str]
    dice_results: Optional[Dict[str, Dict[str, Any]]]
    is_batched: bool
    # Sync fields — carries character sync results through the pipeline
    sync_report: Optional[Dict[str, Any]]
