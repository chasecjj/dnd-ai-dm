"""
Tests for tools/action_queue.py — ActionQueue, QueuedAction, RollRequest, MonsterRoll.

Tests the Pydantic models and the async queue operations.
"""

import asyncio

from tools.action_queue import (
    RollRequest,
    MonsterRoll,
    QueuedAction,
    ActionQueue,
)


# ---------------------------------------------------------------------------
# Model tests
# ---------------------------------------------------------------------------

class TestRollRequest:

    def test_creation(self):
        rr = RollRequest(index=0, roll_type="Attack", formula="1d20+5")
        assert rr.index == 0
        assert rr.roll_type == "Attack"
        assert rr.formula == "1d20+5"
        assert rr.dc is None
        assert rr.result is None
        assert rr.resolved is False

    def test_with_dc(self):
        rr = RollRequest(index=0, roll_type="Perception", formula="1d20+3", dc=15)
        assert rr.dc == 15

    def test_resolve(self):
        rr = RollRequest(index=0, roll_type="Attack", formula="1d20+5")
        rr.result = 18
        rr.detail = "1d20(13)+5 = 18"
        rr.resolved = True
        assert rr.resolved is True
        assert rr.result == 18


class TestMonsterRoll:

    def test_auto_id(self):
        mr = MonsterRoll(monster_name="Goblin", roll_type="Attack", formula="1d20+4")
        assert len(mr.id) > 0
        assert mr.timestamp > 0

    def test_two_rolls_unique_ids(self):
        mr1 = MonsterRoll(monster_name="Goblin", roll_type="Attack", formula="1d20+4")
        mr2 = MonsterRoll(monster_name="Goblin", roll_type="Attack", formula="1d20+4")
        assert mr1.id != mr2.id

    def test_optional_fields(self):
        mr = MonsterRoll(monster_name="Goblin", roll_type="Attack", formula="1d20+4")
        assert mr.target is None
        assert mr.result is None
        assert mr.detail is None


class TestQueuedAction:

    def test_creation(self):
        qa = QueuedAction(
            discord_user_id=12345,
            discord_message_id=67890,
            channel_id=99999,
            character_name="Hadrian",
            player_input="I swing my axe!",
        )
        assert qa.character_name == "Hadrian"
        assert qa.player_input == "I swing my axe!"
        assert qa.status == "pending"
        assert len(qa.id) > 0

    def test_needs_roll_empty(self):
        qa = QueuedAction(discord_user_id=1, discord_message_id=1, channel_id=1, player_input="Hello")
        assert qa.needs_roll is False

    def test_needs_roll_with_rolls(self):
        qa = QueuedAction(
            discord_user_id=1, discord_message_id=1, channel_id=1, player_input="Attack",
            rolls=[RollRequest(index=0, roll_type="Attack", formula="1d20+5")],
        )
        assert qa.needs_roll is True

    def test_current_pending_roll(self):
        qa = QueuedAction(
            discord_user_id=1, discord_message_id=1, channel_id=1, player_input="Attack",
            rolls=[
                RollRequest(index=0, roll_type="Attack", formula="1d20+5"),
                RollRequest(index=1, roll_type="Damage", formula="1d8+3"),
            ],
        )
        pending = qa.current_pending_roll
        assert pending is not None
        assert pending.roll_type == "Attack"

    def test_all_rolls_resolved(self):
        qa = QueuedAction(
            discord_user_id=1, discord_message_id=1, channel_id=1, player_input="Attack",
            rolls=[
                RollRequest(index=0, roll_type="Attack", formula="1d20+5", resolved=True, result=18),
                RollRequest(index=1, roll_type="Damage", formula="1d8+3", resolved=True, result=7),
            ],
        )
        assert qa.all_rolls_resolved is True
        assert qa.current_pending_roll is None

    def test_all_rolls_resolved_false_with_no_rolls(self):
        qa = QueuedAction(discord_user_id=1, discord_message_id=1, channel_id=1, player_input="X")
        assert qa.all_rolls_resolved is False  # No rolls means not "all resolved"


# ---------------------------------------------------------------------------
# ActionQueue tests
# ---------------------------------------------------------------------------

class TestActionQueueBasics:

    def test_initial_state(self):
        q = ActionQueue()
        assert q.is_queue_mode is False
        assert q.count == 0
        assert q.has_pending_rolls is False

    def test_enable_disable_queue_mode(self):
        q = ActionQueue()
        q.enable_queue_mode()
        assert q.is_queue_mode is True
        q.disable_queue_mode()
        assert q.is_queue_mode is False

    def test_toggle_queue_mode(self):
        q = ActionQueue()
        result = q.toggle_queue_mode()
        assert result is True
        assert q.is_queue_mode is True
        result = q.toggle_queue_mode()
        assert result is False
        assert q.is_queue_mode is False


class TestEnqueueAndGet:

    def test_enqueue_and_count(self):
        q = ActionQueue()
        action = QueuedAction(discord_user_id=1, discord_message_id=1, channel_id=1, player_input="Test")

        async def run():
            await q.enqueue(action)
            assert q.count == 1
            all_actions = await q.get_all()
            assert len(all_actions) == 1
            assert all_actions[0].player_input == "Test"

        asyncio.run(run())

    def test_get_by_id(self):
        q = ActionQueue()
        action = QueuedAction(discord_user_id=1, discord_message_id=1, channel_id=1, player_input="Test")

        async def run():
            await q.enqueue(action)
            found = await q.get_by_id(action.id)
            assert found is not None
            assert found.id == action.id

        asyncio.run(run())

    def test_get_by_id_not_found(self):
        q = ActionQueue()

        async def run():
            found = await q.get_by_id("nonexistent")
            assert found is None

        asyncio.run(run())

    def test_remove(self):
        q = ActionQueue()
        action = QueuedAction(discord_user_id=1, discord_message_id=1, channel_id=1, player_input="Test")

        async def run():
            await q.enqueue(action)
            removed = await q.remove(action.id)
            assert removed is not None
            assert q.count == 0

        asyncio.run(run())


class TestFlushAndBatch:

    def test_flush_all(self):
        q = ActionQueue()

        async def run():
            await q.enqueue(QueuedAction(discord_user_id=1, discord_message_id=1, channel_id=1, player_input="A"))
            await q.enqueue(QueuedAction(discord_user_id=2, discord_message_id=2, channel_id=1, player_input="B"))
            flushed = await q.flush()
            assert len(flushed) == 2
            assert q.count == 0

        asyncio.run(run())

    def test_flush_ready_only(self):
        q = ActionQueue()

        async def run():
            ready = QueuedAction(discord_user_id=1, discord_message_id=1, channel_id=1, player_input="Ready", status="ready")
            waiting = QueuedAction(discord_user_id=2, discord_message_id=2, channel_id=1, player_input="Waiting", status="awaiting_roll")
            await q.enqueue(ready)
            await q.enqueue(waiting)
            flushed = await q.flush_ready()
            assert len(flushed) == 1
            assert flushed[0].player_input == "Ready"
            assert q.count == 1  # "waiting" stays

        asyncio.run(run())

    def test_confirm_batch(self):
        q = ActionQueue()

        async def run():
            await q.enqueue(QueuedAction(discord_user_id=1, discord_message_id=1, channel_id=1, player_input="X", status="ready"))
            await q.flush_ready()
            await q.confirm_batch()
            # _last_batch should be empty after confirm
            restored = await q.restore_batch()
            assert restored == 0

        asyncio.run(run())

    def test_restore_batch(self):
        q = ActionQueue()

        async def run():
            await q.enqueue(QueuedAction(discord_user_id=1, discord_message_id=1, channel_id=1, player_input="X", status="ready"))
            flushed = await q.flush_ready()
            assert q.count == 0
            restored = await q.restore_batch()
            assert restored == 1
            assert q.count == 1
            # Restored actions should have status reset to "ready"
            all_actions = await q.get_all()
            assert all_actions[0].status == "ready"

        asyncio.run(run())


class TestRollSequence:

    def test_update_roll_result_single(self):
        q = ActionQueue()

        async def run():
            action = QueuedAction(discord_user_id=42, discord_message_id=1, channel_id=1, player_input="Attack")
            await q.enqueue(action)
            await q.request_roll(action.id, "Attack", "1d20+5", dc=15)

            result_action, next_roll = await q.update_roll_result(42, 18, "1d20(13)+5 = 18")
            assert result_action is not None
            assert result_action.rolls[0].resolved is True
            assert result_action.rolls[0].result == 18
            assert next_roll is None  # Only one roll, so done
            assert result_action.status == "ready"

        asyncio.run(run())

    def test_multi_roll_sequence(self):
        q = ActionQueue()

        async def run():
            action = QueuedAction(discord_user_id=42, discord_message_id=1, channel_id=1, player_input="Attack")
            await q.enqueue(action)
            await q.request_roll(action.id, "Attack", "1d20+5", dc=15)
            await q.request_roll(action.id, "Damage", "1d8+3")

            # First roll — attack
            result_action, next_roll = await q.update_roll_result(42, 18, "1d20(13)+5 = 18")
            assert result_action is not None
            assert next_roll is not None
            assert next_roll.roll_type == "Damage"
            assert result_action.status == "awaiting_roll"  # Still awaiting damage

            # Second roll — damage
            result_action, next_roll = await q.update_roll_result(42, 7, "1d8(4)+3 = 7")
            assert result_action is not None
            assert next_roll is None  # All done
            assert result_action.status == "ready"
            assert result_action.all_rolls_resolved is True

        asyncio.run(run())

    def test_update_roll_no_pending(self):
        q = ActionQueue()

        async def run():
            result_action, next_roll = await q.update_roll_result(99, 15, "1d20 = 15")
            assert result_action is None
            assert next_roll is None

        asyncio.run(run())


class TestMonsterRolls:

    def test_add_and_get(self):
        q = ActionQueue()

        async def run():
            roll = await q.add_monster_roll("Goblin", "Attack", "1d20+4", target="Hadrian")
            assert roll.monster_name == "Goblin"
            all_rolls = await q.get_monster_rolls()
            assert len(all_rolls) == 1

        asyncio.run(run())

    def test_resolve_monster_roll(self):
        q = ActionQueue()

        async def run():
            roll = await q.add_monster_roll("Goblin", "Attack", "1d20+4")
            success = await q.resolve_monster_roll(roll.id, 15, "1d20(11)+4 = 15")
            assert success is True
            all_rolls = await q.get_monster_rolls()
            assert all_rolls[0].result == 15

        asyncio.run(run())

    def test_flush_monster_rolls(self):
        q = ActionQueue()

        async def run():
            roll1 = await q.add_monster_roll("Goblin", "Attack", "1d20+4")
            roll2 = await q.add_monster_roll("Wolf", "Bite", "1d20+4")
            await q.resolve_monster_roll(roll1.id, 15, "15")
            # Only resolved rolls get flushed
            flushed = await q.flush_monster_rolls()
            assert len(flushed) == 1
            assert flushed[0].monster_name == "Goblin"
            # Unresolved wolf remains
            remaining = await q.get_monster_rolls()
            assert len(remaining) == 1
            assert remaining[0].monster_name == "Wolf"

        asyncio.run(run())


class TestPlayerThreads:

    def test_register_and_get(self):
        q = ActionQueue()
        q.register_player_thread(42, 999)
        assert q.get_player_thread(42) == 999

    def test_get_unregistered(self):
        q = ActionQueue()
        assert q.get_player_thread(42) is None

    def test_is_player_thread(self):
        q = ActionQueue()
        q.register_player_thread(42, 999)
        assert q.is_player_thread(999) is True
        assert q.is_player_thread(888) is False


class TestDMEvent:

    def test_add_dm_event(self):
        q = ActionQueue()

        async def run():
            event = await q.add_dm_event("A storm rolls in", annotation="Set the mood")
            assert event.is_dm_event is True
            assert event.player_input == "A storm rolls in"
            assert event.dm_annotation == "Set the mood"
            assert event.status == "ready"
            assert q.count == 1

        asyncio.run(run())
