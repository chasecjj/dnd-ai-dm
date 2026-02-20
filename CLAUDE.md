# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Discord-based AI Dungeon Master for D&D 5e campaigns. Multi-agent LangGraph pipeline processes player actions through Router → Rules Lawyer → Storyteller → Chronicler. Persistent state in MongoDB (mechanical truth) and Obsidian vault (narrative truth). Live Foundry VTT integration for battlemaps/tokens. LLM backbone is Google Gemini.

## Commands

```bash
# Run the bot
python orchestration/main.py
# or on Windows:
start_bot.bat

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
2. **Pipeline Layer** (`pipeline/`) — LangGraph compiled StateGraph. Nodes wrap agents, edges handle conditional routing. Typed `GameState` (TypedDict with ~17 fields) flows through every node.
3. **Data Layer** (`models/` + `tools/`) — Pydantic v2 schemas are the contract for all writes. `StateManager` = MongoDB via Motor. `VaultManager` = Obsidian vault I/O with YAML frontmatter.

### Game Loop Pipeline

```
Player message → Router Node (classify: casual/game action/out-of-game)
  → Board Monitor Node (optional: fetch Foundry VTT state)
  → Rules Lawyer Node (validate D&D 5e mechanics, return structured JSON)
  → Storyteller Node (generate narrative prose)
  → Scene Sync Node (detect scene changes, update Foundry)
  → Chronicler Node (extract structured updates → validate via ChroniclerOutput → write to vault + MongoDB)
```

### Key Directories

- `bot/cogs/` — Discord commands split by domain: `dm_cog.py` (campaign), `foundry_cog.py` (VTT), `prep_cog.py` (worldbuilding)
- `pipeline/nodes/` — One file per pipeline node, each is an async function returning a partial state dict
- `agents/` — Pure Python agent classes (no Discord/DB imports). Constructor takes Gemini client + ContextAssembler. Each has `async process_request() -> dict|str`
- `agents/tools/foundry_tool.py` — Self-contained Foundry VTT REST client (~870 lines)
- `models/` — Pydantic v2 schemas. `chronicler_output.py` is the validation gate for all state writes
- `tools/state_manager.py` — Async MongoDB CRUD via Motor with Pydantic validation on every write
- `tools/vault_manager.py` — Obsidian vault I/O with frontmatter parsing, file locking, entity-specific methods
- `tools/context_assembler.py` — Dynamic prompt builder with weighted memory decay (score = impact × 0.85^turns_ago)
- `campaigns/Default/` — Obsidian vault structure: `00 - Session Log/`, `01 - Party/`, `02 - NPCs/`, `03 - Locations/`, `04 - Quests/`, `05 - Factions/`, `06 - World State/`, `07 - Lore/`

### Entry Point

`orchestration/main.py` (18-line wrapper) → imports `run()` from `bot/client.py` → loads agents, builds LangGraph pipeline, connects to Discord.

## Architectural Invariants

These rules are from `gemini.md` (the project constitution) and must be followed:

1. **Data-First Rule** — No tool writes to the database without passing through a Pydantic model. No raw dicts or JSON strings written directly.
2. **Vault = Narrative, MongoDB = Mechanical** — Obsidian holds prose (session logs, lore, NPC backstories). MongoDB holds mechanical state (HP, conditions, quest status, world clock). Vault is never source of truth for mechanical data.
3. **Agents are Pure Python** — Agent classes have no Discord imports, no database imports. They receive and return strings/dicts. The pipeline wraps them.
4. **Chronicler Validation Gate** — `StateManager.apply_chronicler_output()` accepts only a validated `ChroniclerOutput`. If LLM output doesn't match, `ValidationError` fires and nothing is written.
5. **Scene sync errors never block gameplay** — logged and skipped.
6. **All Gemini calls go through the rate limiter** — `await gemini_limiter.acquire()` before every call.
7. **Vault `.md` files are never deleted** during any migration or overhaul.

## Key Patterns

**Agent constructor pattern**: All agents take `(client, context_assembler, vault=None, foundry=None, model_id=None)`. Default model is `gemini-2.0-flash`. Temperature: 0.1 for logic agents, 0.9 for creative agents.

**Pipeline node pattern**: Async functions with signature `async def node_name(state: GameState, *, agent=None, **kwargs) -> dict`. Use `functools.partial` to bind agent instances when registering in `pipeline/graph.py`. Return partial dicts — LangGraph merges them into GameState.

**Pydantic validation pattern**: Use `Field()` + `field_validator()` for constraints. `model_validate_json()` for parsing LLM outputs. All validators use `@classmethod` decorator.

**Async everywhere**: All agents, StateManager methods, and pipeline nodes are async. Uses `motor` for non-blocking MongoDB.

**Graceful degradation**: MongoDB unavailable → vault-only mode (lazy import of motor). Foundry VTT down → board monitor fails gracefully, game continues.

## Environment Variables

Configured in `.env`: `DISCORD_BOT_TOKEN`, `GEMINI_API_KEY`, `FOUNDRY_API_KEY`, `FOUNDRY_RELAY_URL`, `FOUNDRY_CLIENT_ID`, `MODERATOR_LOG_CHANNEL_ID`, `WAR_ROOM_CHANNEL_ID`, `GAME_TABLE_CHANNEL_ID`, `MONGODB_URI`, `PLAYER_MAP` (format: `discord_user:CharName,discord_user2:CharName2`).

## Channel Routing

Discord messages route by channel ID:
- **Game Table** (`GAME_TABLE_CHANNEL_ID`) → full pipeline (router → rules → storyteller → chronicler)
- **War Room** (`WAR_ROOM_CHANNEL_ID`) → prep agents (worldbuilding, campaign planning, map generation)
- **Moderator Log** (`MODERATOR_LOG_CHANNEL_ID`) → receives rules details and debug output
