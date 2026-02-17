# Spoiler-Free Session Prep — Brainstorm

## The Problem

The AI DM needs scenes, maps, tokens, and NPCs ready in Foundry VTT so the story flows without awkward pauses. But Chase is both a player and the system admin — he can't prep the content himself without spoiling the story, and the AI can't use GUI-based map tools like Inkarnate.

## The Constraints

- Chase must NOT see what's been prepped ahead of time
- The AI can only interact with tools that have APIs, CLIs, or URL-based interfaces
- Maps need to be decent quality (players will see them)
- The system needs to handle unpredictable player choices (they WILL go off-script)
- Ideally minimal manual intervention once set up

---

## Solution 1: The "Deep Pantry" Approach

**Concept:** Stock Foundry with a massive library of generic, reusable assets ONCE, then let the AI pick from them in real time.

**How it works:**
1. Install 5-6 free Foundry battlemap packs (MAD Cartographer, Miska's Maps, MikWewa, Baileywiki, TacticalMap — all free, all come with walls + lighting pre-built)
2. Import a pool of ~50 common monsters from the dnd5e compendium (goblins, wolves, bandits, skeletons, zombies, orcs, etc.)
3. Tag each scene with keywords using the Tagger module (already installed): "forest", "cave", "tavern", "city", "dungeon", "road", etc.
4. The FoundryArchitect's `switch_scene` action does a fuzzy match against tags instead of exact name matching

**Pros:** No spoilers (generic maps), high quality (community-made with walls/lighting), works TODAY
**Cons:** Limited variety, might reuse the same "cave" map multiple times, no custom maps
**Effort:** Low — a few hours of installing packs and importing monsters

---

## Solution 2: The "Blind Prep" Pipeline

**Concept:** A `!prep` command that runs the full AI planning pipeline in a hidden channel, building out the next session's likely scenes and encounters without Chase seeing the details.

**How it works:**
1. Chase types `!prep` in a private DM with the bot (or a dedicated hidden channel)
2. The CampaignPlanner reads the vault state (quests, location, consequences, story arc)
3. It generates 3-4 likely scenarios for the next session (branching paths)
4. For each scenario, the WorldArchitect describes what scenes/NPCs are needed
5. The FoundryArchitect builds them in Foundry (imports monsters, creates scenes, sets up tokens)
6. Chase gets ONLY a summary like: "Prep complete. 3 scenes ready, 8 NPCs imported, 2 encounters staged."
7. All details go to the moderator log (which Chase can choose to never read)

**Pros:** Tailored to the actual story arc, handles branching, fully automated
**Cons:** Chase could still peek at moderator logs if curious, requires trust in the AI's prep quality
**Effort:** Medium — needs a new prep orchestrator, ~200 lines of code

---

## Solution 3: The "CartographerAgent" with AI Image Generation

**Concept:** A new AI agent that generates custom battlemap images and creates complete Foundry scenes from them.

**How it works:**
1. The WorldArchitect describes a scene: "A forest clearing with a stream, fallen logs, and a ruined shrine. 30x20 grid, twilight lighting."
2. The CartographerAgent sends this to an image generation API (Gemini Imagen, DALL-E, or Stable Diffusion) with a specialized prompt for top-down battlemaps
3. The generated image is saved to Foundry's data directory
4. The CartographerAgent creates a new Scene in Foundry via REST API with:
   - The generated image as the background
   - Grid overlay configured (size, offset)
   - Basic walls around the edges
   - Lighting sources (torches, campfire, etc.)
   - Ambient audio (forest sounds, water, etc.)

**Pros:** Truly custom maps for every situation, no reuse, maximum immersion
**Cons:** AI-generated battlemaps are inconsistent quality (grid alignment issues, style varies), requires an image gen API key/cost, slower than pre-built maps
**Effort:** High — new agent, image gen integration, scene assembly logic, ~400 lines

**Enhancement:** Use AI generation as the BACKGROUND, then overlay a procedural grid + programmatic walls. This separates "making it look good" (AI) from "making it functional" (code).

---

## Solution 4: The "Watabou Hybrid"

**Concept:** Use Watabou's free procedural generators for cities/dungeons (they support URL parameters), then convert the output to Foundry scenes.

**How it works:**
1. For cities: Hit `watabou.github.io/city-generator/?seed=XXXX&size=medium&export=svg`
2. For dungeons: Use the one-page dungeon generator with similar parameters
3. For villages: Use the village generator
4. Capture the SVG/PNG output
5. Create a Foundry scene with the generated map as the background
6. Use the generator's JSON output (when available) to programmatically place walls

**Pros:** Free, procedural (infinite variety), no API key needed, decent aesthetic
**Cons:** Limited to city/dungeon/village types (no forests, caves, interiors), browser-based (needs scraping or screenshot), style may not match other maps
**Effort:** Medium — URL builder + image capture + scene creation

---

## Solution 5: The "Scheduled Night Owl" (using Cowork Shortcuts)

**Concept:** A scheduled shortcut that runs overnight before each session, automatically prepping everything while Chase sleeps.

**How it works:**
1. Create a Cowork shortcut scheduled to run at 2 AM before game day
2. The shortcut triggers the Blind Prep Pipeline (Solution 2)
3. By morning, Foundry is stocked with scenes, monsters, and encounters
4. Chase wakes up, launches the bot, and plays — everything is ready
5. A brief non-spoiler summary is posted to Discord: "Session prep complete ✅"

**Pros:** Zero manual effort, prep happens while sleeping, true "set and forget"
**Cons:** Requires the bot + Foundry + Docker to be running overnight, prep is based on predictions (might miss what players actually do)
**Effort:** Low (on top of Solution 2) — just scheduling

---

## Solution 6: The "Theater of Mind + Combat Maps" Split

**Concept:** Don't try to have a map for EVERYTHING. Only generate maps when combat happens. Use atmospheric splash images for exploration/roleplay.

**How it works:**
1. For exploration/RP: The Storyteller generates a mood image (single illustration, not a battlemap) — just a pretty scene card shown in Discord or Foundry
2. For combat: The full FoundryArchitect pipeline kicks in — grabs a matching scene from the library, imports/places monsters, starts the encounter
3. This mirrors how most actual D&D tables work — theater of mind for RP, grid maps for fights

**Pros:** WAY less prep needed, focuses effort where it matters (combat), mood images are easy for AI to generate well (they don't need grids), most authentic D&D experience
**Cons:** Less visual immersion during exploration, players might want to see where they are
**Effort:** Low-Medium — mood image generation + existing combat pipeline

---

## Solution 7: The "Living World Map"

**Concept:** Instead of separate scenes, build ONE massive interconnected world map with fog of war. The AI reveals sections as the party explores.

**How it works:**
1. Start with a large regional map (Waterdeep, or the campaign area)
2. All locations exist on the map but are hidden under fog of war
3. As the party moves, the FoundryArchitect reveals the relevant section
4. Combat encounters overlay temporary battle grids on top of the world map
5. Zoom levels handle the transition from "walking through the city" to "fighting in the alley"

**Pros:** Seamless exploration, no jarring scene switches, truly persistent world, very immersive
**Cons:** Massive upfront effort to build the world map, Foundry fog of war has limitations at large scales, needs careful grid management
**Effort:** Very High for initial setup, but low ongoing maintenance

---

## Solution 8: The "Community Module Scraper"

**Concept:** Foundry has THOUSANDS of free community scene modules. Build a tool that searches, downloads, and imports relevant modules based on what the campaign needs.

**How it works:**
1. The prep pipeline identifies needed scene types ("forest path", "city market", "underground temple")
2. A scraper searches the Foundry package registry for matching free scene modules
3. Downloads and installs matching packs automatically
4. Tags and indexes the new scenes for the FoundryArchitect to use

**Pros:** Massive variety, professional quality, free, community-maintained
**Cons:** Requires Foundry package API access, quality varies, might download too much, potential copyright/licensing concerns with automated downloading
**Effort:** Medium — Foundry package registry API + download automation

---

## Recommended Combination

The most practical path is probably **Solution 1 + Solution 2 + Solution 6**, layered:

1. **NOW:** Install free battlemap packs + import common monsters (Solution 1 — "Deep Pantry")
   - Gets you 100+ ready-made scenes immediately
   - 2-3 hours of setup, zero code

2. **NEXT:** Build the `!prep` command (Solution 2 — "Blind Prep")
   - Tailors the generic library to upcoming story needs
   - Imports specific monsters, stages encounters
   - Medium coding effort

3. **LATER:** Add the CartographerAgent (Solution 3) for custom maps
   - Only for unique locations that don't match any generic scene
   - AI-generated battlemaps as a fallback
   - Can be improved incrementally over time

4. **OPTIONAL:** Schedule it with Cowork shortcuts (Solution 5)
   - Once the prep pipeline works, automate it before game day

This gives you immediate improvement (maps TODAY), smart prep (tailored scenes), and a growth path toward fully custom AI-generated content — all without spoiling Chase.
