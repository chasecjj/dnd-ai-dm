# Campaign Reset & Character Creation Wizard — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Reset campaign data for a fresh start (same Waterdeep setting), then build an interactive 7-step character creation wizard for new players.

**Architecture:** Three independent workstreams: (1) A Python script that clears player-specific vault files and resets world state, optionally calling the existing Foundry reset script. (2) A systems verification check. (3) A new `character-wizard.html` page with companion JS/CSS that provides a step-by-step character builder matching the existing Adventurer's Compendium dark theme. All D&D data is embedded as client-side JS objects — no backend needed.

**Tech Stack:** Python 3.14 (reset script), vanilla HTML/CSS/JS (wizard), existing design system (Cinzel/Inter fonts, CSS custom properties from `guide-shared.css`)

---

## Task 1: Campaign Reset Script

**Files:**
- Create: `scripts/reset_campaign.py`
- Read: `campaign_vault/06 - World State/clock.md` (for default content)
- Read: `campaign_vault/06 - World State/consequences.md` (for default content)

**Step 1: Write the reset script**

```python
"""
Campaign Reset Script — Clears player-specific data for a fresh campaign start.

Preserves: NPCs, Locations, Factions, Lore, Templates, Assets
Clears: Party, Quests, Session Logs, World State, Memory Checkpoint

Usage: python scripts/reset_campaign.py
       python scripts/reset_campaign.py --include-foundry
"""
import os
import sys
import glob
import json
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

VAULT_ROOT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "campaign_vault")

CLOCK_DEFAULT = """---
type: world_clock
current_date: "1st of Ches"
time_of_day: evening
season: early_spring
session: 0
tags: [meta, world_state]
---
# World Clock

## Current Time
- **In-Game Date:** 1st of Ches (early spring)
- **Time of Day:** Evening
- **Weather:** Not yet established
- **Moon Phase:** Not yet established

## Timeline
| Session | In-Game Date | Key Event |
|---------|-------------|-----------|

## Notes
- Waterdeep: Dragon Heist takes place over Levels 1-5.
- The calendar uses the Harptos Calendar (Forgotten Realms).
- Ches = 3rd month (March equivalent). Early spring — snow melting, days getting longer.
"""

CONSEQUENCES_DEFAULT = """---
type: consequences
tags: [meta, world_state]
---
# Consequence Queue

Consequences are ripple effects from party decisions. The Chronicler agent writes new entries here. The Context Assembler checks for due consequences and includes them in the Storyteller's prompt when trigger conditions are met.

## Pending

## Resolved
_(none yet)_
"""


def delete_files_in(directory, pattern="*.md"):
    """Delete matching files in a directory (non-recursive)."""
    target = os.path.join(VAULT_ROOT, directory, pattern)
    files = glob.glob(target)
    for f in files:
        os.remove(f)
        print(f"  Deleted: {os.path.basename(f)}")
    if not files:
        print(f"  (no files to delete)")
    return len(files)


def reset_file(relative_path, content):
    """Overwrite a file with default content."""
    path = os.path.join(VAULT_ROOT, relative_path)
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    print(f"  Reset: {relative_path}")


def main():
    parser = argparse.ArgumentParser(description="Reset campaign for a fresh start")
    parser.add_argument("--include-foundry", action="store_true",
                        help="Also reset Foundry VTT (requires relay running)")
    parser.add_argument("--yes", "-y", action="store_true",
                        help="Skip confirmation prompt")
    args = parser.parse_args()

    print("=" * 50)
    print("CAMPAIGN RESET")
    print("=" * 50)
    print()
    print("This will CLEAR:")
    print("  - Party member files (01 - Party/)")
    print("  - Active quests (04 - Quests/Active/)")
    print("  - Session logs (00 - Session Log/)")
    print("  - World clock & consequences (reset to defaults)")
    print("  - Memory checkpoint (reset to empty)")
    print()
    print("This will KEEP:")
    print("  - NPCs, Locations, Factions, Lore")
    print("  - Templates and Assets")
    print()

    if not args.yes:
        confirm = input("Proceed? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Aborted.")
            return

    print()

    # 1. Clear party members
    print("--- Clearing Party ---")
    delete_files_in("01 - Party")

    # 2. Clear active quests
    print("\n--- Clearing Active Quests ---")
    delete_files_in("04 - Quests/Active")

    # 3. Clear session logs
    print("\n--- Clearing Session Logs ---")
    delete_files_in("00 - Session Log")

    # 4. Reset world state
    print("\n--- Resetting World State ---")
    reset_file("06 - World State/clock.md", CLOCK_DEFAULT)
    reset_file("06 - World State/consequences.md", CONSEQUENCES_DEFAULT)

    # 5. Reset memory checkpoint
    checkpoint_path = os.path.join(VAULT_ROOT, "06 - World State", "memory_checkpoint.json")
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump([], f)
    print("  Reset: 06 - World State/memory_checkpoint.json")

    print("\n--- Vault Reset Complete ---")

    # 6. Optionally reset Foundry
    if args.include_foundry:
        print("\n--- Resetting Foundry VTT ---")
        import asyncio
        from scripts.reset_foundry import main as foundry_reset
        asyncio.run(foundry_reset())

    print()
    print("=" * 50)
    print("RESET COMPLETE")
    print("=" * 50)
    print()
    print("Next steps:")
    print("  1. Update PLAYER_MAP in .env with new player mappings")
    print("  2. Create party member files in campaign_vault/01 - Party/")
    print("  3. Run: python orchestration/main.py")


if __name__ == "__main__":
    main()
```

**Step 2: Run the reset script (with confirmation)**

Run: `cd "C:\Users\chase\Documents\Antigravity Projects" && python scripts/reset_campaign.py`
Expected: Prompts for confirmation, then deletes party files, quests, resets world state.

**Step 3: Commit**

```bash
git add scripts/reset_campaign.py
git commit -m "feat: add campaign reset script for fresh starts"
```

---

## Task 2: Systems Check

**Files:**
- Read: `tests/` (existing test suite)

**Step 1: Run the test suite**

Run: `cd "C:\Users\chase\Documents\Antigravity Projects" && python -m pytest tests/ -v --tb=short 2>&1 | head -80`
Expected: ~20 passing tests, 14 known failures (test_blind_prep, test_cartographer, test_scene_classifier)

**Step 2: Verify bot imports**

Run: `cd "C:\Users\chase\Documents\Antigravity Projects" && python -c "from bot.client import run; print('Bot imports OK')"`
Expected: "Bot imports OK"

**Step 3: Verify pipeline builds**

Run: `cd "C:\Users\chase\Documents\Antigravity Projects" && python -c "from pipeline.graph import build_game_pipeline; print('Pipeline imports OK')"`
Expected: "Pipeline imports OK"

---

## Task 3: Character Wizard — Data Module

**Files:**
- Create: `docs/guide/wizard-data.js`

This file contains all PHB Level 1 character creation data as JS objects. It's the single source of truth for the wizard.

**Step 1: Write the data module**

The file must export (via global or ES module) these data objects:

- `RACES` — 9 PHB races with: name, abilityBonuses, speed, size, darkvision, languages, traits[], description, nameTable{male[], female[], surname[]}
- `CLASSES` — 12 PHB classes with: name, hitDie, primaryAbility, savingThrows[], armorProficiencies[], weaponProficiencies[], skillChoices{pick, from[]}, startingEquipment{choices[][], fixed[]}, features[], spellcasting (if applicable: cantripsKnown, spellSlots, spellList[])
- `BACKGROUNDS` — 13 PHB backgrounds with: name, skillProficiencies[], toolProficiencies[], languages, equipment[], feature{name, description}, personalityTraits[], ideals[], bonds[], flaws[]
- `STANDARD_ARRAY` — [15, 14, 13, 12, 10, 8]
- `POINT_BUY_COSTS` — {8:0, 9:1, 10:2, 11:3, 12:4, 13:5, 14:7, 15:9}
- `ABILITY_NAMES` — ["STR", "DEX", "CON", "INT", "WIS", "CHA"]

Fantasy name tables should have at least 15-20 names per race/gender. Use lore-appropriate names from Forgotten Realms.

**Step 2: Verify data loads**

Open in browser console: `<script src="wizard-data.js">` should populate `window.WIZARD_DATA` without errors.

**Step 3: Commit**

```bash
git add docs/guide/wizard-data.js
git commit -m "feat: add PHB Level 1 character data for wizard"
```

---

## Task 4: Character Wizard — HTML Structure

**Files:**
- Create: `docs/guide/character-wizard.html`
- Modify: `docs/guide/character-creation.html` (add link to wizard)
- Modify: every guide page nav (add "Create Character" link)

**Step 1: Write the wizard HTML**

Structure:
- Same nav bar as other guide pages (with new "Create Character" nav link)
- Breadcrumbs: Home > Character Creation > Create Your Character
- Progress bar (steps 1-7, gold accent for current step)
- 7 `<section>` elements, one per step, only current step visible
- Step 1: Name input + "Generate Name" button + concept textarea
- Step 2: Race cards grid (reuse SVG icons from character-creation.html, add `.selectable` class behavior)
- Step 3: Class cards grid (same pattern)
- Step 4: Background cards grid
- Step 5: Ability score assignment (Standard Array / Point Buy / Roll tabs)
- Step 6: Equipment display with class+background auto-populated items
- Step 7: Character sheet summary card + action buttons
- Footer with "Copy for DM" and "Print" buttons
- Load `guide-shared.css`, `character-wizard.css`, `guide-shared.js`, `wizard-data.js`, `character-wizard.js`

Card markup pattern (for selectable cards):
```html
<div class="card selectable accent-teal" data-race="elf">
    <div class="card-header">
        <svg class="icon-md card-icon"><use href="#icon-race-elf"></use></svg>
        <div class="card-title">Elf</div>
        <div class="card-subtitle">Ancient and graceful...</div>
    </div>
    <div class="card-summary">Long-lived beings of otherworldly grace...</div>
    <div class="card-details">
        <p><strong>Racial Traits:</strong></p>
        <ul>...</ul>
    </div>
</div>
```

**Step 2: Add nav link to all guide pages**

Add to the nav-links `<div>` in: `character-creation.html`, `rules.html`, `reference.html`, `dm-setup.html`, `dm-running.html`, `guide.html`:
```html
<a href="character-wizard.html" data-page="character-wizard" class="nav-cta">Create Character</a>
```

**Step 3: Verify page loads**

Open `docs/guide/character-wizard.html` in browser. Should show Step 1 with proper styling.

**Step 4: Commit**

```bash
git add docs/guide/character-wizard.html
git commit -m "feat: add character wizard HTML structure"
```

---

## Task 5: Character Wizard — CSS

**Files:**
- Create: `docs/guide/character-wizard.css`

**Step 1: Write wizard-specific styles**

Key additions beyond `guide-shared.css`:

- `.wizard-progress` — horizontal step indicator bar (numbered circles connected by lines, gold for completed, border for future)
- `.wizard-step` — `display: none` by default, `.wizard-step.active` shows it
- `.card.selectable` — cursor pointer, on click adds `.selected` class with gold border glow + checkmark overlay
- `.card.selectable.selected` — `border-color: var(--gold); box-shadow: 0 0 20px rgba(212,165,68,0.2);`
- `.card.selectable.selected::after` — gold checkmark badge in top-right corner
- `.wizard-nav` — bottom bar with Back/Next buttons (styled like `.console-btn` but larger)
- `.ability-assignment` — grid for stat assignment with dropdowns or drag targets
- `.point-buy-counter` — running total display
- `.dice-roller` — animated dice roll display
- `.name-generator` — button + output area
- `.char-sheet-summary` — final character sheet layout (2-column on desktop, single on mobile)
- `.copy-btn`, `.print-btn` — action buttons with gold accent
- Print stylesheet: `@media print` that shows only the character sheet summary in clean black-on-white

**Step 2: Verify styles**

Refresh character-wizard.html — progress bar, cards, and buttons should render correctly.

**Step 3: Commit**

```bash
git add docs/guide/character-wizard.css
git commit -m "feat: add character wizard styles"
```

---

## Task 6: Character Wizard — Core JS Logic

**Files:**
- Create: `docs/guide/character-wizard.js`

**Step 1: Write the wizard controller**

Key responsibilities:

1. **Step navigation** — `currentStep` state, show/hide sections, update progress bar, enable/disable Next based on required selections
2. **Race selection** — click handler on `.card.selectable[data-race]`, stores selection, shows racial traits summary, updates name generator
3. **Class selection** — same pattern with `[data-class]`
4. **Background selection** — same pattern with `[data-background]`
5. **Name generator** — `generateName(race, gender)` function that picks from `WIZARD_DATA.RACES[race].nameTable`, displays in input field
6. **Ability scores** — three modes:
   - Standard Array: 6 dropdowns, each stat gets one value, no duplicates
   - Point Buy: increment/decrement buttons per stat (min 8, max 15, 27 points total), running point display
   - Roll: "Roll" button simulates 4d6-drop-lowest per stat with brief animation
   - All modes auto-apply racial bonuses and show final modifier
7. **Equipment** — auto-populate from class+background data, render as editable checklist
8. **Summary generation** — compile all selections into a character sheet object, render in `.char-sheet-summary`, calculate: HP = hitDie max + CON mod, AC from armor, proficiency bonus (+2 at level 1), skill proficiencies from class+background+race, saving throw proficiencies from class
9. **Copy for DM** — generate vault-template-formatted markdown string, copy to clipboard
10. **Print** — trigger `window.print()`
11. **localStorage** — save wizard state on every change, restore on page load (so players don't lose progress on refresh)

**Step 2: Verify full wizard flow**

Open in browser, click through all 7 steps:
- Step 1: Enter name or generate one
- Step 2: Select a race (card highlights gold)
- Step 3: Select a class
- Step 4: Select a background
- Step 5: Assign ability scores (try all 3 modes)
- Step 6: Review equipment
- Step 7: See full character sheet, click Copy

**Step 3: Commit**

```bash
git add docs/guide/character-wizard.js
git commit -m "feat: add character wizard interactive logic"
```

---

## Task 7: Update Navigation Across All Guide Pages

**Files:**
- Modify: `docs/guide.html` (home page)
- Modify: `docs/guide/character-creation.html`
- Modify: `docs/guide/rules.html`
- Modify: `docs/guide/reference.html`
- Modify: `docs/guide/dm-setup.html`
- Modify: `docs/guide/dm-running.html`

**Step 1: Add "Create Character" nav link to every page**

In each file's `.nav-links` div, add the wizard link. Also add a prominent call-to-action on the character-creation.html page linking to the wizard.

**Step 2: Add a hero CTA on the guide home page**

On `guide.html`, add a prominent "Create Your Character" button/card linking to the wizard.

**Step 3: Verify navigation**

Click through all pages — "Create Character" link should appear in nav and route correctly.

**Step 4: Commit**

```bash
git add docs/guide.html docs/guide/character-creation.html docs/guide/rules.html docs/guide/reference.html docs/guide/dm-setup.html docs/guide/dm-running.html
git commit -m "feat: add character wizard link to all guide pages"
```

---

## Task 8: Visual QA & Polish

**Files:**
- Modify: `docs/guide/character-wizard.css` (fixes)
- Modify: `docs/guide/character-wizard.js` (fixes)

**Step 1: Mobile test**

Open wizard on mobile viewport (375px width). Verify:
- Progress bar wraps or scrolls horizontally
- Cards stack single-column
- Ability score controls are touch-friendly
- Character sheet summary is readable

**Step 2: Cross-browser test**

Test in Chrome + Firefox. Verify CSS animations, backdrop-filter, clipboard API work.

**Step 3: Test the "Copy for DM" output**

Copy output should match the vault party_member_template.md format:
```markdown
---
type: party_member
name: "[Character Name]"
player: ""
race: "[Race]"
class: "[Class]"
level: 1
hp_current: [HP]
hp_max: [HP]
ac: [AC]
conditions: []
...
---
```

**Step 4: Final commit**

```bash
git add -A docs/guide/
git commit -m "polish: character wizard visual QA and mobile fixes"
```

---

## Task 9: Deploy & Verify Live

**Step 1: Push to GitHub**

```bash
git push origin main
```

**Step 2: Verify GitHub Pages deployment**

Visit: https://chasecjj.github.io/dnd-ai-dm/docs/guide/character-wizard.html
Verify the wizard loads and functions correctly.

**Step 3: Share link with players**

Provide the URL to players for character creation.
