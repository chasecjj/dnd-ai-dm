# D&D AI DM — Completion Plan

## Current State (After Bug Fixes)

**Fixed:** Chronicler async/await bug (the only remaining critical bug). The RulesLawyer, model versioning, and all other agents were already correct.

**Working:** Discord bot, message routing, storyteller, rules lawyer, board monitor, vault manager (all methods implemented), context assembler with weighted memory, reference manager with populated indices, Foundry VTT relay, all `!` commands, War Room prep pipeline.

**Not yet tested end-to-end:** The full game loop (player message → router → rules → storyteller → chronicler → vault update) should now work with the Chronicler fix, but needs a live test.

---

## Phase 1: Hardening (Get the Core Loop Bulletproof)

### 1.1 — End-to-End Smoke Test
- Start the bot, send a test game action in the Game Table channel
- Verify: Router classifies correctly → Rules Lawyer returns valid JSON → Storyteller generates narrative → Chronicler extracts changes → Vault files update
- **Check the logs** for any remaining errors in the pipeline

### 1.2 — Chronicler Context Enrichment
The Chronicler currently only sees the immediate exchange (player action + ruling + narrative) plus party state and quests. It should also see:
- **Recent history** (so it can detect recurring patterns, like "the party keeps ignoring this quest")
- **Location context** (so it knows WHERE events happen for the session log)

**File:** `tools/context_assembler.py` → `build_chronicler_context()`
**Change:** Add `self._build_location_section()` and `self._build_history_section()` to the chronicler context.

### 1.3 — Session Log Auto-Creation
When the bot starts (or when `current_session` increments), it should create a new session log file from the template if one doesn't exist yet. Currently `append_to_session_log` creates a bare file if missing, but it doesn't use the template's frontmatter properly.

**File:** `tools/vault_manager.py` → `append_to_session_log()`
**Change:** When creating a new session file, populate the frontmatter with `session_number`, `ingame_date` (from world clock), and `location` (from last known location).

---

## Phase 2: Feature Completion

### 2.1 — Wire FoundryArchitect into the Live Game Loop
Currently the FoundryArchitect is only accessible via `!setup` and the War Room's `SCENE_SETUP` route. It should also be available during live gameplay so the Storyteller can trigger scene changes.

**Approach:** Add a post-storyteller hook — after the Storyteller responds, check if the narrative implies a scene change (new location, combat start). If so, dispatch to FoundryArchitect to update the board.

**Implementation:**
1. Add a lightweight classifier to detect scene-change triggers in the storyteller's output
2. When triggered, call `foundry_architect.process_request()` with the relevant context
3. This runs async (non-blocking) so the player gets their narrative immediately

### 2.2 — Consequence Resolution
Consequences are tracked and due consequences are surfaced to the Storyteller via context. But there's no mechanism to **resolve** consequences (mark them as handled after they fire).

**File:** `tools/vault_manager.py`
**Change:** Add `resolve_consequence(event_text, session_number)` — moves the entry from `## Pending` to `## Resolved` in `consequences.md`.

**File:** `agents/chronicler.py`
**Change:** After the Chronicler detects that a consequence was woven into the narrative, call `vault.resolve_consequence()`.

### 2.3 — Rate Limiting & Error Recovery
The bot currently has no rate limiting for Gemini API calls or Discord messages.

**Add:**
- A simple token bucket rate limiter for Gemini calls (e.g., 15 requests/minute for Flash)
- Exponential backoff on 429 errors from Discord
- A `max_retries` parameter for API calls with logging

**File:** New file `tools/rate_limiter.py` or integrate into `orchestration/bot.py`

### 2.4 — Session State Checkpointing
If the bot crashes mid-session, turn-by-turn chronicler events could be lost. The conversation history (MemoryEntry list) exists only in memory.

**Approach:** Periodically serialize `context_assembler.history.entries` to a JSON file in `06 - World State/`. On startup, reload it.

**File:** `tools/context_assembler.py`
**Changes:**
- Add `save_history(filepath)` and `load_history(filepath)` to `ConversationHistory`
- Call `save_history()` after every Chronicler pass
- Call `load_history()` at startup in `bot.py`

---

## Phase 3: Polish & Quality of Life

### 3.1 — Board Monitor Optimization
Currently `BoardMonitor.process_request()` is called for every game action, even when spatial context isn't needed (e.g., "I ask the bartender about rumors"). The router already classifies whether `needs_board_monitor` is true, but the board monitor still does full Foundry queries.

**Change:** Add message-type-aware queries to the board monitor — if the action is purely social, skip the combat/token queries and just return the current scene name.

### 3.2 — Foundry Path Separator Fix (Windows)
The reference indices use Windows-style backslash paths (`player_s_handbook\\chunk_0000.md`). The `ReferenceManager._read_chunk()` uses `os.path.join()` which should handle this on Windows, but would break on Linux.

**Change:** Normalize paths in the index with `os.path.normpath()` or replace `\\` with `/` at load time.

### 3.3 — Discord Embed Formatting for Storyteller
The storyteller currently sends raw text. For longer narratives, Discord embeds would look much better and allow for:
- A title (scene/location name)
- Color-coding (green for success, red for failure, gold for story beats)
- Footer showing current in-game time

### 3.4 — `!newsession` Command
A command to increment the session number, create a fresh session log, and optionally generate a recap of the previous session.

---

## Priority Order

1. **Phase 1.1** — Smoke test (verify the Chronicler fix works)
2. **Phase 1.2** — Chronicler context enrichment (quick win, ~10 lines)
3. **Phase 1.3** — Session log auto-creation (quick win, ~15 lines)
4. **Phase 2.4** — Session state checkpointing (prevents data loss)
5. **Phase 2.2** — Consequence resolution (completes the consequence loop)
6. **Phase 2.1** — FoundryArchitect live integration (biggest feature, most complex)
7. **Phase 2.3** — Rate limiting (important for stability)
8. **Phase 3.x** — Polish items (nice-to-have, do as time allows)
