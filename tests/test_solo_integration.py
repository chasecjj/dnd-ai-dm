"""
Integration tests for the Solo Adventure system.

Covers:
- Per-session history isolation (Phase 0.1)
- Processing lock behavior (Phase 0.2)
- Multi-turn undo stack (Phase 3.2a)
- Oracle grading (Phase 1.3)
- Chaos factor assessment (Phase 2.1)
- Thread tracker dormancy (Phase 2.2)
- NPC registry and autonomy (Phase 2.3)
- Faction tracker (Phase 3.1)
- Narrative directive coordination (Phase 2.4)
- Session serialization (Phase 2.0)
- Session timeout detection (Phase 3.2b)
- Snapshot schema versioning (Phase 3.2c)
- Merge summary generation (Phase 4.1)
"""

import asyncio
import time
import pytest

from tools.solo_session import (
    SoloSession, SoloSessionManager, SoloTurnSnapshot,
    SNAPSHOT_SCHEMA_VERSION, MAX_SNAPSHOT_DEPTH,
)
from tools.solo_engine import (
    OutcomeGrade, grade_outcome, build_oracle_directive,
    ChaosTracker, SceneAlteration, build_chaos_directive,
    NarrativeDirective, DirectivePriority, coordinate_directives,
)
from tools.solo_world import (
    ThreadTracker, SoloNPCRegistry, FactionTracker,
    extract_threads_from_chronicler, extract_npcs_from_chronicler,
    build_npc_activity_directive, build_thread_directive, build_faction_directive,
)
from tools.solo_merge import generate_merge_summary, build_solo_recap_for_group


# ---------------------------------------------------------------------------
# Phase 0: Per-Session History Isolation
# ---------------------------------------------------------------------------

class TestPerSessionHistoryIsolation:
    """Verify that concurrent solo sessions have independent histories."""

    @pytest.fixture
    def manager(self):
        return SoloSessionManager()

    @pytest.mark.asyncio
    async def test_sessions_get_independent_histories(self, manager):
        """Two concurrent sessions should have separate ConversationHistory instances."""
        s1 = await manager.start_session(100, 200, "Victor", "Docks", 3)
        s2 = await manager.start_session(101, 201, "Hadrian", "Market", 3)

        h1 = manager.get_history(200)
        h2 = manager.get_history(201)

        assert h1 is not None
        assert h2 is not None
        assert h1 is not h2  # Different instances

        # Adding to one doesn't affect the other
        h1.add_event("Victor fought a rat", impact=5)
        assert len(h1.entries) == 1
        assert len(h2.entries) == 0

    @pytest.mark.asyncio
    async def test_end_session_cleans_up_history(self, manager):
        """Ending a session should remove its history."""
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        assert manager.get_history(200) is not None

        await manager.end_session(200)
        assert manager.get_history(200) is None

    @pytest.mark.asyncio
    async def test_end_one_preserves_other_history(self, manager):
        """Ending one session shouldn't affect another's history."""
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        await manager.start_session(101, 201, "Hadrian", "Market", 3)

        h2 = manager.get_history(201)
        h2.add_event("Hadrian bought a sword", impact=3)

        await manager.end_session(200)

        # Hadrian's history still intact
        h2_after = manager.get_history(201)
        assert h2_after is not None
        assert len(h2_after.entries) == 1


# ---------------------------------------------------------------------------
# Phase 0.2: Processing Locks
# ---------------------------------------------------------------------------

class TestProcessingLocks:
    """Verify per-session processing locks."""

    @pytest.fixture
    def manager(self):
        return SoloSessionManager()

    @pytest.mark.asyncio
    async def test_processing_lock_created(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        lock = manager.get_processing_lock(200)
        assert lock is not None
        assert isinstance(lock, asyncio.Lock)

    @pytest.mark.asyncio
    async def test_processing_lock_independent(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        await manager.start_session(101, 201, "Hadrian", "Market", 3)

        lock1 = manager.get_processing_lock(200)
        lock2 = manager.get_processing_lock(201)
        assert lock1 is not lock2

    @pytest.mark.asyncio
    async def test_processing_lock_cleaned_up(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        await manager.end_session(200)
        assert manager.get_processing_lock(200) is None


# ---------------------------------------------------------------------------
# Phase 1.3: Oracle Grading
# ---------------------------------------------------------------------------

class TestOracleGrading:
    """Test the graduated outcome oracle system."""

    def test_critical_success_nat20(self):
        assert grade_outcome(25, 15, is_nat_20=True) == OutcomeGrade.CRITICAL_SUCCESS

    def test_critical_success_beat_by_5(self):
        assert grade_outcome(20, 15) == OutcomeGrade.CRITICAL_SUCCESS

    def test_success(self):
        assert grade_outcome(15, 15) == OutcomeGrade.SUCCESS
        assert grade_outcome(18, 15) == OutcomeGrade.SUCCESS

    def test_partial(self):
        assert grade_outcome(14, 15) == OutcomeGrade.PARTIAL
        assert grade_outcome(12, 15) == OutcomeGrade.PARTIAL

    def test_failure(self):
        assert grade_outcome(10, 15) == OutcomeGrade.FAILURE
        assert grade_outcome(8, 15) == OutcomeGrade.FAILURE

    def test_critical_failure_nat1(self):
        assert grade_outcome(5, 15, is_nat_1=True) == OutcomeGrade.CRITICAL_FAILURE

    def test_critical_failure_miss_by_10(self):
        assert grade_outcome(5, 15) == OutcomeGrade.CRITICAL_FAILURE

    def test_oracle_directive_contains_grade(self):
        directive = build_oracle_directive(OutcomeGrade.PARTIAL)
        assert "Yes, but..." in directive
        assert "NARRATION GUIDE" in directive

    def test_oracle_directive_all_grades(self):
        """Every grade should produce a non-empty directive."""
        for grade in OutcomeGrade:
            directive = build_oracle_directive(grade)
            assert len(directive) > 20


# ---------------------------------------------------------------------------
# Phase 2.1: Chaos Factor
# ---------------------------------------------------------------------------

class TestChaosTracker:
    """Test chaos factor tracking and event generation."""

    def test_initial_factor(self):
        chaos = ChaosTracker()
        assert chaos.factor == 5

    def test_adjust_up(self):
        chaos = ChaosTracker(factor=5)
        chaos.adjust("up")
        assert chaos.factor == 6

    def test_adjust_down(self):
        chaos = ChaosTracker(factor=5)
        chaos.adjust("down")
        assert chaos.factor == 4

    def test_clamp_max(self):
        chaos = ChaosTracker(factor=9)
        chaos.adjust("up")
        assert chaos.factor == 9  # Can't exceed max

    def test_clamp_min(self):
        chaos = ChaosTracker(factor=1)
        chaos.adjust("down")
        assert chaos.factor == 1  # Can't go below min

    def test_assess_chaos_up(self):
        """HP loss + conditions should push chaos up."""
        chaos = ChaosTracker()
        direction = chaos.assess_chronicler_output({
            "character_updates": [
                {"name": "Victor", "hp_current": 10, "conditions": ["poisoned"]},
            ],
        })
        assert direction == "up"

    def test_assess_chaos_down(self):
        """Quest completion should push chaos down."""
        chaos = ChaosTracker()
        direction = chaos.assess_chronicler_output({
            "quest_updates": [
                {"name": "Find the merchant", "status": "completed"},
            ],
            "events": [{"type": "decision"}],
        })
        assert direction == "down"

    def test_assess_chaos_neutral(self):
        """Minimal chronicler output should be neutral."""
        chaos = ChaosTracker()
        direction = chaos.assess_chronicler_output({})
        assert direction == "none"

    def test_serialization(self):
        chaos = ChaosTracker(factor=7)
        d = chaos.to_dict()
        restored = ChaosTracker.from_dict(d)
        assert restored.factor == 7

    def test_chaos_directive_normal(self):
        directive = build_chaos_directive(5, SceneAlteration.NORMAL, None)
        assert "5/9" in directive

    def test_chaos_directive_altered(self):
        directive = build_chaos_directive(7, SceneAlteration.ALTERED, "discovery")
        assert "ALTERED" in directive
        assert "discovery" in directive.lower()


# ---------------------------------------------------------------------------
# Phase 2.2: Thread Tracker
# ---------------------------------------------------------------------------

class TestThreadTracker:
    """Test plot thread tracking with dormancy detection."""

    def test_add_thread(self):
        tracker = ThreadTracker()
        tracker.add_thread("Find the merchant", turn=1, priority=7)
        assert len(tracker.get_active()) == 1
        assert tracker.get_active()[0].title == "Find the merchant"

    def test_no_duplicates(self):
        tracker = ThreadTracker()
        tracker.add_thread("Find the merchant", turn=1)
        tracker.add_thread("Find the merchant", turn=5)
        assert len(tracker.threads) == 1
        assert tracker.threads[0].last_mentioned_turn == 5

    def test_dormancy(self):
        tracker = ThreadTracker()
        tracker.add_thread("Old quest", turn=1)
        tracker.check_dormancy(current_turn=15)
        assert len(tracker.get_dormant()) == 1
        assert len(tracker.get_active()) == 0

    def test_reactivation(self):
        tracker = ThreadTracker()
        tracker.add_thread("Old quest", turn=1)
        tracker.check_dormancy(current_turn=15)
        assert tracker.threads[0].status == "dormant"

        # Mentioning it again reactivates
        tracker.mention_thread("Old quest", turn=15)
        assert tracker.threads[0].status == "active"

    def test_resolve(self):
        tracker = ThreadTracker()
        tracker.add_thread("Side quest", turn=1)
        tracker.resolve_thread("Side quest")
        assert tracker.threads[0].status == "resolved"
        assert len(tracker.get_all_unresolved()) == 0

    def test_serialization(self):
        tracker = ThreadTracker()
        tracker.add_thread("Quest A", turn=1, priority=8)
        tracker.add_thread("Quest B", turn=3, priority=5)

        data = tracker.to_list()
        restored = ThreadTracker.from_list(data)
        assert len(restored.threads) == 2
        assert restored.threads[0].title == "Quest A"

    def test_thread_directive(self):
        tracker = ThreadTracker()
        tracker.add_thread("Find the gem", turn=1, priority=7)
        tracker.add_thread("Strange symbols", turn=2)
        tracker.check_dormancy(current_turn=15)

        directive = build_thread_directive(
            tracker.get_active(), tracker.get_dormant(), current_turn=15
        )
        assert "Find the gem" in directive or "Strange symbols" in directive


# ---------------------------------------------------------------------------
# Phase 2.3: NPC Registry
# ---------------------------------------------------------------------------

class TestSoloNPCRegistry:
    """Test NPC tracking for solo play."""

    def test_register(self):
        registry = SoloNPCRegistry()
        registry.register("Durnan", turn=1, disposition="friendly", motivation="Run the inn")
        assert len(registry.get_all()) == 1
        assert registry.npcs["durnan"].motivation == "Run the inn"

    def test_update_existing(self):
        registry = SoloNPCRegistry()
        registry.register("Durnan", turn=1, disposition="friendly")
        registry.register("Durnan", turn=5, disposition="neutral", motivation="Hide something")
        assert len(registry.get_all()) == 1
        assert registry.npcs["durnan"].disposition == "neutral"
        assert registry.npcs["durnan"].last_seen_turn == 5

    def test_active_agents(self):
        registry = SoloNPCRegistry()
        registry.register("Durnan", turn=1, motivation="Run the inn")
        registry.register("Guard", turn=8, motivation="Patrol the streets")

        # At turn 10, Durnan unseen for 9 turns (>5 threshold)
        agents = registry.get_active_agents(current_turn=10)
        assert len(agents) == 1
        assert agents[0].name == "Durnan"

    def test_no_motivation_no_agent(self):
        """NPCs without motivations don't generate autonomous activity."""
        registry = SoloNPCRegistry()
        registry.register("Random Guy", turn=1)
        agents = registry.get_active_agents(current_turn=20)
        assert len(agents) == 0

    def test_serialization(self):
        registry = SoloNPCRegistry()
        registry.register("Durnan", turn=1, disposition="friendly", motivation="Run inn")
        registry.register("Thief", turn=3, disposition="hostile", motivation="Steal gems")

        data = registry.to_list()
        restored = SoloNPCRegistry.from_list(data)
        assert len(restored.get_all()) == 2

    def test_npc_activity_directive(self):
        registry = SoloNPCRegistry()
        registry.register("Durnan", turn=1, disposition="friendly", motivation="Run the inn")
        agents = registry.get_active_agents(current_turn=10)
        directive = build_npc_activity_directive(agents, current_turn=10)
        assert "Durnan" in directive
        assert "Run the inn" in directive


# ---------------------------------------------------------------------------
# Phase 2.4: Directive Coordinator
# ---------------------------------------------------------------------------

class TestDirectiveCoordinator:
    """Test narrative directive prioritization and capping."""

    def test_cap_at_two(self):
        directives = [
            NarrativeDirective(DirectivePriority.NPC_ACTIVITY, "NPC stuff"),
            NarrativeDirective(DirectivePriority.CHAOS_EVENT, "Chaos stuff"),
            NarrativeDirective(DirectivePriority.DORMANT_THREAD, "Thread stuff"),
            NarrativeDirective(DirectivePriority.ORACLE, "Oracle stuff"),
        ]
        active, queued = coordinate_directives(directives)
        assert len(active) == 2
        assert len(queued) == 2
        # Oracle (1) and Chaos (2) should be active (highest priority)
        assert "Oracle stuff" in active
        assert "Chaos stuff" in active

    def test_fewer_than_max(self):
        directives = [
            NarrativeDirective(DirectivePriority.ORACLE, "Oracle stuff"),
        ]
        active, queued = coordinate_directives(directives)
        assert len(active) == 1
        assert len(queued) == 0

    def test_empty(self):
        active, queued = coordinate_directives([])
        assert active == []
        assert queued == []


# ---------------------------------------------------------------------------
# Phase 3.1: Faction Tracker
# ---------------------------------------------------------------------------

class TestFactionTracker:
    """Test faction dynamics tracking."""

    def test_register(self):
        tracker = FactionTracker()
        tracker.register("Iron Brotherhood", goals="Control the docks", power_level=4)
        assert len(tracker.get_active()) == 1

    def test_tick_generates_hints(self):
        tracker = FactionTracker()
        tracker.register("Iron Brotherhood", goals="Control the docks", turn=0)
        # No hints until interval passes
        hints = tracker.tick(current_turn=3)
        assert len(hints) == 0
        # After interval (5 turns)
        hints = tracker.tick(current_turn=5)
        assert len(hints) == 1
        assert "Iron Brotherhood" in hints[0]

    def test_serialization(self):
        tracker = FactionTracker()
        tracker.register("Guild", goals="Profit", power_level=3, disposition="neutral")
        data = tracker.to_list()
        restored = FactionTracker.from_list(data)
        assert len(restored.get_active()) == 1

    def test_faction_directive(self):
        hints = ["The Iron Brotherhood is recruiting mercenaries."]
        directive = build_faction_directive(hints)
        assert "WORLD MOVEMENT" in directive
        assert "Iron Brotherhood" in directive


# ---------------------------------------------------------------------------
# Phase 2.0: Session Serialization
# ---------------------------------------------------------------------------

class TestSessionSerialization:
    """Test SoloSession to/from dict for MongoDB persistence."""

    def test_round_trip(self):
        session = SoloSession(
            discord_user_id=100,
            thread_id=200,
            character_name="Victor",
            current_location="Docks",
            session_number=3,
            chaos_factor=7,
            active_consequences=["Broken arm", "Debt to Durnan"],
        )
        session.push_snapshot(SoloTurnSnapshot(
            turn_number=1,
            history_snapshot=[{"text": "test", "base_impact": 5, "turns_ago": 0}],
            location_before="Market",
            player_input="I look around",
        ))

        d = session.to_dict()
        restored = SoloSession.from_dict(d)

        assert restored.character_name == "Victor"
        assert restored.chaos_factor == 7
        assert len(restored.active_consequences) == 2
        assert len(restored.snapshot_stack) == 1
        assert restored.snapshot_stack[0].turn_number == 1

    def test_snapshot_schema_versioning(self):
        """Snapshots with wrong schema version should be skipped."""
        data = {
            "discord_user_id": 100,
            "thread_id": 200,
            "character_name": "Victor",
            "current_location": "Docks",
            "session_number": 3,
            "snapshot_stack": [
                {
                    "turn_number": 1,
                    "history_snapshot": [],
                    "location_before": "Market",
                    "player_input": "old",
                    "schema_version": 999,  # Wrong version
                },
                {
                    "turn_number": 2,
                    "history_snapshot": [],
                    "location_before": "Docks",
                    "player_input": "current",
                    "schema_version": SNAPSHOT_SCHEMA_VERSION,
                },
            ],
        }
        session = SoloSession.from_dict(data)
        # Only the valid snapshot should be restored
        assert len(session.snapshot_stack) == 1
        assert session.snapshot_stack[0].turn_number == 2


# ---------------------------------------------------------------------------
# Phase 3.2a: Multi-Turn Undo Stack
# ---------------------------------------------------------------------------

class TestMultiTurnUndo:
    """Test the snapshot stack for multi-turn undo."""

    def test_push_pop(self):
        session = SoloSession(
            discord_user_id=100, thread_id=200,
            character_name="Victor", current_location="Docks", session_number=3,
        )
        for i in range(3):
            session.push_snapshot(SoloTurnSnapshot(
                turn_number=i + 1,
                history_snapshot=[],
                location_before=f"Location_{i}",
                player_input=f"Action {i}",
            ))

        assert len(session.snapshot_stack) == 3

        snap = session.pop_snapshot()
        assert snap.turn_number == 3
        assert len(session.snapshot_stack) == 2

    def test_max_depth(self):
        session = SoloSession(
            discord_user_id=100, thread_id=200,
            character_name="Victor", current_location="Docks", session_number=3,
        )
        for i in range(MAX_SNAPSHOT_DEPTH + 3):
            session.push_snapshot(SoloTurnSnapshot(
                turn_number=i + 1,
                history_snapshot=[],
                location_before=f"Loc_{i}",
                player_input=f"Action {i}",
            ))

        assert len(session.snapshot_stack) == MAX_SNAPSHOT_DEPTH
        # Oldest should have been dropped
        assert session.snapshot_stack[0].turn_number == 4  # 1,2,3 dropped

    def test_pop_empty(self):
        session = SoloSession(
            discord_user_id=100, thread_id=200,
            character_name="Victor", current_location="Docks", session_number=3,
        )
        assert session.pop_snapshot() is None

    def test_last_snapshot_property(self):
        session = SoloSession(
            discord_user_id=100, thread_id=200,
            character_name="Victor", current_location="Docks", session_number=3,
        )
        assert session.last_snapshot is None

        session.push_snapshot(SoloTurnSnapshot(
            turn_number=1, history_snapshot=[], location_before="X", player_input="Y",
        ))
        assert session.last_snapshot is not None
        assert session.last_snapshot.turn_number == 1


# ---------------------------------------------------------------------------
# Phase 3.2b: Session Timeout
# ---------------------------------------------------------------------------

class TestSessionTimeout:
    """Test session timeout detection."""

    @pytest.fixture
    def manager(self):
        return SoloSessionManager()

    @pytest.mark.asyncio
    async def test_no_timeout_fresh(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        assert len(manager.get_timed_out_sessions()) == 0

    @pytest.mark.asyncio
    async def test_timeout_old_session(self, manager):
        session = await manager.start_session(100, 200, "Victor", "Docks", 3)
        # Simulate old activity (3 hours ago)
        session.last_activity = time.time() - (3 * 3600)
        timed_out = manager.get_timed_out_sessions()
        assert len(timed_out) == 1
        assert timed_out[0].character_name == "Victor"

    @pytest.mark.asyncio
    async def test_touch_prevents_timeout(self, manager):
        session = await manager.start_session(100, 200, "Victor", "Docks", 3)
        session.last_activity = time.time() - (3 * 3600)
        session.touch()  # Update activity
        assert len(manager.get_timed_out_sessions()) == 0


# ---------------------------------------------------------------------------
# Phase 4.1: Merge Summary
# ---------------------------------------------------------------------------

class TestMergeSummary:
    """Test solo → campaign merge summary generation."""

    def test_basic_merge(self):
        session_data = {
            "character_name": "Victor",
            "current_location": "Dark Forest",
            "turn_count": 12,
            "active_consequences": ["Broken arm"],
            "encountered_npcs": [
                {"name": "Durnan", "disposition": "friendly", "motivation": "Run the inn"},
            ],
            "active_threads": [
                {"title": "Find the gem", "status": "active", "priority": 7},
                {"title": "Rescue villager", "status": "resolved", "priority": 5},
            ],
        }
        summary = generate_merge_summary(session_data)
        assert summary["character"] == "Victor"
        assert summary["final_location"] == "Dark Forest"
        assert len(summary["consequences"]) == 1
        assert len(summary["encountered_npcs"]) == 1
        assert len(summary["active_threads"]) == 1
        assert len(summary["resolved_threads"]) == 1

    def test_recap_for_group(self):
        summary = {
            "character": "Victor",
            "final_location": "Dark Forest",
            "consequences": ["Broken arm"],
            "encountered_npcs": [{"name": "Durnan"}],
            "active_threads": [{"title": "Find the gem"}],
        }
        recap = build_solo_recap_for_group(summary)
        assert "Victor" in recap
        assert "Dark Forest" in recap
        assert "Broken arm" in recap
        assert "Durnan" in recap
        assert "Find the gem" in recap


# ---------------------------------------------------------------------------
# Phase 2.2: Thread Extraction from Chronicler
# ---------------------------------------------------------------------------

class TestThreadExtraction:
    """Test heuristic thread extraction from chronicler output."""

    def test_quest_update_extraction(self):
        chronicler = {
            "quest_updates": [
                {"name": "Retrieve the Lost Amulet", "status": "active"},
            ],
        }
        threads = extract_threads_from_chronicler(chronicler, "narrative", 5)
        assert len(threads) >= 1
        assert any(t["title"] == "Retrieve the Lost Amulet" for t in threads)

    def test_npc_quest_keyword(self):
        chronicler = {
            "npc_updates": [
                {"name": "Durnan", "notes": "wants to find his missing daughter"},
            ],
        }
        threads = extract_threads_from_chronicler(chronicler, "narrative", 5)
        assert len(threads) >= 1

    def test_location_exploration(self):
        chronicler = {
            "scene_changes": {"location_changed": True, "new_location": "Dark Cave"},
        }
        threads = extract_threads_from_chronicler(chronicler, "narrative", 5)
        assert any("Dark Cave" in t.get("title", "") for t in threads)


# ---------------------------------------------------------------------------
# Phase 2.3: NPC Extraction from Chronicler
# ---------------------------------------------------------------------------

class TestNPCExtraction:
    """Test NPC data extraction from chronicler output."""

    def test_npc_update_extraction(self):
        chronicler = {
            "npc_updates": [
                {"name": "Durnan", "disposition": "friendly", "location": "Tavern",
                 "notes": "wants to protect the portal"},
            ],
        }
        npcs = extract_npcs_from_chronicler(chronicler, current_turn=5)
        assert len(npcs) == 1
        assert npcs[0]["name"] == "Durnan"
        assert npcs[0]["disposition"] == "friendly"

    def test_new_npc_extraction(self):
        chronicler = {
            "new_npcs": [
                {"name": "Shadow Thief", "disposition": "hostile",
                 "location": "Alley", "personality": "Cunning and greedy"},
            ],
        }
        npcs = extract_npcs_from_chronicler(chronicler, current_turn=3)
        assert len(npcs) == 1
        assert npcs[0]["name"] == "Shadow Thief"
        assert npcs[0]["motivation"] == "Cunning and greedy"


# ---------------------------------------------------------------------------
# Phase 4.3: Concurrent Play Guards
# ---------------------------------------------------------------------------

class TestConcurrentPlayGuards:
    """Test character-level concurrent play guards."""

    @pytest.fixture
    def manager(self):
        return SoloSessionManager()

    @pytest.mark.asyncio
    async def test_get_by_character(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        session = manager.get_by_character("Victor")
        assert session is not None
        assert session.character_name == "Victor"

    @pytest.mark.asyncio
    async def test_get_by_character_case_insensitive(self, manager):
        await manager.start_session(100, 200, "Victor", "Docks", 3)
        assert manager.get_by_character("victor") is not None
        assert manager.get_by_character("VICTOR") is not None

    @pytest.mark.asyncio
    async def test_get_by_character_missing(self, manager):
        assert manager.get_by_character("Nobody") is None
