# Campaign Setup Guide

How to set up a new campaign for the AI Dungeon Master. This guide walks you through creating a campaign, populating the vault, and getting your first session ready.

---

## Step 1: Create the Campaign

```
!campaign new Dragon Heist
```

This creates a new campaign directory under `campaigns/` with the full vault structure and sets it as the active campaign. The bot symlinks it to `campaign_vault/` so all agents can find it.

To switch between campaigns later:
```
!campaign load Dragon Heist
!campaign list
```

---

## Step 2: Configure PLAYER_MAP

In your `.env` file, map Discord usernames to character names:

```env
PLAYER_MAP=saaxmaan:Balthur,frognar_player:Frognar,kal_player:Kallisar
```

Format: `discord_username:CharacterName` — comma-separated, no spaces. The bot uses this to identify which character is acting when a player types in Game Table.

---

## Step 3: Create Character Files

Add a markdown file for each PC in `01 - Party/`. Use the YAML frontmatter format the agents expect.

**Template:** `_templates/party_member_template.md`

**Example** (`01 - Party/Balthur.md`):

```yaml
---
type: party_member
name: Balthur
player: saaxmaan
race: Human
class: Wizard
level: 1
hp_current: 6
hp_max: 6
ac: 12
conditions: []
spell_slots_used: 0
spell_slots_max: 2
lay_on_hands_pool: 0
tags:
- party
char_class: Wizard
pronouns: ''
foundry_uuid: null
---
# Balthur

## Stats
| Stat | Score | Mod |
|------|-------|-----|
| STR  | 8     | -1  |
| DEX  | 14    | +2  |
| CON  | 10    | +0  |
| INT  | 16    | +3  |
| WIS  | 12    | +1  |
| CHA  | 13    | +1  |

## Abilities & Features
- Arcane Recovery
- Spellcasting (Intelligence)

## Prepared Spells
- _(to be determined)_

## Inventory
- _(to be determined)_

## Personality
_Roleplaying notes, quirks, motivations._

## Bonds & Hooks
_Story threads tied to this character._

## Session Notes
_Running notes on this character's arc._
```

**Key fields:** `name` must match the value in `PLAYER_MAP`. `player` is the Discord username. `hp_current`, `hp_max`, `ac`, and `conditions` are updated by the Chronicler during play. `foundry_uuid` links to the Foundry VTT token if you're using it.

---

## Step 4: Set Up the World Clock

Edit `06 - World State/clock.md` to establish your starting date and time:

```yaml
---
type: world_clock
current_date: 1st of Ches
time_of_day: evening
season: early_spring
session: 1
tags:
- meta
- world_state
---
# World Clock

## Current Time
- **In-Game Date:** 1st of Ches (early spring)
- **Time of Day:** Evening
- **Weather:** Clear skies, cool breeze
- **Moon Phase:** Waxing crescent

## Timeline
| Session | In-Game Date | Key Event |
|---------|-------------|-----------|

## Notes
- The calendar uses the Harptos Calendar (Forgotten Realms).
```

The Chronicler updates this file as time passes in-game. The Storyteller reads it for atmospheric context.

---

## Step 5: Create Your Starting Location

Add a file in `03 - Locations/` for wherever the campaign begins.

**Template:** `_templates/location_template.md`

**Example** (`03 - Locations/Yawning Portal.md`):

```yaml
---
type: location
name: The Yawning Portal
region: Waterdeep
district: Castle Ward
owner: "[[Durnan]]"
notable_npcs: ["[[Durnan]]", "[[Yagra Strongfist]]"]
visited: false
first_visited_session: null
tags: [location, tavern, key_location]
---
# The Yawning Portal

## Description
A legendary tavern in Castle Ward, Waterdeep. Famous for the massive
entry well in its center — a 140-foot shaft leading to Undermountain.

## Current State
A busy evening. Patrons fill the tables, drinks flow freely.

## Notable Features
- **The Well:** A 140-ft shaft to Undermountain, roped off.
- **Heavy Oak Tables:** Sturdy furniture throughout.

## NPCs Present
- [[Durnan]] — Owner, behind the bar.

## Connections
- Located in Castle Ward, Waterdeep.
- The well connects to Undermountain below.

## DM Notes
_Hidden elements, upcoming events at this location._
```

Use `[[wiki-links]]` for NPCs and other locations — these create connections in the vault.

---

## Step 6: Add Initial NPCs

Create files in `02 - NPCs/` for any NPCs the party will meet early.

**Template:** `_templates/npc_template.md`

```yaml
---
type: npc
name: Durnan
race: Human
role: Tavern Owner
location: "[[The Yawning Portal]]"
faction: ""
disposition: neutral
alive: true
first_seen_session: 1
last_seen_session: 1
tags: [npc]
---
```

You don't need to create every NPC up front. The AI generates NPC entries during play when new characters appear — the Chronicler writes them to the vault automatically.

---

## Step 7: Set Up Quests

Add active quests in `04 - Quests/Active/`.

**Template:** `_templates/quest_template.md`

```yaml
---
type: quest
name: Find the Missing People
status: active
quest_giver: Volothamp Geddarm
location: "[[The Yawning Portal]]"
started_session: 1
completed_session: null
reward: "10 gold pieces and a map"
tags: [quest]
---
# Find the Missing People

## Objective
Locate Floon Blagmaar, who has gone missing in the Dock Ward.

## Background
Volo approached the party in the Yawning Portal, desperate for help.

## Progress
- [ ] Speak to Volo about the details
- [ ] Investigate the Dock Ward

## Complications
_Obstacles, twists, dangers._

## Rewards
10 gold pieces and a map to a property in Trollskull Alley.
```

Completed quests get moved to `04 - Quests/Completed/` by the Chronicler.

---

## Step 8: Create Lorebook Entries

Add world lore in `07 - Lore/`. These are reference entries the AI draws on when relevant topics come up.

```yaml
---
type: lore
name: Waterdeep
tags: [lore, city]
---
# Waterdeep — The City of Splendors

## Overview
Waterdeep is the greatest city on the Sword Coast...
```

**Tips for lorebook entries:**
- Keep entries under 200 words — the AI includes them in context, so brevity matters
- Use specific, unique keywords in the `name` and `tags` fields
- Focus on information the AI needs to narrate accurately (geography, politics, customs)
- Let the AI generate lore during play with `!brainstorm` — then clean it up into vault entries

---

## Step 9: Set Up Consequences

The file `06 - World State/consequences.md` tracks ripple effects from party decisions. Start with an empty queue:

```yaml
---
type: consequences
tags:
- meta
- world_state
---
# Consequence Queue

Consequences are ripple effects from party decisions. The Chronicler writes
new entries here. The Context Assembler surfaces due consequences to the
Storyteller when trigger conditions are met.

## Pending

## Resolved
```

The Chronicler populates this during play. Example consequence:

```markdown
- **trigger:** session >= 3
  **event:** The Zhentarim send agents to investigate the party.
  **caused_by:** "Party killed a Zhentarim operative."
  **impact:** 7
  **notes:** Agents arrive at the party's known lodging.
```

---

## Step 10: Add Factions

Create files in `05 - Factions/` for organizations relevant to your campaign:

```yaml
---
type: faction
name: Xanathar Guild
disposition_to_party: unknown
reputation: 0
tags: [faction]
---
# Xanathar Guild

## Overview
A thieves' guild run by the beholder Xanathar from beneath Waterdeep.

## Known Members
- _(discovered during play)_

## Party Standing
- **Disposition:** Unknown
- **Reputation:** 0

## Key Interests
- Total control of Waterdeep's criminal underworld.

## DM Notes
_Hidden motivations, plot hooks._
```

The Chronicler updates `disposition_to_party` and `reputation` as the party interacts with factions.

---

## Tips

- **Start small.** You need characters, a starting location, and one quest. Everything else can grow during play.
- **Let the AI generate content.** The Chronicler creates NPC entries, updates locations, and tracks consequences automatically. You don't need to pre-populate everything.
- **Use `!brainstorm` to flesh out the world.** Run it in the War Room channel to generate ideas for locations, NPCs, and plot hooks — then edit the results into vault entries.
- **Use `!prep` before sessions.** It generates encounter ideas, NPC motivations, and potential complications based on current campaign state.
- **Check `_templates/` for file formats.** Every vault file type has a template showing the expected frontmatter fields.
- **Wiki-links (`[[Name]]`) matter.** They create connections between vault files that the Context Assembler uses to pull related information.
