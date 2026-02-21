# Campaign Reset & Character Creation Wizard — Design Doc

**Date:** 2026-02-20
**Status:** Approved

## Context

New campaign tonight with different/more players, all creating new characters. Same Waterdeep: Dragon Heist setting. Need to reset player-specific data, verify systems work, and provide an interactive character creation experience via the existing Adventurer's Compendium website.

## Workstream 1: Campaign Reset

### Clear
- `campaign_vault/01 - Party/*.md` (Frognar, Kallisar)
- `campaign_vault/04 - Quests/Active/*.md` (Volo's Quest)
- `campaign_vault/00 - Session Log/*.md` (any session logs)
- `campaign_vault/06 - World State/clock.md` → reset to Session 0 defaults
- `campaign_vault/06 - World State/consequences.md` → clear pending
- `campaign_vault/06 - World State/memory_checkpoint.json` → empty
- `.env` PLAYER_MAP → clear (repopulate after character creation)

### Keep
- NPCs (12 files), Locations (12 files), Factions, Lore, Templates, Assets

### Foundry VTT Reset
- Run `python scripts/reset_foundry.py` (already exists)
- Clears tokens from all scenes, ends encounters, resets lighting

### Implementation
- Write `scripts/reset_campaign.py` that handles vault reset + calls Foundry reset
- Single command: `python scripts/reset_campaign.py`

## Workstream 2: Systems Check

- Run `pytest tests/` — verify 20 passing tests still pass
- Start bot with `python orchestration/main.py` — verify startup
- Confirm pipeline flow: router → rules → storyteller → chronicler

## Workstream 3: Character Creation Wizard

### New File
`docs/guide/character-wizard.html` + `docs/guide/character-wizard.js` + `docs/guide/character-wizard.css`

### 7-Step Flow

1. **Name & Concept** — text input + fantasy name generator (race-aware syllable tables), optional concept textarea
2. **Race** — clickable cards with racial traits, ability bonuses. 9 PHB races.
3. **Class** — clickable cards with hit die, key abilities, role description. 12 PHB classes.
4. **Background** — 13 PHB backgrounds with skill/tool proficiencies, languages, personality suggestions
5. **Ability Scores** — Standard Array / Point Buy / Roll (4d6 drop lowest). Auto-applies racial bonuses. Live modifier display.
6. **Equipment & Inventory** — auto-populated from class + background. Starting armor, weapons, tools, gold. AC calculation.
7. **Character Sheet Summary** — full D&D-style layout with all calculated values. "Copy for DM" (vault-template markdown), "Print/Save PDF" (print stylesheet).

### Design Constraints
- Dark theme matching existing Cinzel/Inter design system (same CSS variables)
- Pure client-side JS, no backend
- localStorage for progress saving
- Mobile-friendly
- Progressive disclosure (expand for details)
- Nav link added to existing navigation

### Data
All PHB Level 1 data embedded as JS objects:
- Race traits, ability bonuses, speeds, languages, features
- Class hit dice, primary abilities, saving throw proficiencies, armor/weapon proficiencies, starting equipment choices
- Background skill proficiencies, tool proficiencies, equipment, personality traits/ideals/bonds/flaws
- Fantasy name tables per race (curated syllable arrays)
