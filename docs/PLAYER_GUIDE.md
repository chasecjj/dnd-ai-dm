# Player Guide — D&D AI Dungeon Master

Welcome! This guide explains how to play D&D with the AI Dungeon Master bot. Your DM handles the behind-the-scenes work — you just need to know how to interact with the bot in Discord.

---

## The Basics

### Where to play

Your DM has set up a Discord channel called something like **Game Table**. That's where the game happens. Type your actions there and the AI (guided by your DM) will narrate what happens.

### How to take actions

Just type what your character does in natural language:

> I search the room for hidden doors

> I approach the merchant and ask about the rumors

> I cast Fireball at the group of goblins

> I try to persuade the guard to let us through

The bot acknowledges your action with an ⏳ hourglass reaction. Your DM will review it and trigger the AI to narrate the results.

### When you need to roll dice

Sometimes the DM (or the AI Rules Lawyer) will determine that your action requires a dice roll. The bot will prompt you:

> **Frognar**, roll Perception: `!roll 1d20+3`

Type exactly what it says:

```
!roll 1d20+3
```

The bot responds with your result:

> `1d20+3`: **16** d20: [13]

If your action requires multiple rolls (like Attack then Damage), the bot will prompt you for each one in order:

> **Frognar**, roll Attack: `!roll 1d20+7`

*(you roll)*

> **Frognar**, now roll Damage: `!roll 2d6+4`

*(you roll)*

After all rolls are captured, the DM resolves the turn and the AI narrates what happened.

---

## Commands You Can Use

### Dice Rolling

| Command | Example | What it does |
|---------|---------|-------------|
| `!roll <formula>` | `!roll 1d20+5` | Roll dice through Foundry VTT |
| `!roll <formula> <reason>` | `!roll 1d20+5 Perception` | Roll with a label |

**Common formulas:**
- `1d20+5` — standard ability/skill check
- `2d6+3` — damage roll
- `1d20+7` — attack roll
- `4d6kh3` — roll 4d6, keep highest 3 (ability score generation)
- `2d20kh1+5` — advantage (roll 2d20, keep highest, add modifier)
- `2d20kl1+5` — disadvantage (roll 2d20, keep lowest, add modifier)

### Information

| Command | What it does |
|---------|-------------|
| `!status` | Shows party HP, AC, conditions, and active quests |
| `!recap` | Shows the latest session recap |
| `!recap 3` | Shows the recap from session 3 |
| `!pc Frognar` | Look up a character's stats |

---

## Secret Actions

Want to do something the other players shouldn't know about? Use the `/whisper` command.

### How it works

1. Type `/whisper` in any text channel
2. The bot creates a private thread — only you and the DM can see it
3. Type your secret action in that thread

> I secretly pocket the gemstone before the others notice

Your action joins the DM's queue tagged as `[SECRET]`. When the DM resolves it, the results appear **in your private thread**, not the Game Table.

### The private console

Your private thread has two buttons:

| Button | What it does |
|--------|-------------|
| **My Queue Status** | Shows your pending actions and their status |
| **Help** | Shows a quick help summary |

### When to use Game Table vs. Private Thread

| Use Game Table for | Use Private Thread for |
|-------------------|----------------------|
| Normal actions the party should see | Stealing from NPCs or party members |
| Combat actions | Sending a secret message |
| Group decisions | Investigating something alone |
| Casual RP | Anything you want hidden from other players |

---

## What the Status Icons Mean

When your action is in the queue, you'll see these status indicators if you check with the **My Queue Status** button:

| Icon | Meaning |
|------|---------|
| 🟡 | **Pending** — DM hasn't reviewed it yet |
| 🔍 | **Analyzing** — the AI is figuring out if you need to roll |
| 🎲 | **Awaiting Roll** — you need to roll dice (check Game Table for the prompt) |
| 🟢 | **Ready** — all set, waiting for DM to resolve the turn |

---

## Tips

- **Be descriptive.** "I search the desk" is fine, but "I carefully check the desk drawers for hidden compartments or false bottoms" gives the AI more to work with.
- **Wait for the prompt before rolling.** Don't pre-roll dice — the DM and AI decide what rolls are needed.
- **One action at a time.** Send one action per message. If you want to do multiple things, send multiple messages.
- **NAT 20 / NAT 1** are called out automatically when you roll through Foundry.
- **Don't worry about rules.** The AI Rules Lawyer handles D&D 5e mechanics. Just describe what you want to do in plain English.
- **The ⏳ hourglass** means your action was received. Sit tight — the DM will process it.
