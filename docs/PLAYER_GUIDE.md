# Player Guide — Playing D&D with an AI Dungeon Master

Your Dungeon Master is an AI. It narrates the world, adjudicates rules, and responds to your actions in real time. A human admin monitors the session and can intervene for complex situations, but most of the time you're interacting directly with the AI.

---

## The Basics

### Where to play

Your admin has set up a Discord channel called something like **Game Table**. That's where the game happens. Type your actions there and the AI processes them immediately.

### How to take actions

Just type what your character does in natural language:

> I search the room for hidden doors

> I approach the merchant and ask about the rumors

> I cast Fireball at the group of goblins

> I try to persuade the guard to let us through

In most cases, the AI responds within seconds with a narration of what happens. Sometimes the admin may be using Queue Mode (for combat or complex scenes), in which case your action gets an ⏳ hourglass reaction and is processed when the admin resolves the turn.

### When you need to roll dice

Sometimes the AI (or the admin) determines that your action requires a dice roll. The bot will prompt you:

> **Frognar**, roll Perception: `!roll 1d20+3`

Type exactly what it says:

```
!roll 1d20+3
```

The bot responds with your result:

> `1d20+3`: **16** d20: [13]

If your action requires multiple rolls (like Attack then Damage), the bot prompts you for each one in order:

> **Frognar**, roll Attack: `!roll 1d20+7`

*(you roll)*

> **Frognar**, now roll Damage: `!roll 2d6+4`

*(you roll)*

After all rolls are captured, the AI narrates what happened.

---

## Writing Good Actions

The AI responds to what you write, so better input produces better narration.

### Be specific
| Instead of | Try |
|-----------|-----|
| "I search the room" | "I carefully check the desk drawers for hidden compartments or false bottoms" |
| "I attack" | "I charge at the nearest goblin, swinging my greataxe at its neck" |
| "I talk to the bartender" | "I lean on the bar and quietly ask the bartender if he's seen anyone matching Floon's description" |

### Describe attempts, not outcomes
Write what you **try** to do, not what happens. The AI decides the outcome based on rules, dice, and context.

- **Good:** "I try to leap across the chasm"
- **Bad:** "I leap across the chasm and land safely"

### One action per message
Send one action per message. If you want to do multiple things, send multiple messages. This helps the AI process each action clearly.

### Include motivation
The AI narrates better when it understands *why* you're doing something:

> "I examine the strange runes on the wall — my character studied ancient languages at the academy and might recognize them"

### Use the environment
Reference things the AI has described. If the narration mentioned chandeliers, use them:

> "I grab the chandelier chain and swing across to the balcony"

---

## What the AI Can and Cannot Do

### The AI can:
- Narrate scenes with atmosphere, dialogue, and sensory detail
- Adjudicate D&D 5e rules (attacks, spells, skill checks, saving throws)
- Remember recent events (what happened this session and the last few sessions)
- Track HP, spell slots, conditions, and other mechanical state
- Role-play NPCs with distinct personalities
- Manage quests, consequences, and world state
- Respond to creative and unexpected player actions

### The AI cannot:
- Adjudicate homebrew rules (the admin handles these)
- Recall events from many sessions ago without prompting (long-term memory is being improved)
- Perfectly balance encounter difficulty every time
- Read your mind — if your intent isn't clear, the AI guesses
- Handle simultaneous complex interactions between many NPCs (the admin may step in)

If the AI gets something wrong, say so in Game Table. The admin is watching and can correct it.

---

## Pacing Expectations

### Auto Mode (most of the time)
The AI responds in **seconds**. You type an action, and the narration appears almost immediately. There's a short batching window (~45 seconds) where the AI may wait to see if other players are also acting, then it narrates all actions together.

### Queue Mode (combat and complex scenes)
The admin switches to Queue Mode for tighter control. In this mode:
- Your action gets an ⏳ reaction (it's been received)
- The admin clicks Analyze — you may be prompted to roll dice
- You roll when prompted
- The admin clicks Resolve — narration appears
- This is closer to traditional D&D pacing

You'll notice the difference — Auto Mode feels like a conversation, Queue Mode feels like structured turns.

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

> **If Foundry VTT is not connected:** The `!roll` command won't work. Your admin
> can use an external dice roller and input results manually, or you can roll
> physical dice and report your result in Game Table.

### Information

| Command | What it does |
|---------|-------------|
| `!status` | Shows party HP, AC, conditions, and active quests |
| `!recap` | Shows the latest session recap |
| `!recap 3` | Shows the recap from session 3 |
| `!pc Frognar` | Look up a character's stats |

### Solo Adventures

| Command | What it does |
|---------|-------------|
| `/solo` | Start a solo adventure in a private thread |
| `/solo_end` | End your solo adventure |
| `/solo_undo` | Rewind your last solo turn |

### System

| Command | What it does |
|---------|-------------|
| `/bot-status` | Show bot health and pipeline stats |
| `/solo-sessions` | List active solo adventures |

---

## Solo Adventures (Between Sessions)

Want to explore the world, talk to NPCs, or run side quests on your own between group sessions? Use the `/solo` command.

### Starting a Solo Adventure

1. Type `/solo` in any text channel
2. The bot creates a private thread: "*YourCharacterName's Solo Adventure*"
3. The AI generates an opening scene based on your character's current location
4. Type actions just like in Game Table — the AI responds as your personal DM

### Commands in Solo Mode

| Command | What it does |
|---------|-------------|
| `/solo` | Start a solo adventure (creates private thread) |
| `/solo_end` | End your solo adventure (summary + thread archived) |
| `/solo_undo` | Rewind your last turn and try something different |

### What You Can Do in Solo Mode

- Explore locations, talk to NPCs, gather information
- Run small personal side quests
- Develop your character's backstory and relationships
- Acquire minor items and gold
- Engage in small-scale combat (1-3 enemies)

### What You Can't Do in Solo Mode

- Gain XP or level up (that's for group sessions)
- Kill major named NPCs from the campaign
- Advance the main campaign plot
- Acquire powerful magical items

### Undo

Made a choice you regret? Type `/solo_undo` to rewind your last turn. The AI forgets what happened and you can try a different approach. You can only undo once per turn — no chaining undos.

### Tips for Solo Play

- **Solo play builds your character.** The AI learns your character's personality, fears, goals, and relationships during solo sessions. This carries over into group play for richer narration.
- **Time is frozen.** The world clock doesn't advance during solo play. The AI uses phrases like "Later that evening..." instead of specific dates. Your DM reconciles timeline at the next group session.
- **You can have a solo session while others do too.** Multiple players can run solo adventures concurrently in separate threads.

---

## Secret Actions

Want to do something the other players shouldn't know about? Use the `/whisper` command.

### How it works

1. Type `/whisper` in any text channel
2. The bot creates a private thread — only you and the admin can see it
3. Type your secret action in that thread

> I secretly pocket the gemstone before the others notice

Your action joins the queue tagged as `[SECRET]`. When it resolves, the results appear **in your private thread**, not the Game Table.

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

When your action is in the queue (Queue Mode), you'll see these if you check with **My Queue Status**:

| Icon | Meaning |
|------|---------|
| 🟡 | **Pending** — not yet reviewed |
| 🔍 | **Analyzing** — the AI is figuring out if you need to roll |
| 🎲 | **Awaiting Roll** — you need to roll dice (check Game Table for the prompt) |
| 🟢 | **Ready** — all set, waiting for the turn to resolve |

---

## Troubleshooting

### The AI responded incorrectly
Say so in Game Table: "Wait, my character has darkvision — I should be able to see in this room." The admin can correct the narration or annotate the next turn. The AI also learns from corrections within the session.

### The AI forgot something
The AI's memory covers recent sessions well but may miss details from many sessions ago. Remind it in your action: "I check the map we found in session 2 — does it show this area?" The admin can also annotate with forgotten context.

### No response after typing an action
- **In Auto Mode:** Check the Moderator Log channel for errors. The admin may need to restart the pipeline.
- **In Queue Mode:** This is normal — your action is queued. The admin will process it when ready.

### The narrative seems off
If the AI's tone or pacing feels wrong, mention it in Game Table. The admin can adjust the AI's approach with annotations. You can also steer the tone through your own actions — writing dramatically encourages dramatic narration.

### Dice roll didn't register
Make sure you typed the `!roll` command exactly as prompted. The formula must match (e.g., `!roll 1d20+7`, not `!roll d20+7`). If Foundry is disconnected, the admin will handle rolls manually.

---

## Tips

- **Be descriptive.** "I search the desk" works, but "I carefully check the desk drawers for hidden compartments" gives the AI more to work with.
- **Wait for the prompt before rolling.** Don't pre-roll dice — the AI decides what rolls are needed.
- **One action at a time.** Send one action per message for clearest results.
- **NAT 20 / NAT 1** are called out automatically when you roll through Foundry.
- **Don't worry about rules.** The AI handles D&D 5e mechanics. Just describe what you want to do in plain English.
- **The AI handles rules automatically** but you can challenge a ruling in character — "I don't think that's how Shield works" — and the admin will review it.
- **If something seems wrong, say so in Game Table.** The admin is watching and can correct the AI.
- **The ⏳ hourglass** means your action was received. In Auto Mode it processes immediately; in Queue Mode the admin will handle it.
