# DM Guide — Running Sessions with the Admin Console

This guide walks you through running a D&D session using the DM Admin Console. It covers every button, every command, and the full workflow from session start to session end.

---

## Quick Reference

### Slash Commands

| Command | Where | What it does |
|---------|-------|-------------|
| `/console` | Any text channel | Opens your private DM Admin Console thread |
| `/whisper` | Any text channel | *(Players use this)* Creates a player's private action thread |

### `!` Commands (type in any channel)

| Command | What it does |
|---------|-------------|
| `!roll 1d20+5` | Roll dice via Foundry VTT |
| `!roll 1d20+5 Perception` | Roll with a reason label |
| `!monster goblin` | Look up a monster stat block |
| `!pc Frognar` | Look up a player character's stats |
| `!scene tavern` | Search Foundry for battle maps |
| `!build 4 goblins ambush in a forest` | AI builds a full encounter (finds map, places tokens) |
| `!daytime` | Set active Foundry scene to bright |
| `!nighttime` | Set active Foundry scene to dark |
| `!foundry` | Check Foundry VTT connection status |
| `!status` | Show party HP, AC, conditions, active quests |
| `!recap` | Show latest session recap |
| `!recap 3` | Show recap for session 3 |
| `!campaign list` | List all campaigns |
| `!campaign new Dragon Heist` | Create a new campaign |
| `!campaign load Dragon Heist` | Switch to a different campaign |
| `!save` | Confirms game state is saved (vault is always persistent) |
| `!reset` | Clear conversation memory (vault files untouched) |
| `!prep <description>` | AI blind-preps a session (War Room only) |
| `!brainstorm <topic>` | Worldbuilding brainstorm (War Room only) |
| `!plan <notes>` | AI helps plan a session (War Room only) |

---

## The Admin Console

### Opening the Console

1. Type `/console` in any text channel
2. The bot creates a **private thread** called "DM Console" — only you can see it
3. Inside the thread: a live-updating **dashboard embed** and 13 **control buttons**

### Dashboard Embed

The embed auto-updates whenever the queue changes:

```
━━━ DM CONSOLE ━━━━━━━━━━━━━━━━━━━━━━━━━━━
Session 3 | The Yawning Portal
Queue Mode: ON | Foundry: Connected
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Queued Actions (2):
1. 🟡 [Frognar] "I approach the barkeep and ask about the missing people"
2. 🟢 [Kallisar] "I scan the room for threats"
   🎲 Perception DC 14: **17** PASS

Monster Rolls (1):
🧌 Goblin Archer Attack vs Frognar: **18** (1d20+4: d20: [14] = 18)

Party:
  Frognar — 28/28 HP | AC 16
  Kallisar — 18/18 HP | AC 14

Use buttons below to manage the game.
```

### Status Icons

| Icon | Meaning |
|------|---------|
| 🟡 | **Pending** — action received, not yet analyzed |
| 🔍 | **Analyzing** — Rules Lawyer is examining it |
| 🎲 | **Awaiting Roll** — player needs to roll dice |
| 🟢 | **Ready** — all rolls done, ready to resolve |
| ⏳ | Roll waiting / queued in sequence |

### Button Layout

**Row 1 — Core Actions:**
| Button | What it does |
|--------|-------------|
| ▶ **Resolve Turn** | Flushes all ready actions through the AI pipeline. Narrative posted to Game Table. |
| 🔍 **Analyze** | Runs Rules Lawyer pre-analysis on all pending actions. Identifies needed dice rolls. |
| 🎲 **Request Roll** | Manually request a specific dice roll for a queued action (opens select menu → modal). |
| ➕ **DM Event** | Inject a narrative event into the queue ("A hooded figure enters..."). |

**Row 2 — Queue Management:**
| Button | What it does |
|--------|-------------|
| 🧌 **Monster Roll** | Roll dice for a monster/NPC via Foundry. Result shown in console thread. |
| 📝 **Annotate** | Add a private DM note to an action (e.g., "This NPC is actually a dragon"). AI sees it, players don't. |
| ⏭ **Skip Action** | Remove an action from the queue without processing it. |
| 🤐 **Secret Toggle** | Mark an action as secret/public. Secret results go to the player's private thread. |
| 📢 **Post to Table** | Type narration and post it directly to Game Table, bypassing the AI. |

**Row 3 — Session Lifecycle:**
| Button | What it does |
|--------|-------------|
| 🔄 **Refresh** | Force-refresh the dashboard embed. |
| ▶ **Start Session** | Enables queue mode, creates session log, generates "Previously on..." recap. |
| ⏹ **End Session** | Generates session summary, saves to vault, increments session number, disables queue. |
| ⚡ **Auto Mode** | Toggle between Queue Mode (DM-controlled turns) and Auto Mode (instant AI responses). |

---

## Session Walkthrough

Here's a complete session from start to finish.

### Before the Session

1. **Prep in the War Room** (optional):
   - `!prep The party will explore the Undermountain entrance` — AI prepares NPCs, locations, encounters
   - `!brainstorm What factions might be interested in the party's success?`
   - `!plan Party enters the dungeon, encounters a puzzle, then ambush by duergar`

2. **Set up Foundry** (optional):
   - `!build 3 duergar defensive in a dungeon corridor` — pre-builds an encounter
   - `!scene undermountain` — find and load a battle map

### Starting the Session

1. Open the console: `/console`
2. Click **▶ Start Session**
   - Queue mode turns ON automatically
   - A session log file is created in the vault
   - AI generates a "Previously on..." recap from the last session
   - Recap is posted to Game Table
   - Players see: `--- Session 3 Begins ---` followed by the recap

### During the Session

**The turn cycle:**

```
Players type actions → Queue fills up → DM reviews → Resolve → Narrative posted
     ↑                                                              |
     └──────────────────────────────────────────────────────────────┘
```

**Step by step:**

1. **Players type in Game Table:**
   > Frognar: "I kick down the door and charge at the nearest enemy"
   > Kallisar: "I cast Detect Magic on the strange altar"

   Each gets an ⏳ hourglass reaction. Actions appear in the console.

2. **DM clicks 🔍 Analyze:**
   - Rules Lawyer examines each action
   - Frognar's action: needs an Attack roll (`1d20+7`) and maybe Damage (`2d6+4`)
   - Kallisar's action: no roll needed (ritual casting)
   - Bot auto-prompts in Game Table:
     > **Frognar**, roll Attack: `!roll 1d20+7`

3. **Players roll dice:**
   > Frognar types: `!roll 1d20+7`
   > Bot responds: `1d20+7: **19** d20: [12]`

   If the Rules Lawyer identified a multi-roll sequence (Attack → Damage), the bot auto-prompts for the next roll:
   > **Frognar**, now roll Damage: `!roll 2d6+4`

4. **DM manages the queue:**
   - **📝 Annotate** Frognar's action: "The door is actually a mimic. DC should be higher."
   - **🧌 Monster Roll** the Mimic's Attack: `1d20+5` targeting Frognar
   - **➕ DM Event**: "The mimic's tongue lashes out as the door comes alive!"

5. **DM clicks ▶ Resolve Turn:**
   - All ready actions + DM events + monster rolls are bundled together
   - The AI pipeline processes the entire batch:
     - Rules Lawyer applies actual dice results
     - Storyteller narrates the round covering all characters
     - Chronicler saves state changes to the vault
   - Narrative posted to Game Table

6. **Repeat** for the next round of actions.

### DM's Own Character

If you (the DM) also play a character:
- Your Discord username must be in `PLAYER_MAP`
- When your character needs a roll, the prompt appears **in the console thread** (not Game Table) with a clickable **Roll** button
- Click the button → Foundry rolls → result captured automatically

### Secret Actions

When a player does something the others shouldn't know about:

**Player-initiated:** The player uses `/whisper` to open their private console, then types their secret action there. It queues with a `[SECRET]` tag.

**DM-initiated:** Click **🤐 Secret Toggle** on any queued action to mark it secret. Results go to the player's private thread instead of Game Table.

### Posting Direct Narration

Sometimes you want to post something to Game Table without the AI rewriting it:
- Click **📢 Post to Table**
- Type your narration
- It posts verbatim — no AI processing

### Ending the Session

1. Click **⏹ End Session**
   - AI generates a one-paragraph session summary
   - Summary saved to the session log in the vault
   - Closing message posted to Game Table:
     > `--- Session 3 Ends ---`
     > *The party retreated to the Yawning Portal, wounds tended and plans made for a return to the dungeon's depths...*
   - Session number incremented
   - Queue mode disabled
   - Memory checkpoint saved

---

## Two Modes of Operation

### Queue Mode (DM-controlled)
- Player messages queue up with ⏳ reactions
- Nothing happens until the DM reviews and clicks Resolve
- Full control over turn order, dice, and narrative
- **Best for:** Combat, important story beats, any scene requiring DM oversight

### Auto Mode (instant AI)
- Player messages immediately trigger the full AI pipeline
- Narrative posted within seconds
- No DM review or queue
- **Best for:** Free exploration, casual RP, scenes where you don't need control

Toggle with the **⚡ Auto Mode** button or by starting/ending a session (Start Session auto-enables queue mode).

---

## Tips

- **Analyze early:** Click Analyze as soon as actions arrive. This gives players time to roll while you review.
- **Batch intelligently:** Include related actions in the same resolve. The AI handles multi-character narration well.
- **Use annotations freely:** The AI reads your DM notes and adjusts its storytelling. "Make this dramatic" or "This should feel eerie" work great.
- **Monster rolls before Resolve:** Roll monster attacks/damage before clicking Resolve so the AI has all the information for narration.
- **Auto Mode for downtime:** Switch to Auto Mode for tavern RP and exploration, then back to Queue Mode when combat starts.
- **The console thread persists:** You can close and reopen it with `/console` without losing state.
- **If the pipeline crashes:** Actions are automatically restored to the queue. Check Moderator Log for errors, then try resolving again.
