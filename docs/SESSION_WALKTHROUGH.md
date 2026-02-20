# Simulated Session Walkthrough

This document simulates a full session from first boot to session end, showing exactly what every participant sees in Discord. Characters in this example: **Frognar** (Half-Orc Barbarian, played by John) and **Kallisar** (Elf Wizard, played by Jane). The DM is **Chase**.

---

## Before the Session

### Bot Startup

Chase runs `python orchestration/main.py`. The terminal shows:

```
2026-02-20 18:30:01 [INFO] DND_Bot: Logged in as ArcaneArbitrator (1234567890)
2026-02-20 18:30:01 [INFO] DND_Bot: Vault path: campaign_vault
2026-02-20 18:30:01 [INFO] DND_Bot: Current session: 3
2026-02-20 18:30:02 [INFO] DND_Bot: StateManager connected — DB-backed context active.
2026-02-20 18:30:02 [INFO] DND_Bot: Foundry VTT connected: client=ai-dm
2026-02-20 18:30:02 [INFO] DND_Bot: Admin console persistent view registered.
2026-02-20 18:30:02 [INFO] DND_Bot: Synced 2 slash command(s).
D&D AI System Online. Vault-backed state is active.
```

### DM Opens the Console

Chase types `/console` in the War Room channel.

**What Chase sees (ephemeral):**
> Console created: #DM Console

A new private thread "DM Console" appears. Inside:

```
┌─────────────────────────────────────────────────────────┐
│  DM Console                                              │
│                                                          │
│  Session 3 | The Yawning Portal                          │
│  Queue Mode: OFF | Foundry: Connected                    │
│  ──────────────────────────────────────────────────       │
│                                                          │
│  Queued Actions                                          │
│  No actions queued.                                      │
│                                                          │
│  Party                                                   │
│    Frognar — 28/28 HP | AC 16                            │
│    Kallisar — 18/18 HP | AC 14                           │
│                                                          │
│  Use buttons below to manage the game.                   │
├─────────────────────────────────────────────────────────┤
│ [▶ Resolve Turn] [🔍 Analyze] [🎲 Request Roll] [➕ DM Event]  │
│ [🧌 Monster Roll] [📝 Annotate] [⏭ Skip Action] [🤐 Secret Toggle] [📢 Post to Table] │
│ [🔄 Refresh] [▶ Start Session] [⏹ End Session] [⚡ Auto Mode]  │
└─────────────────────────────────────────────────────────┘
```

---

## Starting the Session

Chase clicks **▶ Start Session**.

**What the DM Console says (ephemeral):**
> Session 3 started. Queue mode enabled. Recap posted.

**What everyone sees in Game Table:**

> **--- Session 3 Begins ---**
>
> *Previously, on our adventure...*
>
> *The party descended into the Yawning Portal's infamous well, navigating treacherous corridors until they discovered an ancient dwarven forge guarded by rust monsters. After a tense battle — Frognar's greataxe nearly dissolved by the creatures' antennae — the party retreated to the surface with a mysterious map fragment etched in Dwarvish. Kallisar identified it as part of a larger cartographic work showing hidden passages beneath Waterdeep.*
>
> *The night air of Waterdeep greets you as morning light spills through the tavern windows. Durnan polishes a glass behind the bar, eyeing your group with his usual measured gaze...*

The dashboard embed now shows:
```
Queue Mode: ON
```

---

## Round 1: Player Actions

### Players Type Their Actions

**John types in Game Table:**
> I walk up to Durnan and show him the map fragment. "Have you seen markings like these before?"

Bot reacts with ⏳

**Jane types in Game Table:**
> While Frognar talks to Durnan, I study the map fragment with Detect Magic to see if it has any enchantments

Bot reacts with ⏳

### DM Console Updates

The dashboard now shows:

```
Queued Actions (2):
1. 🟡 [Frognar] "I walk up to Durnan and show him the map fragment..."
2. 🟡 [Kallisar] "While Frognar talks to Durnan, I study the map fragm..."
```

### DM Analyzes

Chase clicks **🔍 Analyze**.

The Rules Lawyer AI examines both actions:
- Frognar showing a map and asking a question → **no roll needed** (social interaction, NPC response)
- Kallisar casting Detect Magic → **no roll needed** (ritual spell, automatic success)

**Console update:**
```
Queued Actions (2):
1. 🟢 [Frognar] "I walk up to Durnan and show him the map fragment..."
2. 🟢 [Kallisar] "While Frognar talks to Durnan, I study the map fragm..."
```

Both are 🟢 ready (no rolls required).

### DM Adds Context

Chase clicks **📝 Annotate**, selects Frognar's action, and types:
> Durnan recognizes the markings but is guarded. He knows about the passages but doesn't trust the party enough yet. He gives a cryptic hint.

Chase also clicks **➕ DM Event** and types:
- **What happens?** A cloaked halfling at a nearby table perks up when she overhears the conversation about the map.
- **DM notes:** This is Lira, a rogue NPC who will offer to guide the party for a price. Introduce her subtly.

**Console update:**
```
Queued Actions (3):
1. 🟢 [Frognar] "I walk up to Durnan and show him the map fragment..."
   📝 Durnan recognizes the markings but is guar...
2. 🟢 [Kallisar] "While Frognar talks to Durnan, I study the map fragm..."
3. 🟢 [DM] "A cloaked halfling at a nearby table perks up..."
   📝 This is Lira, a rogue NPC who will offer...
```

### DM Resolves

Chase clicks **▶ Resolve Turn**.

**What everyone sees in Game Table:**

> Frognar slides the weathered parchment across the bar toward Durnan, who pauses mid-polish. The old adventurer's eyes narrow as they trace the angular Dwarvish script.
>
> "Those markings," Durnan says slowly, setting down the glass with deliberate care. "I've seen their like before. Decades ago." He leans closer, voice dropping. "There are doors beneath this city that were sealed for good reason. The dwarves who carved those runes — they weren't just mapping tunnels. They were marking what to *avoid*."
>
> He straightens and resumes polishing, his expression closing like a shuttered window. "That's all I'll say on it. Some knowledge costs more than gold."
>
> Meanwhile, Kallisar traces careful arcane gestures over the fragment, the ritual's familiar cadence washing over the parchment. The map itself bears no enchantment — but faint traces of abjuration magic cling to the edges, as though the original complete map was once protected by powerful wards. Whatever was being hidden, someone went to great lengths to keep it secret.
>
> At a shadowed table near the hearth, a cloaked figure shifts almost imperceptibly. A halfling woman, her hood drawn low, turns a copper coin between nimble fingers. She'd been nursing her drink in bored silence — but when the word "map" carried across the bar, her eyes sharpened beneath the cowl.

---

## Round 2: Combat Encounter

### Players Act

**John types:**
> I notice the halfling watching us. I turn to face her directly. "You. What's your interest in our business?"

**Jane types:**
> I discreetly cast Mage Hand under the table to check if the halfling has any weapons within easy reach

### DM Analyzes

Chase clicks **🔍 Analyze**.

Rules Lawyer results:
- Frognar's confrontation → **no roll** (direct social interaction, no deception/persuasion)
- Kallisar's sneaky Mage Hand → **needs roll**: Sleight of Hand (Dexterity) check, DC 13

**Game Table auto-prompt:**
> **Kallisar**, roll Sleight of Hand: `!roll 1d20+4`

**Console update:**
```
1. 🟢 [Frognar] "I notice the halfling watching us..."
2. 🎲 [Kallisar] "I discreetly cast Mage Hand under the table..."
   ⏳ Waiting: Sleight of Hand `1d20+4`
```

### Player Rolls

**Jane types in Game Table:**
```
!roll 1d20+4
```

**Bot responds:**
> `1d20+4`: **11** d20: [7]

**Console updates:**
```
2. 🟢 [Kallisar] "I discreetly cast Mage Hand under the table..."
   🎲 Sleight of Hand DC 13: **11** FAIL
```

### DM Adds a Monster Roll

Chase decides the halfling (Lira) notices Kallisar's attempt. He clicks **🧌 Monster Roll**:
- **Monster name:** Lira
- **Roll type:** Perception
- **Formula:** 1d20+6
- **Target:** Kallisar

The console thread shows:
> 🧌 **Lira** rolls Perception vs **Kallisar**: `1d20+6` = **19** d20: [13]

### DM Annotates and Resolves

Chase annotates Frognar's action:
> Lira is amused by the confrontation, not threatened. She should respond with cocky confidence.

Chase clicks **▶ Resolve Turn**.

**Game Table:**

> Frognar rises from his barstool with the casual menace of a thunderstorm building on the horizon. The barbarian turns to face the halfling directly, arms crossed, his frame blocking the firelight.
>
> "You. What's your interest in our business?"
>
> The halfling doesn't flinch. Instead, she smiles — a sharp, knowing expression that suggests she's been caught intentionally. She pushes back her hood, revealing bright, clever eyes and a scar that traces her jaw.
>
> "The name's Lira," she says, tilting her chair back with practiced ease. "And your *business* happens to align with mine. I know those tunnels. I know what's down there." She spins the copper coin once more, then catches it. "Question is — do you want to wander in blind, or do you want a guide?"
>
> Beneath the table, Kallisar's spectral hand drifts toward Lira's belt — but the halfling's foot shifts, a dagger hilt suddenly pressing against the invisible fingers. Her smile doesn't waver as she glances sidelong at the elf.
>
> "Careful, wizard. I count my blades the way you count your spell slots." Two short swords hang at her hips. A hand crossbow peeks from beneath her cloak. She is *very* well armed.

---

## Round 3: The DM's Own Character

Chase also plays a character, **Theron** (Cleric), mapped in `PLAYER_MAP`.

**Chase types in Game Table (as a player):**
> I cast Insight on Lira to see if she's being truthful about knowing the tunnels

Chase clicks **🔍 Analyze**.

Since this is the DM's own character, the roll prompt appears **in the console thread** (not Game Table) with a clickable button:

> 🎲 **Theron** needs to roll **Insight** DC 14: `1d20+6`
> [🎲 Roll 1d20+6]

Chase clicks the **Roll** button. Foundry rolls automatically:

> `1d20+6`: **22** d20: [16]

The console updates with the result, and Chase resolves normally.

---

## Ending the Session

After several more rounds, the party agrees to hire Lira. Chase decides to wrap up.

Chase clicks **⏹ End Session**.

**Game Table:**

> **--- Session 3 Ends ---**
>
> *A deal was struck at the Yawning Portal: the mysterious halfling Lira joined the party as a guide to the sealed passages beneath Waterdeep. Durnan's cryptic warnings linger as the group prepares for a descent into tunnels that were sealed for good reason. The map fragment's faded wards suggest powerful forces once guarded whatever lies below — and whatever drove the dwarves to mark these passages did not do so lightly.*

**DM Console (ephemeral):**
> Session 3 ended. Summary saved. Next session: 4. Queue mode disabled.

The vault now contains:
- `00 - Session Log/Session 003.md` — with the summary filled in
- `06 - World State/World Clock.md` — session_number updated to 4

---

## What Happens Without Foundry VTT

Everything above still works except:
- `!roll` commands won't function (players can use external dice rollers and the DM can manually input results)
- `!monster`, `!scene`, `!build`, `!daytime`, `!nighttime` are unavailable
- Monster Roll button shows "Foundry not connected"
- The AI still identifies needed rolls — you just need another way to generate them
