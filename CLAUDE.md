# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discord-based AI Dungeon Master for D&D 5e campaigns. Multi-agent LangGraph pipeline processes player actions through Router → Rules Lawyer → Storyteller → Chronicler. Persistent state in MongoDB (mechanical truth) and Obsidian vault (narrative truth). Live Foundry VTT integration for battlemaps/tokens. LLM backbone is Google Gemini.

## Commands

```bash
# Run the bot
python orchestration/main.py
# or on Windows:
start_bot.bat          # interactive menu: bot only, +Docker, +Foundry, +all

# Run all tests
pytest tests/

# Run a single test file
pytest tests/test_vault_models.py -v

# Type checking
pyright .
```

No formal linter or formatter is configured. Python 3.14, Pydantic v2.

## Architecture

### Three-Layer Design

1. **Discord Layer** (`bot/`) — Receives messages, routes by channel, formats responses. Zero knowledge of agents or game logic.
2. **Pipeline Layer** (`pipeline/`) — LangGraph compiled StateGraph. Nodes wrap agents, edges handle conditional routing. Typed `GameState` (TypedDict with 17 fields) flows through every node.
3. **Data Layer** (`models/` + `tools/`) — Pydantic v2 schemas are the contract for all writes. `StateManager` = MongoDB via Motor. `VaultManager` = Obsidian vault I/O with YAML frontmatter.

### Entry Point & Startup

`orchestration/main.py` (thin wrapper, avoids module shadowing) → imports `run()` from `bot/client.py` → loads Gemini client, agents, managers → builds LangGraph pipeline → `bot.run(TOKEN)`. Foundry and MongoDB connect lazily in `on_ready()`, not at import time.

### Pipeline Graph Topology

```text
router ──conditional──┬─→ board ──conditional──┬─→ rules ──→ storyteller ──→ scene_sync ──→ chronicler ──→ END
                      ├─→ rules                ├─→ storyteller
                      ├─→ storyteller           └─→ END
                      └─→ END (casual_chat, direct_response, error)
```

The router sets flags (`needs_board_monitor`, `needs_rules_lawyer`, `needs_storyteller`) that conditional edges read. After rules, the path is always linear: rules → storyteller → scene_sync → chronicler → END. Agents are bound to nodes via `functools.partial()` in `pipeline/graph.py`.

### DM Admin Console (Queue Mode)

The bot has two modes: **Auto Mode** (pipeline fires instantly on every message) and **Queue Mode** (actions queue for DM review). Toggle via the admin console or session start/end.

**Key files:**
- `tools/action_queue.py` — `ActionQueue`, `QueuedAction`, `RollRequest`, `MonsterRoll` models. Thread-safe via asyncio.Lock.
- `bot/cogs/admin_cog.py` — `/console` slash command, dashboard embed builder, console refresh logic
- `bot/views/admin_views.py` — 13 persistent buttons, modals (DMEvent, Annotate, RollRequest, MonsterRoll, PostToTable), ActionSelectView
- `bot/cogs/player_cog.py` — `/whisper` slash command for player private threads, secret actions
- `bot/client.py: handle_batch_resolve()` — processes curated action batches through the pipeline with two-phase commit (confirm_batch/restore_batch)

**Queue Mode flow:** Player message → `QueuedAction` created → ⏳ reaction → DM reviews in console → Analyze (Rules Lawyer pre-pass) → Players roll dice → DM clicks Resolve → `handle_batch_resolve()` → narrative posted.

**Dice flow:** `RollRequest` model supports multi-roll sequences (Attack → Damage). `update_roll_result()` returns `(action, next_roll)` tuple — next_roll is None when all rolls are done. Foundry cog intercepts `!roll` results when queue mode is active.

### Channel Routing

Discord messages route by channel ID (see `on_message()` in `bot/client.py`):

- **Game Table** (`GAME_TABLE_CHANNEL_ID`) → full LangGraph pipeline
- **War Room** (`WAR_ROOM_CHANNEL_ID`) → prep agents (worldbuilding, campaign planning, map generation)
- **Moderator Log** (`MODERATOR_LOG_CHANNEL_ID`) → receives rules details and debug output
- **Player private threads** (created via `/whisper`) → queue as secret actions
- **DM Console thread** (created via `/console`) → admin controls, DM's own character rolls

### GameState Fields

`pipeline/state.py` — TypedDict that flows through every node. Key fields:

- `player_input`, `character_name` — input from Discord
- `message_type` — router classification (game_action, casual_chat, etc.)
- `direct_response`, `needs_board_monitor`, `needs_rules_lawyer`, `needs_storyteller` — routing flags
- `board_context`, `rules_ruling`, `narrative`, `scene_changes` — per-node outputs
- `chronicler_done`, `session`, `current_location`, `error`, `direct_reply` — control/metadata
- `dm_context`, `dice_results`, `is_batched` — queue mode fields (DM annotations, actual roll results, multi-action flag)

### Foundry VTT Integration

Foundry has no native REST API. The project uses **Three Hats Relay** (Docker container on port 3010) as an HTTP↔WebSocket bridge. `agents/tools/foundry_tool.py` (~870 lines) is a self-contained async REST client wrapping that relay. `agents/tools/foundry_errors.py` defines a custom error hierarchy (retryable vs. non-retryable). Relay Docker config lives in `foundryvtt-relay/docker-compose.yml`.

Foundry V11+ schema quirks: `background.src` (not `img`), `environment.darknessLevel` (not `darkness`). Token placement uses embedded document creation (`parentUuid`) to avoid race conditions.

### Campaign Vault Structure

`campaigns/Default/` follows a numbered directory convention. `campaign_manager.py` uses Windows junctions (`mklink /J`) to symlink the active campaign to `campaign_vault/`.

```text
Default/
├── 00 - Session Log/    # Turn-by-turn prose logs
├── 01 - Party/          # PC character files
├── 02 - NPCs/           # NPC dossiers
├── 03 - Locations/      # Location descriptions
├── 04 - Quests/         # Active/ and Completed/ subdirs
│   ├── Active/
│   └── Completed/
├── 05 - Factions/
├── 06 - World State/    # Clock, consequences
├── 07 - Lore/
└── Assets/              # Maps/, Tokens/
```

## Key Reference: `gemini.md`

`gemini.md` is the **project constitution**. All data schemas (Character, NPC, Quest, Location, WorldClock, Consequence, GameEvent, ChroniclerOutput), behavioral rules, and architectural invariants are defined there. When schemas change, `gemini.md` is updated first.

## Architectural Invariants

These rules are from `gemini.md` and must be followed:

1. **Data-First Rule** — No tool writes to the database without passing through a Pydantic model. No raw dicts or JSON strings written directly.
2. **Vault = Narrative, MongoDB = Mechanical** — Obsidian holds prose (session logs, lore, NPC backstories). MongoDB holds mechanical state (HP, conditions, quest status, world clock). Vault is never source of truth for mechanical data.
3. **Agents are Pure Python** — Agent classes have no Discord imports, no database imports. They receive and return strings/dicts. The pipeline wraps them.
4. **Chronicler Validation Gate** — `StateManager.apply_chronicler_output()` accepts only a validated `ChroniclerOutput`. If LLM output doesn't match, `ValidationError` fires and nothing is written.
5. **Scene sync errors never block gameplay** — logged and skipped.
6. **All Gemini calls go through the rate limiter** — `await gemini_limiter.acquire()` before every call.
7. **Vault `.md` files are never deleted** during any migration or overhaul.

## Key Patterns

**Agent constructor pattern**: All agents take `(client, context_assembler, vault=None, foundry=None, model_id=None)`. Default model is `gemini-2.0-flash`. Temperature: 0.1 for logic agents, 0.9 for creative agents.

**Pipeline node pattern**: Async functions with signature `async def node_name(state: GameState, *, agent=None, **kwargs) -> dict`. Return partial dicts — LangGraph merges them into GameState. Agents are bound via `functools.partial()` in `graph.py`.

**Pydantic validation**: `Field()` + `field_validator()` for constraints. `model_validate_json()` for parsing LLM outputs. All validators use `@classmethod` decorator.

**Lazy imports for optional deps**: Motor and LangGraph use `try/except ImportError` with `HAS_MOTOR`/`HAS_LANGGRAPH` flags. MongoDB unavailable → vault-only mode. LangGraph missing → clear error at pipeline build time.

**Rate limiting**: Token bucket in `tools/rate_limiter.py`. Pre-configured instances: `gemini_limiter` (15 tokens, 0.25/s = ~15/min), `discord_limiter` (5 tokens, 1.0/s), `foundry_limiter` (10 tokens, 2.0/s). All async — `await limiter.acquire()` sleeps when bucket is empty.

**Context assembler memory decay**: `tools/context_assembler.py` uses weighted scoring: `score = impact × 0.85^turns_ago`. Impact is 1–10; critical events (10) persist ~15+ turns, flavor (2) fades after ~5 turns. Entries below threshold (1.5) are pruned, capped at 20 per context.

## Environment Variables

Configured in `.env`: `DISCORD_BOT_TOKEN`, `GEMINI_API_KEY`, `FOUNDRY_API_KEY`, `FOUNDRY_RELAY_URL`, `FOUNDRY_CLIENT_ID`, `MODERATOR_LOG_CHANNEL_ID`, `WAR_ROOM_CHANNEL_ID`, `GAME_TABLE_CHANNEL_ID`, `MONGODB_URI`, `PLAYER_MAP` (format: `discord_user:CharName,discord_user2:CharName2`).

## Development Notes

- **Test baseline:** 14 pre-existing failures in `test_blind_prep` (7), `test_cartographer` (7), `test_scene_classifier` (1 error). These are mock/fixture issues unrelated to core game logic. The 20 passing tests (`test_vault_models`, `test_vault_concurrency`, `test_campaign_manager`, `test_blind_prep` imports, `test_cartographer` imports) are the real regression gate.
- `docs/` contains player/DM documentation: `GETTING_STARTED.md`, `DM_GUIDE.md`, `PLAYER_GUIDE.md`, `SESSION_WALKTHROUGH.md`
- `COMPLETION_PLAN.md` tracks the phased development roadmap and known TODOs
- `docs/index.html` contains a generated architecture diagram
- IDE type checkers will show false positives for `discord`, `google`, `aiohttp`, `bot.client` imports — these are from unconfigured search roots, not real errors
- `pyrightconfig.json` is configured for Python 3.14 with extra paths for module resolution
