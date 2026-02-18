# D&D AI DM — Project Constitution (`gemini.md`)

> This file is **law**. All data schemas, behavioral rules, and architectural invariants live here.
> Updated only when a schema changes, a rule is added, or architecture is modified.

---

## North Star

A Discord-based AI Dungeon Master that runs a living D&D 5e campaign with:
- Multi-agent pipeline (Router → Rules Lawyer → Storyteller → Chronicler)
- Persistent game state in MongoDB (validated via Pydantic)
- Live Foundry VTT integration (battlemaps, tokens, dice)
- Narrative backup in Obsidian vault (human-readable `.md` files)

---

## Architectural Invariants

1. **Three-Layer Architecture**
   - **Discord Layer** (`bot/`) — receives messages, routes to pipeline, formats output. Zero knowledge of agents or game logic.
   - **Pipeline Layer** (`pipeline/`) — LangGraph compiled graph. Nodes = agents, edges = routing logic. Typed `GameState` flows through every node.
   - **Data Layer** (`models/` + `tools/`) — Pydantic schemas (the contract for all data), StateManager (MongoDB via motor), VaultManager (narrative prose only).

2. **Data-First Rule** — No tool writes to the database without passing through a Pydantic model first. Raw dicts and raw JSON strings are never written directly.

3. **Vault = Narrative, MongoDB = Mechanical** — The Obsidian vault holds prose (session logs, lore text, NPC backstories). MongoDB holds mechanical state (HP, conditions, quest status, world clock). The vault is never the source of truth for mechanical data.

4. **Agents are Pure Python** — Agent classes have no Discord imports, no database imports. They receive strings/dicts and return strings/dicts. The pipeline wraps them.

5. **Chronicler Validation Gate** — `StateManager.apply_chronicler_output()` accepts only a validated `ChroniclerOutput` object. If the LLM returns garbage, `ValidationError` fires and nothing is written.

---

## Data Schemas

### Character (Party Member)
```json
{
  "name": "Frognar Emberheart",
  "race": "Hill Dwarf",
  "char_class": "Paladin",
  "level": 3,
  "hp_current": 28,
  "hp_max": 34,
  "ac": 18,
  "pronouns": "he/him",
  "conditions": [],
  "spell_slots_used": 1,
  "spell_slots_max": 3,
  "lay_on_hands_pool": 15,
  "inventory_notes": "",
  "backstory_hooks": []
}
```

### NPC
```json
{
  "name": "Durnan",
  "race": "Human",
  "role": "Innkeeper",
  "location": "Yawning Portal",
  "faction": "unaffiliated",
  "disposition": "friendly",
  "alive": true,
  "tags": ["quest_giver", "ally"],
  "last_seen_session": 0,
  "notes": ""
}
```

### Quest
```json
{
  "name": "Volos Quest",
  "quest_giver": "Volothamp Geddarm",
  "status": "active",
  "objectives": ["Find Floon Blagmaar"],
  "completed_session": null,
  "rewards": {"gold": 100}
}
```

### Location
```json
{
  "name": "The Yawning Portal",
  "type": "tavern",
  "region": "Castle Ward, Waterdeep",
  "status": "active",
  "atmosphere": "bustling",
  "tags": ["hub", "quest_source"],
  "connected_locations": ["Castle Ward", "Undermountain"]
}
```

### WorldClock
```json
{
  "current_date": "1492 DR, Mirtul 14",
  "time_of_day": "evening",
  "session": 0,
  "current_location": "Yawning Portal"
}
```

### Consequence
```json
{
  "trigger_session": 2,
  "event": "Zhentarim discovers someone broke into their warehouse",
  "impact": 7,
  "notes": "Should lead to a confrontation with Krentz",
  "status": "pending"
}
```

### GameEvent (append-only log)
```json
{
  "session": 0,
  "description": "Frognar cast Lay on Hands on Kallisar for 10 HP",
  "impact": 6,
  "event_type": "combat",
  "timestamp": "2025-06-15T20:30:00Z"
}
```

### SessionLog
```json
{
  "session_number": 0,
  "real_date": "2025-06-15",
  "ingame_date": "1492 DR, Mirtul 14",
  "status": "in_progress",
  "location": "Yawning Portal"
}
```

### ChroniclerOutput (LLM validation gate)
```json
{
  "events": [
    {"description": "...", "impact": 5, "type": "combat"}
  ],
  "character_updates": [
    {"name": "Frognar Emberheart", "hp_current": 22, "conditions": ["poisoned"]}
  ],
  "npc_updates": [
    {"name": "Durnan", "disposition": "friendly", "alive": true}
  ],
  "quest_updates": [
    {"name": "Volos Quest", "status": "active", "progress_note": "Learned Floon was taken to the sewers"}
  ],
  "location_updates": [],
  "world_clock": {"current_date": "1492 DR, Mirtul 14", "time_of_day": "night"},
  "new_consequences": [
    {"trigger_session": 2, "event": "...", "impact": 5, "notes": "..."}
  ]
}
```

---

## Behavioral Rules

1. The Storyteller never breaks the 4th wall or mentions game mechanics in narrative prose.
2. The Rules Lawyer always returns structured JSON with `valid`, `mechanic_used`, and `result` fields.
3. The Chronicler never speaks to players. It runs silently after each exchange.
4. Casual chat messages are ignored (no API call wasted).
5. Scene sync errors never block the game — they are logged and skipped.
6. All Gemini calls go through the rate limiter (`gemini_limiter.acquire()`).
7. The vault `.md` files are never deleted during any migration or overhaul.

---

## External Integrations

| Service       | Purpose           | Env Var              | Status   |
|---------------|-------------------|----------------------|----------|
| Discord       | Player interface   | `DISCORD_BOT_TOKEN`  | Active   |
| Gemini API    | LLM backbone       | `GEMINI_API_KEY`     | Active   |
| Foundry VTT   | Virtual tabletop   | `FOUNDRY_API_KEY`    | Optional |
| MongoDB       | Game state DB      | `MONGODB_URI`        | **New**  |

---

## Dependency Stack

```
discord.py          — Discord interface
motor               — Async MongoDB driver
pymongo             — MongoDB (sync, motor dependency)
pydantic >= 2.0     — Schema validation
langgraph           — Agent pipeline graph
langchain-core      — LangGraph dependency
google-genai        — Gemini API
pyyaml              — Vault frontmatter parsing
python-dotenv       — Environment variables
PyMuPDF             — PDF extraction for knowledge base
```
