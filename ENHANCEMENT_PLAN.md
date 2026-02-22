# D&D AI DM — Enhancement Plan

## Paradigm: Admin-Assisted AI Dungeon Master

The AI **is** the Dungeon Master. It runs the game autonomously in Auto Mode — narrating scenes, adjudicating rules, tracking state, and responding to players in real time. A human admin monitors the session via the Admin Console and intervenes only when needed (complex rulings, dramatic pacing, homebrew situations). Queue Mode exists as an override for scenes requiring tighter control, such as tactical combat. The console is a monitoring dashboard, not a control panel.

---

## Current State

### Working Systems
- **Discord bot** — channel routing, `!` commands, `/console`, `/whisper`
- **LangGraph pipeline** — Router → Board Monitor → Rules Lawyer → Storyteller → Scene Sync → Chronicler
- **All 6 agents** — MessageRouter, RulesLawyer, Storyteller, Chronicler, BoardMonitor, FoundryArchitect
- **Vault I/O** — VaultManager with all CRUD methods, YAML frontmatter parsing, template system
- **Context assembler** — weighted memory with impact-based decay, conversation history
- **Reference manager** — SRD/PHB chunk indices populated and searchable
- **Action queue** — thread-safe queue with analyze/roll/resolve flow
- **Admin console** — 13 buttons, dashboard embed, DM event/annotation/roll modals
- **Rate limiting** — token bucket in `tools/rate_limiter.py` (gemini 15/min, discord 5/s, foundry 10/2s) **DONE**
- **Foundry VTT relay** — Three Hats Relay integration, scene/token/dice operations
- **War Room** — `!prep`, `!brainstorm`, `!plan` via prep pipeline
- **Campaign manager** — multi-campaign support with Windows junction symlinks
- **Player private threads** — `/whisper` with secret action queue support
- **Session log creation** — auto-creates from template with frontmatter **DONE**
- **Basic chronicler context** — party state, quests, immediate exchange **DONE**
- **Basic consequence resolution** — pending/resolved sections in consequences.md **DONE**

### Not Yet Tested End-to-End
The full game loop (player → router → rules → storyteller → chronicler → vault) should work with all fixes applied but needs a live multi-player session test.

---

## Phase 1: Core Autonomy

Priority order for the admin-assisted paradigm — make Auto Mode rock-solid first.

| # | Enhancement | Effort | Key Files | Notes & Corrections |
|---|------------|--------|-----------|---------------------|
| 1.1 | **Turn Gate + unique player dedup** | ~80 lines | `tools/turn_collector.py`, `bot/client.py` | `pending_count` currently counts messages, not unique players — must track a `set` of `character_name` values. The turn gate should batch by unique players, not message count. |
| 1.2 | **JSON Mode for all agents** | ~30 lines | `message_router.py:127`, `rules_lawyer.py:124,215`, `chronicler.py:144`, `prep_router.py:94`, `world_architect.py:209,304` | Previous plan missed `prep_router.py` and `world_architect.py` — **5 files** need `response_mime_type="application/json"`, not 3. |
| 1.3 | **Checkpointing hardening** | ~40 lines | `tools/context_assembler.py` | Add `timestamp` field to `MemoryEntry`. Use atomic writes: write to `.tmp` then `os.replace()` to prevent corruption on crash. |
| 1.4 | **Lorebook triggers** | ~120 lines | New `tools/lorebook.py`, `tools/context_assembler.py`, vault `07 - Lore/*.md` | Extend beyond MoirAI's pattern: add `category` field (deity, history, faction, etc.) and `position` field (before/after context) to frontmatter. Trigger on keyword match in player input. |
| 1.5 | **Auto Mode error recovery** | ~30 lines | `bot/client.py` | Currently no retry or user-facing error message when the pipeline fails in Auto Mode. Add try/except with retry + "The DM pauses to collect their thoughts..." fallback message. |

---

## Phase 2: Intelligence & Memory

| # | Enhancement | Effort | Key Files | Notes & Corrections |
|---|------------|--------|-----------|---------------------|
| 2.1 | **Semantic memory** | ~200 lines | New `tools/semantic_memory.py`, `tools/context_assembler.py` | 2000 entries = ~6MB with numpy embeddings (not 30MB as previously estimated). Use numpy dot-product search — no external vector DB needed at this scale. Add session-pinned memory: events with impact >= 8 never decay below retrieval threshold during the session they occurred. |
| 2.2 | **Chronicler deep context** | ~40 lines | `tools/context_assembler.py` | Enrich `build_chronicler_context()` with faction standings from `05 - Factions/` and recurring pattern detection (e.g., "party keeps ignoring this quest"). |
| 2.3 | **Consequence auto-resolution** | ~20 lines | `agents/chronicler.py` | Strengthen the Chronicler's prompt to explicitly guide the LLM: when a consequence has been woven into the narrative, output it in `resolved_consequences` list. |
| 2.4 | **Player dashboards** | ~80 lines | `bot/cogs/player_cog.py` | Add `!mystats` (character sheet summary) and `!myactions` (recent action history) commands. Add whisper thread button for quick access. |
| 2.5 | **Multi-provider LLM** | ~600 lines | New `tools/llm_provider.py`, all 8 agent files, `bot/client.py` | Budget 600 lines including tests (previous estimate of 460 was too low). Abstract Gemini calls behind a provider interface. Support OpenAI, Anthropic, local models. Per-agent model assignment via config. |

---

## Phase 3: Polish & Experience

| # | Enhancement | Effort | Key Files | Notes |
|---|------------|--------|-----------|-------|
| 3.1 | **Discord embeds** | ~100 lines | `bot/client.py` or new `bot/formatters.py` | Color-coded embeds for storyteller output: green (success), red (failure), gold (story beats). Title = scene/location. Footer = in-game time. |
| 3.2 | **`!newsession` command** | ~60 lines | `bot/cogs/dm_cog.py` | Increment session number, create fresh session log from template, optionally generate recap of previous session. |
| 3.3 | **FoundryArchitect live** | ~80 lines | `bot/client.py`, `pipeline/nodes/scene_sync_node.py` | Post-storyteller hook: detect scene-change triggers in narrative, dispatch to FoundryArchitect async (non-blocking). |
| 3.4 | **Board monitor optimization** | ~30 lines | `agents/board_monitor.py` | Skip full Foundry token/combat queries for purely social actions — just return current scene name. The router already classifies `needs_board_monitor`. |
| 3.5 | **Session log template** | ~20 lines | `tools/vault_manager.py` | Populate frontmatter with `session_number`, `ingame_date` (from world clock), and `location` when creating a new session file. |
| 3.6 | **Admin console redesign** | ~300 lines | `bot/views/admin_views.py`, `bot/cogs/admin_cog.py` | New features: "Pause after next turn" button, narrative tone controls (dramatic/light/combat), AI confidence indicator, rewind/regenerate last response, async play mode (AI responds to each player independently). |

---

## What NOT to Do

These are anti-patterns that would over-complicate the system:

- **Don't create 24+ specialized agents.** The current 6-agent pipeline covers the game loop. Add capabilities to existing agents, not new ones.
- **Don't replace the Obsidian vault** with a database. Markdown files are human-readable, version-controllable, and the Chronicler writes them well.
- **Don't build a web dashboard.** Discord IS the interface. The admin console thread is sufficient.
- **Don't replace LangGraph** with a custom orchestrator. The compiled StateGraph works and handles conditional routing.
- **Don't try to make the AI perfect before shipping.** Use confidence flagging and let the admin catch edge cases. The human-in-the-loop is a feature, not a crutch.

---

## Architecture Optimizations (Cross-Cutting)

These can be applied alongside any phase:

### Vault Read Caching
Add a TTL cache to `ContextAssembler` for vault reads. Most vault files don't change mid-turn. A 30-second TTL would eliminate redundant file I/O during batch resolution.

### Session-Pinned Memory
Events with impact >= 8 should never decay below the retrieval threshold (1.5) during the session they occurred. Currently, the 0.85 decay factor causes even critical events (impact 10) to fade below threshold by turn ~15. Session-pinning prevents this for the current session while still allowing natural decay across sessions.

### Memory Decay Tuning
The current decay factor of 0.85 may be too aggressive. A critical event (impact 10) at turn 0 has score 10.0, but by turn 12 it's down to `10 * 0.85^12 = 1.42` — below the 1.5 threshold. Consider either:
- Reducing decay to 0.9 (critical events persist ~28 turns)
- Implementing the session-pinning approach above
- Both (decay 0.9 + pinning for impact >= 8)

### Atomic Vault Writes
All vault write operations should use write-to-temp-then-rename pattern (`os.replace()`) to prevent file corruption if the bot crashes mid-write. Currently writes are direct.
