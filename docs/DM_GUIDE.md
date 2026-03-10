# Admin Guide — Monitoring & Assisting the AI Dungeon Master

The AI is the Dungeon Master. It narrates scenes, adjudicates rules, tracks state, and responds to players autonomously. Your role as admin is to monitor the session, intervene when the AI needs help, and maintain the campaign vault between sessions. This guide covers the monitoring dashboard, intervention tools, and when to use them.

---

## Quick Reference

### Slash Commands

| Command | Where | What it does |
|---------|-------|-------------|
| `/console` | Any text channel | Opens your private Admin Console thread |
| `/whisper` | Any text channel | *(Players use this)* Creates a player's private action thread |
| `/solo` | Any text channel | *(Players use this)* Starts a solo adventure in a private thread |
| `/solo_end` | Solo thread | *(Players use this)* Ends their solo adventure |
| `/solo_undo` | Solo thread | *(Players use this)* Rewinds last solo turn |
| `/bot-status` | Any text channel | System health overview (ephemeral) |
| `/solo-sessions` | Any text channel | Lists active solo adventures (ephemeral) |

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

## Two Modes of Operation

### Auto Mode (Primary)

Auto Mode is the default. The AI runs the game without intervention:

```
Player types action → AI pipeline fires → Narrative posted (seconds)
```

- Player messages immediately trigger the full LangGraph pipeline
- The AI narrates, adjudicates rules, and updates the vault
- No admin review required — the AI handles everything
- **Best for:** Most gameplay — exploration, roleplay, standard combat, social encounters

### Queue Mode (Override)

Queue Mode gives you direct control over the turn cycle:

```
Players type actions → Queue fills up → Admin reviews → Resolve → Narrative posted
```

- Player messages queue with ⏳ reactions
- Nothing happens until you review and click Resolve
- Full control over turn order, dice, annotations, and narrative
- **Best for:** Complex tactical combat, dramatic story beats, homebrew rulings, scenes requiring tight pacing

Toggle with the **⚡ Auto Mode** button. Starting a session auto-enables Queue Mode; you can immediately switch to Auto if preferred.

---

## The Monitoring Dashboard

### Opening the Console

1. Type `/console` in any text channel
2. The bot creates a **private thread** called "DM Console" — only you can see it
3. Inside the thread: a live-updating **dashboard embed** and 13 **control buttons**

### Dashboard Embed

The embed auto-updates whenever the queue changes:

```
━━━ ADMIN CONSOLE ━━━━━━━━━━━━━━━━━━━━━━━━━
Session 3 | The Yawning Portal
Auto Mode: ON | Foundry: Connected
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

In Auto Mode — AI is handling responses.
Switch to Queue Mode for manual control.

Party:
  Frognar — 28/28 HP | AC 16
  Kallisar — 18/18 HP | AC 14

Use buttons below to manage the game.
```

In Queue Mode, the dashboard shows queued actions, roll results, and monster rolls instead.

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
| 📝 **Annotate** | Add a private note to an action (e.g., "This NPC is actually a dragon"). AI sees it, players don't. |
| ⏭ **Skip Action** | Remove an action from the queue without processing it. |
| 🤐 **Secret Toggle** | Mark an action as secret/public. Secret results go to the player's private thread. |
| 📢 **Post to Table** | Type narration and post it directly to Game Table, bypassing the AI. |

**Row 3 — Session Lifecycle:**
| Button | What it does |
|--------|-------------|
| 🔄 **Refresh** | Force-refresh the dashboard embed. |
| ▶ **Start Session** | Enables queue mode, creates session log, generates "Previously on..." recap. |
| ⏹ **End Session** | Generates session summary, saves to vault, increments session number, disables queue. |
| ⚡ **Auto Mode** | Toggle between Queue Mode and Auto Mode. |

---

## When to Intervene

The AI handles most situations well. Leave it alone for:
- Standard exploration and travel
- NPC conversations with established characters
- Straightforward skill checks
- Combat with clear rules (standard attacks, common spells)
- Casual roleplay between characters

**Intervene when:**

| Situation | Action |
|-----------|--------|
| Complex negotiation with multiple NPCs | Switch to Queue Mode for pacing control |
| Homebrew ruling needed | Annotate the action with your ruling, or Post to Table |
| Dramatic reveal or plot twist | Post to Table for exact wording, or annotate with "Make this dramatic" |
| AI narrated something inconsistent | Post to Table with a correction, or annotate the next action |
| Novel player action the AI might mishandle | Switch to Queue Mode, annotate with guidance |
| Tactical combat requiring precise positioning | Switch to Queue Mode for full turn control |
| Player is confused or frustrated | Post to Table with clarification |

---

## Annotation Cheat Sheet

Annotations are your primary tool for guiding the AI without taking over. The AI reads your annotations and adjusts its narration accordingly.

### Effective Annotations

| Annotation | Effect |
|------------|--------|
| "Make this dramatic" | AI heightens tension, adds sensory details |
| "This should feel eerie and unsettling" | AI adjusts tone to horror/suspense |
| "This NPC is lying" | AI writes the NPC as deceptive — body language cues, evasive answers |
| "DC should be higher — this is very difficult" | AI adjusts difficulty framing in narration |
| "The merchant likes this character" | AI writes the NPC as warm and helpful |
| "This is a trap — describe it subtly" | AI foreshadows danger without revealing it |
| "Keep this short" | AI writes a brief response |
| "This succeeds but with a complication" | AI narrates success with a twist |

### Less Useful Annotations

| Annotation | Why |
|------------|-----|
| "Roll a d20" | Use the Request Roll button instead |
| "Add 5 damage" | Mechanical — use the Rules Lawyer or handle in Foundry |
| "Skip this" | Use the Skip Action button instead |
| Long paragraphs of instructions | Keep it brief — one sentence works best |

---

## When to Override the AI

Use **📢 Post to Table** to bypass the AI entirely for:

- **Plot reveals:** When you need exact wording ("You recognize the sigil — it's the same one from your father's journal.")
- **Specific NPC dialogue:** When an NPC must say something precise
- **Scene transitions:** "Three days pass as you travel north along the Trade Way..."
- **Rule corrections:** "Actually, that ability recharges on a short rest — you still have it available."
- **Atmosphere setting:** Reading a prepared description for a key location

---

## Lorebook Maintenance

Lore entries in `07 - Lore/` provide background knowledge the AI draws on during narration. Maintaining them between sessions keeps the AI's world knowledge accurate.

### Creating Lore Entries

Use `!brainstorm` in the War Room to generate ideas, then edit them into vault entries:

```yaml
---
type: lore
name: The Masked Lords of Waterdeep
tags: [lore, politics, waterdeep]
---
# The Masked Lords of Waterdeep

The city is governed by a secret council of Lords...
```

### Tips

- **Keep entries under 200 words.** The AI includes matched lore in context — brevity prevents context bloat.
- **Use specific tags.** `[lore, deity, mystra]` is better than `[lore, magic]` — more specific tags mean fewer false matches.
- **One topic per file.** Don't combine unrelated lore in one entry.
- **Update after sessions.** If the party learned something new about the world, update the relevant lore entry so the AI stays consistent.
- **Let the AI help.** The Chronicler sometimes creates lore-relevant notes in session logs. Promote useful ones to standalone lore entries.

---

## Session Walkthrough

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
3. **Decide your mode:** For open exploration, click ⚡ to switch to Auto Mode immediately. For a combat-heavy session, stay in Queue Mode.

### During the Session — Auto Mode

In Auto Mode, the AI handles everything:

1. **Players type in Game Table** — AI responds within seconds
2. **You monitor** — watch the console for issues, check narrative quality
3. **Intervene if needed** — annotate, post to table, or switch to Queue Mode
4. **Switch to Queue Mode** when combat starts or a complex scene needs control

### During the Session — Queue Mode

1. **Players type in Game Table:**
   > Frognar: "I kick down the door and charge at the nearest enemy"
   > Kallisar: "I cast Detect Magic on the strange altar"

   Each gets an ⏳ hourglass reaction. Actions appear in the console.

2. **Click 🔍 Analyze:**
   - Rules Lawyer examines each action
   - Frognar's action: needs an Attack roll (`1d20+7`) and maybe Damage (`2d6+4`)
   - Kallisar's action: no roll needed (ritual casting)
   - Bot auto-prompts in Game Table:
     > **Frognar**, roll Attack: `!roll 1d20+7`

3. **Players roll dice:**
   > Frognar types: `!roll 1d20+7`
   > Bot responds: `1d20+7: **19** d20: [12]`

   Multi-roll sequences (Attack → Damage) auto-prompt for the next roll.

4. **Manage the queue:**
   - **📝 Annotate** Frognar's action: "The door is actually a mimic."
   - **🧌 Monster Roll** the Mimic's Attack: `1d20+5` targeting Frognar
   - **➕ DM Event**: "The mimic's tongue lashes out as the door comes alive!"

5. **Click ▶ Resolve Turn:**
   - All ready actions + events + monster rolls are bundled
   - AI pipeline processes the batch: Rules → Storyteller → Chronicler
   - Narrative posted to Game Table

6. **Repeat** for the next round. Switch back to Auto Mode when combat ends.

### Your Own Character

If you also play a character:
- Your Discord username must be in `PLAYER_MAP`
- Roll prompts appear **in the console thread** (not Game Table) with a clickable **Roll** button
- Click the button → Foundry rolls → result captured automatically

### Secret Actions

**Player-initiated:** The player uses `/whisper` to open their private thread, then types their secret action. It queues with a `[SECRET]` tag.

**Admin-initiated:** Click **🤐 Secret Toggle** on any queued action. Results go to the player's private thread instead of Game Table.

### Ending the Session

1. Click **⏹ End Session**
   - AI generates a one-paragraph session summary
   - Summary saved to the session log in the vault
   - Closing message posted to Game Table
   - Session number incremented, queue mode disabled, memory checkpoint saved

---

## Tips

- **Trust the AI for routine play.** Auto Mode handles exploration, roleplay, and standard combat well. Save your interventions for moments that matter.
- **Analyze early in Queue Mode.** Click Analyze as soon as actions arrive — gives players time to roll while you review.
- **Batch intelligently.** Include related actions in the same resolve. The AI handles multi-character narration well.
- **Use annotations freely.** The AI reads your notes and adjusts storytelling. One sentence is usually enough.
- **Monster rolls before Resolve.** Roll monster attacks/damage before clicking Resolve so the AI has all information for narration.
- **The console thread persists.** Close and reopen with `/console` without losing state.
- **If the pipeline crashes:** Actions are automatically restored to the queue. Check Moderator Log for errors, then try resolving again.

---

## Solo Mode (Between-Session Adventures)

Players can run 1-on-1 adventures between group sessions using the `/solo` command. Each session runs in a private thread with the full AI pipeline but single-character context.

### How It Works

1. Player types `/solo` in any channel
2. Bot creates a private thread: "*CharacterName's Solo Adventure*"
3. AI generates an opening scene based on the character's current location
4. Player interacts directly with the AI DM — no admin intervention needed
5. Everything is logged to `00 - Session Log/Solo/`

### Guardrails

Solo mode enforces these constraints automatically (via prompt injection into the storyteller, rules lawyer, and chronicler):

- **No leveling or XP** — progression is reserved for group sessions
- **No killing named campaign NPCs** — protects shared narrative
- **No major campaign plot changes** — keeps the group story intact
- **World clock is frozen** — time doesn't advance, AI uses relative phrases ("Later that evening...")
- **No major magical items** — minor consumables and gold are OK
- **Small-scale combat only** — 1-3 enemies, personal stakes

### Monitoring Solo Sessions

- `/solo-sessions` — Lists all active solo adventures with character name, thread link, location, turn count, and elapsed time
- `/bot-status` — Shows total solo request count in pipeline stats
- Solo turns appear in the moderator log with `[SOLO]` prefix
- Solo logs are saved to `00 - Session Log/Solo/{CharacterName}_Solo_S{NNN}.md`

### Undo

Players can type `/solo_undo` to rewind their last turn. This:
- Restores conversation history to before the undone turn
- Resets location if the turn caused movement
- Marks the turn as `[UNDONE]` in the solo log (preserved for review)
- Can only undo once — no chaining undos

### Character Knowledge

During solo (and group) play, the Chronicler extracts personality traits, backstory fragments, goals, fears, and relationship changes from player actions. These are:
- Saved to `08 - Character Knowledge/{CharacterName}.md` in the vault
- Stored in MongoDB's `character_knowledge` collection
- Fed back into future storyteller context for richer, more personalized narration

This means solo play actively builds the AI's understanding of each character, which carries over into group sessions.

---

## System Monitoring

### `/bot-status`

Shows an ephemeral embed with full system health. Available to all users.

**System Components** — connection status for Discord (with latency), Gemini (with rate limiter tokens), MongoDB (connected/vault-only), and Foundry VTT (connected/disconnected).

**Pipeline Stats** — total requests (group/solo split), success rate, average latency, last request timing, slowest node, and per-node latency averages (router, board, rules, storyteller, scene_sync, chronicler).

**Errors** — breakdown by error type (pipeline_error, gemini_timeout, etc.).

**Color coding** — embed border is green (< 5% errors), yellow (5-20%), or red (> 20%).

### `/solo-sessions`

Lists all active solo adventures with character name, thread link, current location, turn count, and elapsed time.

### Auto-NPC Creation

The Chronicler automatically creates NPC vault files when new characters appear in narration. NPCs are saved to `02 - NPCs/` with standardized frontmatter. You don't need to manually create NPC files — the AI handles it during play.
