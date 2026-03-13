# Solo Enhancement + Session Quality Overhaul — Change Notes

**Date:** 2026-03-09
**Branch:** main (3 prior commits unpushed + all uncommitted changes below)
**Scope:** Solo mode phases 0-4, session wrapup automation, campaign data fixes

---

## What This Changes (Summary)

Solo play went from a basic "private thread + AI DM" to a full standalone experience with:
- Per-session history isolation (no more cross-session corruption)
- Oracle grading (graduated outcomes, not binary pass/fail)
- Chaos factor (escalating tension with random events)
- Thread/quest tracking, NPC autonomy, faction dynamics
- Multi-turn undo, session timeout, MongoDB persistence
- Rich session openers with character context and recap
- Automatic end-of-session cleanup (log dedup, NPC file creation, note consolidation)
- Solo ↔ party integration (merge summaries, concurrent play guards)

---

## New Files

| File | Lines | Purpose |
|------|-------|---------|
| `tools/solo_session.py` | ~260 | SoloSession model, SoloSessionManager, snapshots, persistence |
| `tools/solo_engine.py` | ~280 | Oracle grading, chaos tracker, narrative directive coordinator |
| `tools/solo_world.py` | ~380 | Thread tracker, NPC registry, faction tracker, heuristic extractors |
| `tools/solo_merge.py` | ~200 | Solo → campaign merge summaries, campaign context for solo startup |
| `tools/session_wrapup.py` | ~300 | Post-session cleanup: log dedup, NPC creation sweep, note consolidation |
| `tools/pipeline_metrics.py` | ~100 | In-memory pipeline health metrics (request counts, latency, errors) |
| `bot/cogs/solo_cog.py` | ~640 | `/solo`, `/solo_end`, `/solo_undo` slash commands, rich opener |
| `bot/cogs/monitoring_cog.py` | ~210 | `/bot-status`, `/solo-sessions` monitoring commands |
| `models/character_knowledge.py` | ~60 | CharacterInsight + CharacterKnowledge Pydantic schemas |
| `tests/test_solo_session.py` | ~150 | Unit tests for SoloSession model and manager |
| `tests/test_solo_integration.py` | ~480 | 65 integration tests across 14 test classes |
| `tests/test_pipeline_metrics.py` | ~80 | Pipeline metrics tests |
| `tests/test_location_context.py` | ~60 | Location context assembly tests |
| `campaign_vault/02 - NPCs/Bruenor.md` | ~40 | New NPC: dwarf veteran ally |
| `campaign_vault/02 - NPCs/Willum.md` | ~40 | New NPC: nervous youth with map |

## Modified Files — Code

### `bot/client.py` (+306 lines)
- **`_handle_solo_message()`** — Complete rewrite. Per-session history isolation, processing lock acquisition, `push_snapshot()` for multi-turn undo, `_solo_thread_id` in pipeline state.
- **`_solo_post_process()`** — NEW. Rebuilds chaos/thread/NPC/faction trackers from session state after each pipeline run. Assesses chaos from chronicler output, extracts threads and NPCs via heuristics.
- **`_solo_session_timeout_checker()`** — NEW. Background task (30 min interval), auto-ends sessions idle >2 hours.
- **`on_ready()`** — Sets `solo_manager._state_manager`, calls `restore_active()`, launches timeout checker.
- Added `_nullcontext()` async context manager for lock acquisition fallback.

### `pipeline/nodes/storyteller_node.py` (+206 lines)
- **Solo guardrails expanded** with `[SOLO COMBAT SCALING]` and `[SOLO DEATH ALTERNATIVES]` prompt blocks.
- **`_build_solo_kwargs()`** — NEW. Gathers per-session history and narrative directives for solo storyteller calls.
- **`_build_solo_directives()`** — NEW. Computes chaos/thread/NPC/faction directives from session state, coordinates via max-2 cap.
- **`_inject_oracle_grade()`** — NEW. Reads dice_results from rules ruling, grades outcome, appends oracle text ("Yes, and...", "Yes, but...", etc.) to player input.
- Storyteller call now passes `**solo_kwargs` through to `process_request()`.

### `agents/storyteller.py` (+120 lines)
- `process_request()` signature expanded: `solo_history=None`, `solo_directives=None`, `solo_recap=None`.
- Solo context call passes these through to `build_solo_storyteller_context()`.

### `agents/chronicler.py` (+34 lines)
- Chronicler node now passes `_chronicler_output` through pipeline state for solo post-processing.

### `tools/context_assembler.py` (+197 lines)
- `build_solo_storyteller_context()` — Added `history`, `solo_directives`, `recap` parameters.
- Section 0: Session recap injection.
- Section 5: Per-session history via `_build_solo_history_section(character_name, history=history)`.
- Section 7: Solo narrative directives block.
- `_build_character_knowledge_section()` — NEW. Feeds accumulated character knowledge into storyteller context.

### `tools/vault_manager.py` (+216 lines)
- **`get_latest_solo_log()`** — NEW. Finds most recent solo log for a character.
- **`append_to_session_log()` — BUGFIX.** Fixed heading detection that caused events to land below `## DM Notes`. Now uses `re.search()` with `re.MULTILINE` and properly skips table header rows.
- Solo log methods: `append_to_solo_log()`, `get_latest_solo_log()`.
- Character knowledge methods for dual-write (vault + MongoDB).

### `tools/state_manager.py` (+52 lines)
- `character_knowledge` MongoDB collection support.
- `get_all_npcs()` method for session wrapup NPC sweep.

### `bot/views/admin_views.py` (+27 lines)
- **End Session button** now calls `run_session_wrapup()` after summary, before session increment.
- Admin gets wrapup results in the ephemeral confirmation message.

### `pipeline/state.py` (+4 lines)
- Added `_solo_thread_id: Optional[int]` and `_chronicler_output: Optional[Dict[str, Any]]` to GameState.

### `pipeline/nodes/rules_node.py` (+18 lines)
- Solo guardrails expanded with death alternative instruction.

### `pipeline/nodes/chronicler_node.py` (+13 lines)
- Passes `_chronicler_output` through pipeline state for solo post-processing.

### `pipeline/graph.py` (+36 lines)
- `_timed_node()` wrapper for per-node latency tracking.
- Pipeline metrics integration.

### `models/chronicler_output.py` (+3 lines)
- `character_insights: List[CharacterInsight]` field on `ChroniclerOutput`.

### `bot/cogs/solo_cog.py` (this session's changes)
- **`/solo` command** — Added optional `character:` parameter (admin-only override for testing).
- **Welcome embed** — Rich character brief: tagline, HP/AC/Level, toolkit (abilities + spells + slots), notable gear, personality drive, recap.
- **Opening prompt** — Rich context blocks: `[CHARACTER]`, `[PERSONALITY]`, `[CAPABILITIES]`, `[RECAP]`. Explicit instructions for the storyteller to include "Previously on...", scene description, 2-3 hooks, and an action-demanding ending.
- **`_build_character_brief()`** — NEW. Pulls character sheet data (stats, abilities, spells, inventory, personality) into a structured dict for embed and prompt.
- **`_build_opening_prompt()`** — NEW. Constructs the rich opening prompt with all context blocks.

### `bot/cogs/monitoring_cog.py`
- Renamed `bot_status` method to `system_status` (Discord.py 2.x naming restriction — methods can't start with `bot_` or `cog_`).

## Modified Files — Campaign Data

### `campaigns/Default/00 - Session Log/Session 000.md`
- **Complete rewrite.** Cleaned up from raw chronicler dump to structured, chronological, deduplicated session log. Filtered inappropriate content from SonOfThunder. Added combat encounters, decisions & consequences, loot, notable quotes, DM notes sections.

### `campaigns/Default/06 - World State/memory_checkpoint.json`
- **Curated to 14 entries** reflecting the actual session arc (troll → recruiting → docks → Finnigan lead). Removed 73+ raw entries with duplicates and stale data.

### `knowledge/storyteller_context.md`
- **Complete rewrite.** Updated from stale "Frognar + Kallisar 2-player party fighting a troll" to actual 4-player roster (Hadrian, Victor, Sigfried, Kallisar) with correct classes, personalities, and pronouns. Updated current situation to docks/fish market, active NPCs (Bruenor, Willum, Durnan), and next narrative action (find Fingers Finnigan).

### `campaigns/Default/01 - Party/Kallisar Voidcaller.md`
- Set `pronouns: he/him` (was empty — caused misgendering).

### `campaigns/Default/01 - Party/Victor Saltzpyre.md`
- Fixed `player: Ember` → `player: SonOfThunder` (Ember is Hadrian's player).
- Set `pronouns: he/him`.

### `campaigns/Default/02 - NPCs/Durnan.md`
- Updated "Party Relationship" from "Not yet met" to actual session interactions.

### `CLAUDE.md`
- Added Solo Mode, Character Knowledge, Pipeline Monitoring, and Session Wrapup documentation sections.

### `docs/` (DM_GUIDE, PLAYER_GUIDE, GETTING_STARTED, etc.)
- Updated with solo mode documentation, commands, and workflow descriptions.

---

## Architecture Decisions Worth Preserving

These decisions should inform the party mode overhaul:

### 1. Prompt-First, Code-Second
Combat scaling and death alternatives are **prompt guardrails**, not code mechanics. The LLM already knows character levels and encounter balance. Code only gets added if playtesting proves prompts insufficient. This avoids premature abstraction.

### 2. No Chronicler Schema Expansion
All new data extraction (threads, NPC autonomy, factions, chaos assessment) uses **Python post-processing** of existing `ChroniclerOutput` fields (`npc_updates`, `scene_changes`, `character_updates`). No new LLM extraction arrays. This keeps the chronicler's job simple and the output schema stable.

### 3. Per-Session History Isolation
Each solo session owns its own `ConversationHistory` instance stored on the **manager** (not the Pydantic model). This prevents concurrent sessions from corrupting each other. The same pattern should apply to party mode if we ever support multiple concurrent game tables.

### 4. Processing Locks on Manager, Not Model
`asyncio.Lock` per thread_id lives on `SoloSessionManager._processing_locks`, not on `SoloSession`. Asyncio primitives aren't Pydantic-serializable, so they can't go on models that need `to_dict()`/`from_dict()`.

### 5. Narrative Directive Cap
Max 2 active system directives per turn (e.g., chaos event + oracle grade). Prevents incoherent storyteller output from 4+ competing instructions. Priority order: oracle > chaos > dormant threads > NPC activity > factions.

### 6. Non-Blocking Wrapup
Session wrapup steps are independently try/excepted. A failed NPC consolidation doesn't block session log cleanup. The session always ends cleanly regardless of wrapup success.

### 7. Atomic File Writes
Merge files use `tempfile.NamedTemporaryFile` + `os.replace()` pattern. Prevents corrupt vault files from interrupted writes.

---

## What Party Mode Needs (Comparison)

| Feature | Solo (Done) | Party (Current State) |
|---------|-------------|----------------------|
| **History isolation** | Per-session ConversationHistory | Single shared global history |
| **Processing locks** | Per-thread asyncio.Lock | `_pipeline_semaphore` (global) |
| **Oracle grading** | Full graduated outcomes | Binary pass/fail from rules lawyer |
| **Session opener** | Rich character brief + recap + hooks | "Session N Begins" + basic recap |
| **End-of-session cleanup** | Auto log dedup, NPC creation, note consolidation | Manual — summary only |
| **Character context in prompts** | `[CHARACTER]`, `[PERSONALITY]`, `[CAPABILITIES]` blocks | Party section from vault (name + HP only) |
| **Directive system** | Chaos, threads, NPCs, factions with max-2 cap | None — storyteller gets raw context |
| **Undo** | Multi-turn stack (max 5) | None |
| **NPC relationship tracking** | Per-turn chronicler notes + session consolidation | Raw chronicler dumps accumulate |
| **Session log quality** | Auto-cleaned at session end | Raw event rows, duplicates, wrong sections |
| **Concurrent safety** | Per-session history + locks | Global history, single semaphore |

### Priority Items for Party Mode Overhaul
1. **Session wrapup already applies to party** — log cleanup, NPC creation, note consolidation run on End Session for both modes.
2. **Rich session opener** — Port `_build_character_brief()` logic to the Start Session button. Show each player their character status in the opening embed.
3. **Oracle grading for party** — The `_inject_oracle_grade()` function works on any `dice_results` in the rules ruling. Wire it into the party storyteller path.
4. **Session log insertion fix already applies to party** — The `append_to_session_log()` bugfix prevents events from landing below DM Notes in all future sessions.
5. **NPC relationship consolidation** — Already runs for all NPC files at end of any session.

### What Party Mode Should NOT Copy from Solo
- **Chaos factor / thread tracker / faction tracker** — These are Mythic GM Emulator mechanics for solo play. Party play has a human DM managing pacing.
- **Death alternatives prompt** — Party play should allow character death (the human DM decides consequences).
- **World clock freeze** — Party play advances time normally.

---

## Playtest Findings & Fixes (Mar 10)

Live playtested Hadrian Goldhammer solo session (4+ turns, stealth/deception/combat scenarios).

### Bugs Found & Fixed

1. **`gemini-2.0-flash` deprecated** — Google deprecated the model ~Mar 2026. Router, chronicler, scene classifier, board monitor all failed silently. Fixed: `MODEL_ID = "gemini-2.5-flash"` in `bot/client.py`. Storyteller stays on `gemini-2.5-pro`.

2. **`ConsequenceEntry.trigger_session` validation** — LLM returned `null` for required `int` field, Pydantic rejected it. Fixed: `Optional[int]` with `default=None` in both `chronicler_output.py` and `world_state.py`.

3. **Undone chaos events leaking into memory** — Chaos event (magical fog) from an undone turn persisted in the global memory checkpoint. Rules lawyer read it and treated as fact, contaminating all subsequent turns. Root cause: dual-write to global checkpoint + per-session history, but undo only restored per-session. Fixed: **solo events skip global checkpoint entirely** — `chronicler_node.py` guards `save_checkpoint()` with `if not is_solo`, `chronicler.py` guards `record_event()` and `advance_turn()` with `if not is_solo`.

4. **Solo log corruption across restarts** — Multiple Turn 0 entries appended to same file when bot restarted mid-session. Fixed: unique sub-session log naming with counter (`{Name}_Solo_S003.md`, `{Name}_Solo_S003_2.md`).

5. **Starting location wrong** — World clock had no `current_location` field, defaulted to "The Yawning Portal" instead of party's actual location. Fixed: added `current_location: Waterdeep Docks` to `clock.md` frontmatter.

### Chaos System Tuning

Original chaos was too aggressive — an environment_shift event at factor 5 had a 50% trigger chance and could completely derail the scene (replacing player's action with magical fog).

**Changes made:**
- Trigger threshold: `roll <= factor` → `roll <= factor - 2` (30% at factor 5, 0% below factor 3)
- INTERRUPTED scenes disabled entirely — only ALTERED remains
- Directive language softened: "weave an unexpected twist INTO the current scene" instead of "replace the scene"
- Event type descriptions softened: "a minor wrinkle", "flavor, not a new scene", "a hook, not a redirect", "a thread tug, not a yank"
- **Key principle:** Chaos should influence and add texture, never derail what the player is doing

### Oracle System — Confirmed Working

- Stealth 25 (beat DC by 5+) → "Yes, and..." (invisible, discovered bonus information)
- Perception 4 (miss by 10+) → Critical failure (can't hear anything)
- Deception 16 (meet DC) → "Yes" (bluff worked, skepticism remained)
- Deception 21 (beat DC by 5+) → "Yes, and..." (bluff shattered enemy confidence, gas lamps died dramatically)

### Model Change — Rules Lawyer

Switched from `gemini-2.5-pro` to `gemini-2.5-flash` for the rules lawyer. Mechanical adjudication (DC checks, skill modifiers, rule lookups) is structured reasoning that Flash handles well. Pro's creative advantage matters more for storytelling. Should noticeably reduce pipeline latency.

### Auto-NPC Creation — Confirmed Working

- Grigor.md and Finn.md auto-created from chronicler output during solo play
- Dedup working correctly ("Grigor already exists — skipping creation")
- Storyteller pulled from Hadrian's personality bond ("I owe my survival to another urchin") to create Finn as that urchin — character knowledge feeding back into narrative

---

## Multiplayer Adaptation Notes

### Oracle Grading → Party Mode

The oracle system (`_inject_oracle_grade()` in `storyteller_node.py`) is **directly portable** to party mode:
- It reads `dice_results` from the rules ruling (already produced in party mode)
- It grades against DC thresholds (universal mechanic)
- It injects "Yes, and..." / "Yes, but..." / "No, but..." / "No, and..." into storyteller context
- **For party:** Apply to each player's action independently. When multiple players roll in a batch, each gets their own oracle grade. The storyteller weaves all grades into a single narrative.
- **Adjustment needed:** In party mode, the directive cap should be relaxed slightly (3 instead of 2) since multi-player scenes need more narrative threads.

### Chaos Factor → Party Mode (with modifications)

The chaos system is a **Mythic GM Emulator** mechanic designed for solo play where there's no human DM managing pacing. For party mode, it needs significant adaptation:

- **Don't use random events** — the human admin controls pacing via Queue Mode
- **DO use scene alteration** as a "DM inspiration" system: when the storyteller starts a new scene, suggest an unexpected twist with low probability. Show it to the admin via the console, not auto-applied.
- **DO use chaos factor as a narrative tension tracker** — rises during combat/danger, falls during rest/shopping. Feed it to the storyteller as a tone guide: "Current tension: 7/9 — descriptions should feel urgent, NPCs should be on edge"
- **Trigger threshold should be even lower for party** (factor - 3, not factor - 2) since human players create enough chaos on their own
- **Key files to modify:** `bot/client.py` (`_handle_game_table`), `pipeline/nodes/storyteller_node.py` (add party directive builder), `tools/solo_engine.py` (extract `ChaosTracker` into shared utility)

### Thread/NPC/Faction Tracking → Party Mode

These heuristic post-processing systems (`solo_world.py`) are **valuable for party mode**:
- Thread tracker catches quest hooks the chronicler mentions but doesn't formally register
- NPC registry tracks disposition changes across sessions
- Faction tracker creates "world in motion" background events
- **For party:** These should feed into the admin console as "suggested hooks" rather than auto-injecting into storyteller context. The admin decides which to activate.

---

## Phase 2 — Pause/Resume & Quality of Life (Mar 11)

### Pause/Resume Feature

Players can now `/solo_pause` a session and pick it up later with `/solo`. All live state is serialized to MongoDB as "cold storage" — zero runtime memory consumed while paused.

**Three-state session lifecycle:** active (in-memory + MongoDB) → paused (MongoDB only) → ended (deleted from both).

**Files modified:**

#### `tools/solo_session.py`
- Added `is_paused: bool` and `conversation_history_data: List[dict]` fields to `SoloSession`
- Updated `to_dict()` / `from_dict()` to persist new fields
- `pause_session()` — serializes full `ConversationHistory` entries, sets `is_paused=True`, persists to MongoDB, removes from active memory (frees `_sessions`, `_processing_locks`, `_histories`)
- `resume_session()` — queries MongoDB for paused doc, rebuilds `SoloSession` + `ConversationHistory` from stored data, registers in active memory, clears serialized history
- `get_paused_session()` — queries MongoDB for paused sessions by user ID and/or character name (case-insensitive regex)
- `restore_active()` — now filters `{"is_paused": {"$ne": True}}` so paused sessions stay dormant on bot restart
- `MAX_SNAPSHOT_DEPTH` raised from 5 → 999 for testing phase (unlimited undo)

#### `bot/cogs/solo_cog.py`
- **`/solo_pause` command** — validates thread ownership, checks MongoDB connectivity (returns friendly error if DB is down: "Ask Chase to start MongoDB"), serializes session, posts summary embed with turns/location/open threads, archives the Discord thread
- **`/solo` resume detection** — after resolving character name, checks for paused session in MongoDB. If found: unarchives original thread, resumes session with full context, posts welcome-back message. If thread is gone: deletes stale paused doc, falls through to create new session
- **Double-defer fix** — restructured defer logic so `interaction.response.defer()` only fires once regardless of which branch executes (paused vs. fresh start)
- Updated embed footer to mention `/solo_pause`
- **Thread-nesting guard** — `/solo` now checks `isinstance(interaction.channel, discord.Thread)` and returns a friendly ephemeral error explaining that solo adventures must be started from a regular text channel, with a tip about resume detection. Prevents `AttributeError: 'Thread' object has no attribute 'create_thread'`

#### What gets preserved on pause

| State | How |
|-------|-----|
| Turn count, location | `SoloSession` fields in MongoDB |
| Full conversation history | Serialized to `conversation_history_data` |
| Chaos factor | `SoloSession.chaos_factor` |
| Active story threads | `SoloSession.active_threads` |
| Encountered NPCs | `SoloSession.encountered_npcs` |
| Faction state | `SoloSession.factions` |
| Active consequences | `SoloSession.active_consequences` |
| Full undo stack | `SoloSession.snapshot_stack` |
| Queued directives | `SoloSession.queued_directives` |
| Discord message history | Thread unarchived on resume |
| Solo vault log | Vault file persists; new turns append |

### Quality of Life Improvements

#### `bot/client.py`
- **Inquiry mode** — rules lawyer can now return `INQUIRY:` responses (lore questions, hypotheticals) that bypass the storyteller and reply directly. Detected via prefix match on `rules_ruling`.
- **`_send_chunked()`** — NEW helper. Splits long narratives at paragraph boundaries (2000 char Discord limit) instead of mid-sentence. Used by solo message handler and solo opener.
- **Opening scene chunking** — rich opening scenes from the storyteller are now sent via `_send_chunked()` instead of being truncated at 2000 chars.

#### `bot/cogs/solo_cog.py`
- **Recap truncation** — `_get_recent_recap()` now truncates at 800 chars (from unlimited) to prevent the opening prompt from exceeding context limits on long sessions.

#### `agents/rules_lawyer.py`
- **Labeled ability checks** — rules lawyer now specifies which ability/skill each check uses (e.g., "Stealth (Dexterity)" instead of just "DC 15"). Helps oracle grading and player understanding.

#### `tools/solo_session.py`
- **Session timeout** — `SESSION_TIMEOUT_HOURS` changed from 2 → 24 hours. Two hours was too aggressive for players who step away.

#### `tests/test_solo_integration.py`
- Updated timeout test values from `3 * 3600` to `25 * 3600` to match new 24-hour timeout.

### Architecture Decision: MongoDB Guard on Pause

`/solo_pause` requires MongoDB connectivity. Without it, the session would be removed from active memory but never persisted — effectively lost. The guard checks `state_manager.is_connected` and returns a friendly error directing the player to ask Chase to start the database. This is safer than silently losing state.

---

## Narrative Continuity Fix (Mar 12)

Solo sessions suffered from severe continuity breaks: NPC physical details flipping between turns, objects teleporting between holders, NPCs named without introduction, and similes repeating verbatim across turns. Root cause: each storyteller call is a separate LLM invocation with no memory of its own previous prose, and NPC vault descriptions were fetched but discarded.

### Phase 1: NPC Descriptions from Vault (immediate impact)

The vault NPC files contain rich descriptions ("A hulking bugbear with thick, sausage-like fingers and dark eyes") but `_build_location_section()` only rendered frontmatter fields (`name`, `role`, `disposition`). The `body` was fetched and thrown away.

**Changes:**

- **`tools/context_assembler.py`** — New `_format_npc_entry()` extracts `## Description` and `## Personality` sections from NPC vault body. Truncates to ~200 chars (description) and ~150 chars (personality). Skips template placeholder text (`_Physical appearance, mannerisms, voice._`). Applied to BOTH `_build_location_section()` and `_build_brief_location_section()` — NPC appearance persists even on "[SAME LOCATION]" turns.
- **`agents/storyteller.py`** — Added `SCENE CONTINUITY (non-negotiable)` block to `STORYTELLER_IDENTITY`: NPC descriptions are ground truth (match exactly), don't name NPCs without introduction, vary descriptive language (never reuse similes), objects stay where last placed.

### Phase 2: Narrative Sliding Window (high impact)

Stores the last 3-5 turns of full DM narrative prose on the session object and injects into the storyteller context. Gives the LLM its own previous output to reference, preventing both repetition and contradictions. ~2400 tokens added (3 turns x 800 chars). Trivial for Gemini's 1M context window.

**Changes:**

- **`tools/solo_session.py`** — New `recent_narratives: List[dict]` field (each entry: `{turn, player_input, narrative}`). New `push_narrative()` method trims to last 5. Added to `to_dict()`/`from_dict()` for MongoDB persistence.
- **`bot/client.py`** — Calls `session.push_narrative(turn_number, user_input, narrative)` after narrative delivery in `_handle_solo_message()`.
- **`tools/context_assembler.py`** — New `_build_narrative_window()` method renders last 3 turns truncated to ~800 chars each with header "do NOT repeat phrases from here". Wired into `build_solo_storyteller_context()` via new `recent_narratives` parameter.
- **`pipeline/nodes/storyteller_node.py`** — `_build_solo_kwargs()` passes `session.recent_narratives` as `solo_recent_narratives`.
- **`agents/storyteller.py`** — `process_request()` accepts `solo_recent_narratives` kwarg, forwards to context builder.

### Phase 3: Scene State Object (structural fix)

A structured "scene state" extracted by the chronicler after each turn, tracking who's present, what they look like, who holds what, and spatial layout. Injected as ground truth into the next turn's storyteller context. The chronicler receives the previous scene state and updates incrementally — physical descriptions carry forward unless the narrative explicitly changes them.

**New file:**

| File | Purpose |
|------|---------|
| `models/scene_state.py` | `SceneEntity`, `SceneObject`, `SceneState` Pydantic models |

**Changes:**

- **`models/chronicler_output.py`** — Added `scene_state: Optional[Dict[str, Any]]` field to `ChroniclerOutput`.
- **`agents/chronicler.py`** — Extended `CHRONICLER_SCHEMA` with `scene_state` extraction block (entities, objects, spatial notes). Added `SCENE STATE` rules for incremental updates (keep physical descriptions exactly as-is unless narrative explicitly changes). `process_exchange()` accepts `previous_scene_state` and injects it into the chronicler prompt.
- **`tools/solo_session.py`** — Added `scene_state_data: dict` field (persisted to MongoDB via `to_dict()`/`from_dict()`).
- **`pipeline/nodes/chronicler_node.py`** — Loads previous scene state from session via `solo_manager`, passes to `chronicler.process_exchange()`.
- **`bot/client.py`** — Extracts `scene_state` from chronicler output in `_solo_post_process()` and stores on session.
- **`tools/context_assembler.py`** — New `_build_scene_state_section()` renders entities (with physical descriptions, held items, demeanor), objects (with holders), and spatial layout. Wired into `build_solo_storyteller_context()` via new `scene_state` parameter.
- **`pipeline/nodes/storyteller_node.py`** — `_build_solo_kwargs()` passes `session.scene_state_data` as `solo_scene_state`.
- **`agents/storyteller.py`** — `process_request()` accepts `solo_scene_state` kwarg, forwards to context builder.

### Expected Impact

| Problem | Fix Layer |
|---------|-----------|
| NPC description flip-flopping (eye count, build) | Phase 1 (vault descriptions) + Phase 3 (scene state) |
| Object teleportation (note changes holders) | Phase 3 (scene state tracks holders) |
| NPC named without introduction | Phase 1 (prompt rule) |
| Simile repetition ("voice like stones grinding") | Phase 2 (narrative window) + Phase 1 (prompt rule) |
| Relationship hierarchy drift | Phase 3 (scene state tracks roles) |

---

## Test Status

- **293 tests passing** (as of 2026-03-12 post-continuity-fix)
- **82 solo tests** (test_solo_session.py + test_solo_integration.py)
- **All pre-existing tests unaffected**
- 14 pre-existing failures in test_blind_prep/test_cartographer/test_scene_classifier remain (mock/fixture issues, unrelated)

## Files to Stage

**Commit 1 — Solo Engine (core mechanics):**
```
tools/solo_session.py
tools/solo_engine.py
tools/solo_world.py
tools/solo_merge.py
models/character_knowledge.py
pipeline/state.py
tests/test_solo_session.py
tests/test_solo_integration.py
```

**Commit 2 — Pipeline integration:**
```
bot/client.py
pipeline/nodes/storyteller_node.py
pipeline/nodes/rules_node.py
pipeline/nodes/chronicler_node.py
pipeline/graph.py
agents/storyteller.py
agents/chronicler.py
models/chronicler_output.py
tools/context_assembler.py
tools/state_manager.py
```

**Commit 3 — Discord layer + cogs:**
```
bot/cogs/solo_cog.py
bot/cogs/monitoring_cog.py
tools/pipeline_metrics.py
tests/test_pipeline_metrics.py
tests/test_location_context.py
```

**Commit 4 — Session wrapup + vault fixes:**
```
tools/session_wrapup.py
tools/vault_manager.py
bot/views/admin_views.py
```

**Commit 5 — Campaign data + docs:**
```
CLAUDE.md
knowledge/storyteller_context.md
campaigns/Default/00 - Session Log/Session 000.md
campaigns/Default/01 - Party/Kallisar Voidcaller.md
campaigns/Default/01 - Party/Victor Saltzpyre.md
campaigns/Default/02 - NPCs/Durnan.md
campaigns/Default/02 - NPCs/Bruenor.md
campaigns/Default/02 - NPCs/Willum.md
campaigns/Default/06 - World State/memory_checkpoint.json
campaign_vault/ (symlinked copies)
docs/
```
