# Task Plan — D&D AI DM Architecture Overhaul

## Phase 0: B.L.A.S.T. Memory Files ✅
- [x] Create `gemini.md` (Project Constitution)
- [x] Create `task_plan.md` (this file)
- [x] Create `findings.md`
- [x] Create `progress.md`

## Phase 1: Data Layer (MongoDB + Pydantic) ✅
- [x] Build `models/` package with full Pydantic v2 schemas
  - `models/__init__.py`
  - `models/characters.py` — Character, NPCModel
  - `models/world_state.py` — WorldClock, Consequence, GameEvent
  - `models/quests.py` — QuestModel
  - `models/locations.py` — LocationModel
  - `models/session.py` — SessionLog
  - `models/chronicler_output.py` — ChroniclerOutput (THE validation gate)
- [x] Build `tools/state_manager.py` — async MongoDB service via motor
- [x] Build `scripts/migrate_vault_to_mongo.py` — with `--dry-run` support

## Phase 2: Split `bot.py` into Cogs ✅
- [x] Create `bot/` package structure
  - `bot/__init__.py`
  - `bot/client.py` — Bot setup, on_message, channel routing, pipelines
  - `bot/cogs/__init__.py`
  - `bot/cogs/dm_cog.py` — !status, !recap, !reset, !save, !image, !campaign
  - `bot/cogs/foundry_cog.py` — !roll, !monster, !scene, !pc, !build, !daytime, !nighttime, !setup
  - `bot/cogs/prep_cog.py` — !prep, !brainstorm, !plan
- [x] Shrink `orchestration/bot.py` to thin entry point (~14 lines)

## Phase 3: LangGraph Pipeline ✅
- [x] Build `pipeline/` package
  - `pipeline/__init__.py`
  - `pipeline/state.py` — GameState TypedDict
  - `pipeline/graph.py` — Compiled LangGraph graph with conditional edges
  - `pipeline/nodes/router_node.py`
  - `pipeline/nodes/board_monitor_node.py`
  - `pipeline/nodes/rules_node.py`
  - `pipeline/nodes/storyteller_node.py`
  - `pipeline/nodes/chronicler_node.py`
  - `pipeline/nodes/scene_sync_node.py`
- [x] Replace `_handle_game_table()` with `await game_pipeline.ainvoke(state)`
- [x] Foundry VTT dispatch runs AFTER pipeline, not inside it

## Phase 4: Context Assembler → StateManager ✅
- [x] Add async context builders that query StateManager for mechanical data
- [x] Keep vault reads for narrative prose (descriptions, lore, session logs)
- [x] Graceful fallback: if StateManager disconnected, vault-only mode
- [x] Added `get_all_npcs()`, `get_all_quests()`, `get_pending_consequences()` to StateManager

## Dependency Updates ✅
- [x] `requirements.txt` — added motor, pymongo, langgraph, langchain-core
- [x] `.env` — added MONGODB_URI
