# Findings — D&D AI DM Architecture Overhaul

## Codebase Analysis (Pre-Overhaul)

### File Sizes
| File | Lines | Role |
|------|-------|------|
| `orchestration/bot.py` | 1,406 | God file — everything lives here |
| `agents/tools/foundry_tool.py` | 872 | Foundry VTT client — self-contained, do not touch |
| `tools/vault_manager.py` | 608 | File I/O for Obsidian vault |
| `tools/context_assembler.py` | 524 | Prompt builder — reads from vault |
| `tools/blind_prep.py` | 436 | Session prep pipeline |
| `agents/world_architect.py` | 357 | Worldbuilding agent |
| `agents/cartographer.py` | 308 | Battlemap generator |
| `agents/foundry_architect.py` | 289 | Scene/encounter setup |
| `tools/reference_manager.py` | 286 | PDF text search |
| `agents/campaign_planner.py` | 277 | Session planning |
| `agents/chronicler.py` | 265 | Silent record-keeper |
| `agents/message_router.py` | 238 | Message classifier |
| `agents/board_monitor.py` | 197 | Foundry state reader |
| `tools/scene_classifier.py` | 159 | Post-narrative analysis |
| `tools/campaign_manager.py` | 149 | Multi-campaign directory mgmt |
| `agents/prep_router.py` | 138 | War Room classifier |
| `agents/rules_lawyer.py` | 129 | D&D 5e rules referee |
| `agents/storyteller.py` | 96 | Narrative generation |
| `tools/models.py` | 77 | Pydantic schemas (basic) |
| `tools/rate_limiter.py` | 68 | Token bucket limiter |

### Key Discoveries
1. `bot.py` contains ALL Discord setup, ALL commands, ALL pipelines, ALL agent instantiation
2. Agents are pure Python (no Discord imports) — good, they can be wrapped directly
3. `tools/models.py` already has basic Pydantic models but missing: WorldClock, Consequence, GameEvent, ChroniclerOutput
4. VaultManager uses Windows-specific file locking (`msvcrt`) — needs cross-platform consideration
5. All agents take `client` (Gemini), `context_assembler`, and optionally `vault`/`foundry` as constructor args
6. The game pipeline in `_handle_game_table()` is ~130 lines of sequential if/else
7. `_calculate_positions()` is a pure math function (no deps) — easy to extract
8. Player identity mapping (`PLAYER_MAP`) is loaded from .env at module level

### Agent Constructor Signatures (for pipeline node wrapping)
- `BoardMonitorAgent(client, foundry)`
- `RulesLawyerAgent(client, context_assembler, model_id)`
- `StorytellerAgent(client, context_assembler, model_id)`
- `FoundryArchitectAgent(client, foundry, model_id)`
- `MessageRouterAgent(client, context_assembler, model_id)`
- `ChroniclerAgent(client, vault, context_assembler, model_id)`
- `WorldArchitectAgent(client, vault, context_assembler, model_id)`
- `CampaignPlannerAgent(client, vault, context_assembler, model_id)`
- `PrepRouterAgent(client, context_assembler, model_id)`
- `CartographerAgent(client, foundry, vault, model_id, output_dir)`
