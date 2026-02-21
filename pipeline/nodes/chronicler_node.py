"""
Chronicler Node — Silent record-keeper that updates the vault after each exchange.

Wraps the existing ChroniclerAgent. Runs last. Never speaks to players.
Errors here never affect gameplay.
"""

import logging
from pipeline.state import GameState
from tools.rate_limiter import gemini_limiter

logger = logging.getLogger("pipeline.chronicler")


async def chronicler_node(
    state: GameState,
    *,
    chronicler,
    context_assembler,
    storyteller,
    vault_manager=None,
    foundry_client=None,
    **_kwargs,
) -> dict:
    """Process the exchange and update the vault.

    Also runs post-sync (vault → Foundry) to push HP changes from the
    pipeline back to Foundry tokens.

    Args:
        state: Current GameState.
        chronicler: The existing ChroniclerAgent instance.
        context_assembler: For saving checkpoints.
        storyteller: For current location.
        vault_manager: VaultManager for reading foundry_uuid (optional).
        foundry_client: FoundryClient for pushing changes (optional).
    """
    # Only chronicle if we ran the rules lawyer or storyteller
    if not state.get("needs_rules_lawyer") and not state.get("needs_storyteller"):
        return {"chronicler_done": False}

    try:
        rules_text = str(state.get("rules_ruling")) if state.get("rules_ruling") else "N/A"
        character_name = state.get("character_name")
        player_input = state["player_input"]
        # Prefix with character name so the Chronicler attributes events correctly
        if character_name:
            player_input = f"[{character_name}]: {player_input}"

        await gemini_limiter.acquire()
        changes = await chronicler.process_exchange(
            player_action=player_input,
            rules_response=rules_text,
            story_response=state.get("narrative", ""),
            session_number=state.get("session", 0),
            current_location=storyteller._current_location,
        )
        context_assembler.save_checkpoint()

        # Post-sync: push character HP changes to Foundry
        post_sync_results = []
        if foundry_client and foundry_client.is_connected and changes and vault_manager:
            char_updates = changes.get("character_updates", [])
            if char_updates:
                from tools.character_sync import push_changes_to_foundry
                try:
                    update_dicts = [
                        {"name": u.get("name", ""), **{k: v for k, v in u.items()
                         if k != "name" and v is not None}}
                        for u in char_updates if u.get("name")
                    ]
                    post_sync_results = await push_changes_to_foundry(
                        update_dicts, vault_manager, foundry_client
                    )
                    if post_sync_results:
                        logger.info(f"Post-sync: {len(post_sync_results)} push(es)")
                except Exception as e:
                    logger.warning(f"Post-sync failed (non-blocking): {e}")

        # Merge sync_report: append post_sync to any existing pre_sync
        sync_report = dict(state.get("sync_report") or {})
        if post_sync_results:
            sync_report["post_sync"] = post_sync_results

        result = {"chronicler_done": True}
        if sync_report:
            result["sync_report"] = sync_report
        return result

    except Exception as e:
        # Chronicler errors are NEVER blocking
        logger.error(f"Chronicler node error (non-blocking): {e}", exc_info=True)
        return {"chronicler_done": False}
