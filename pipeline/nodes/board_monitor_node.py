"""
Board Monitor Node — Pulls live Foundry VTT spatial context.

Wraps the existing BoardMonitorAgent. Only runs if needs_board_monitor is True.
"""

import logging
from pipeline.state import GameState

logger = logging.getLogger("pipeline.board_monitor")


async def board_monitor_node(
    state: GameState,
    *,
    board_monitor,
    vault_manager=None,
    state_manager=None,
    **_kwargs,
) -> dict:
    """Pull spatial context from Foundry VTT.

    Also runs pre-sync (Foundry → vault/DB) for linked characters so the
    pipeline operates on the freshest HP/condition data.

    Args:
        state: Current GameState.
        board_monitor: The existing BoardMonitorAgent instance.
        vault_manager: VaultManager for character sync (optional).
        state_manager: StateManager for MongoDB sync (optional).
    """
    if not state.get("needs_board_monitor"):
        return {"board_context": ""}

    try:
        # Pre-sync: pull Foundry → vault/DB before the pipeline reads character state
        pre_sync_changes = []
        if vault_manager and board_monitor.foundry and board_monitor.foundry.is_connected:
            from tools.character_sync import sync_foundry_to_local
            try:
                pre_sync_changes = await sync_foundry_to_local(
                    board_monitor.foundry, vault_manager, state_manager
                )
                if pre_sync_changes:
                    logger.info(f"Pre-sync: {len(pre_sync_changes)} change(s)")
            except Exception as e:
                logger.warning(f"Pre-sync failed (non-blocking): {e}")

        context = await board_monitor.process_request(state["player_input"])
        if context == "No specific board state queried.":
            context = ""
        logger.info(f"Board context: {context[:100]}...")

        result = {"board_context": context}
        if pre_sync_changes:
            result["sync_report"] = {"pre_sync": pre_sync_changes}
        return result

    except Exception as e:
        logger.error(f"Board monitor node error: {e}", exc_info=True)
        return {"board_context": ""}
