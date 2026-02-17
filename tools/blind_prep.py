"""
Blind Prep Pipeline — Spoiler-free session preparation orchestrator.

Chains multiple AI agents to prepare sessions without revealing plot details to Chase.
All spoiler content goes to the moderator log; only a non-spoiler summary reaches the player.

Pipeline:
  1. CampaignPlanner → generates likely scenarios and needed assets
  2. WorldArchitect → creates NPCs and locations for each scenario
  3. CartographerAgent → generates battlemaps for locations without scenes (optional)
  4. FoundryArchitect → imports monsters, places tokens, stages scenes
  5. Report → non-spoiler summary to player, full details to mod log
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional, Any, Dict, List

from google import genai
from tools.rate_limiter import gemini_limiter

logger = logging.getLogger('BlindPrep')


# ---------------------------------------------------------------------------
# Result Dataclass
# ---------------------------------------------------------------------------

@dataclass
class BlindPrepResult:
    """Result of a blind prep run — split into spoiler/non-spoiler content."""
    summary: str = ""               # Non-spoiler summary for the player
    details: str = ""               # Full spoiler log for moderator channel
    scenes_created: int = 0
    npcs_created: int = 0
    locations_created: int = 0
    encounters_staged: int = 0
    errors: list = field(default_factory=list)


# ---------------------------------------------------------------------------
# Scenario Extraction Prompt
# ---------------------------------------------------------------------------

SCENARIO_EXTRACTION_PROMPT = """You are a D&D session prep planner. Given the DM's description of what's
coming up next, analyze the campaign context and generate a structured prep plan.

Think about 2-3 likely scenario branches the players might take, and for each, identify
what assets (locations, NPCs, monsters) need to be prepared.

## Campaign Context
{campaign_context}

## DM's Prep Request
{description}

You MUST respond with ONLY a valid JSON object (no markdown, no explanation):
{{
    "session_overview": "One sentence describing the session theme",
    "scenarios": [
        {{
            "name": "Scenario branch name",
            "likelihood": "high/medium/low",
            "locations_needed": [
                {{
                    "name": "Location Name",
                    "type": "tavern/dungeon/wilderness/city/etc",
                    "description": "Brief sensory description for map generation",
                    "lighting": "bright/dim/dark",
                    "grid_size": "30x20"
                }}
            ],
            "npcs_needed": [
                {{
                    "name": "NPC Name",
                    "description": "Brief description including role, race, personality"
                }}
            ],
            "monsters_needed": [
                {{
                    "name": "Monster Name",
                    "quantity": 1,
                    "cr": "1/4"
                }}
            ],
            "encounter_description": "Brief description of the encounter setup"
        }}
    ]
}}

IMPORTANT:
- Only include locations/NPCs/monsters that don't already exist in the campaign context
- Keep it realistic — 2-3 scenarios max, 1-3 locations each
- Monster names should match D&D 5e SRD names (e.g. "Goblin", "Bandit Captain", "Young Dragon")
- Grid sizes should be practical: "20x20" for small, "30x20" for medium, "40x30" for large
"""


# ---------------------------------------------------------------------------
# Core Pipeline
# ---------------------------------------------------------------------------

async def run_blind_prep(
    description: str,
    campaign_planner,
    world_architect,
    foundry_architect,
    cartographer,           # Can be None — map generation is optional
    foundry_client,
    gemini_client,
    model_id: str,
    vault,
) -> BlindPrepResult:
    """Run the full blind prep pipeline.

    Args:
        description: DM's natural-language description of the upcoming session.
        campaign_planner: CampaignPlannerAgent instance.
        world_architect: WorldArchitectAgent instance.
        foundry_architect: FoundryArchitectAgent instance.
        cartographer: CartographerAgent instance (or None to skip map generation).
        foundry_client: FoundryClient for Foundry VTT operations.
        gemini_client: Google Gemini client for direct AI calls.
        model_id: Gemini model ID (e.g. "gemini-2.0-flash").
        vault: VaultManager for reading/writing campaign files.

    Returns:
        BlindPrepResult with non-spoiler summary and full spoiler details.
    """
    result = BlindPrepResult()
    detail_log = []     # Accumulates spoiler details
    summary_parts = []  # Accumulates non-spoiler summary lines

    logger.info(f"Blind prep started: {description}")
    detail_log.append(f"=== BLIND PREP SESSION ===")
    detail_log.append(f"Request: {description}")
    detail_log.append("")

    # ------------------------------------------------------------------
    # Step 1: Generate scenario plan via AI
    # ------------------------------------------------------------------
    logger.info("Step 1: Generating scenario plan...")
    detail_log.append("--- STEP 1: SCENARIO PLANNING ---")

    scenarios = await _generate_scenarios(
        description, campaign_planner, gemini_client, model_id, vault
    )

    if not scenarios:
        result.summary = "⚠️ Could not generate prep scenarios. Try being more specific."
        result.details = "\n".join(detail_log)
        return result

    session_overview = scenarios.get("session_overview", "Session prep")
    scenario_list = scenarios.get("scenarios", [])
    detail_log.append(f"Overview: {session_overview}")
    detail_log.append(f"Scenarios: {len(scenario_list)}")

    for sc in scenario_list:
        detail_log.append(f"\n  Scenario: {sc.get('name', '?')} ({sc.get('likelihood', '?')})")
        detail_log.append(f"  Locations: {[l.get('name') for l in sc.get('locations_needed', [])]}")
        detail_log.append(f"  NPCs: {[n.get('name') for n in sc.get('npcs_needed', [])]}")
        detail_log.append(f"  Monsters: {[m.get('name') for m in sc.get('monsters_needed', [])]}")

    # ------------------------------------------------------------------
    # Step 2: Create locations and NPCs via WorldArchitect
    # ------------------------------------------------------------------
    logger.info("Step 2: Creating locations and NPCs...")
    detail_log.append("\n--- STEP 2: ASSET CREATION ---")

    # Collect unique locations and NPCs across all scenarios
    all_locations = []
    all_npcs = []
    seen_loc_names = set()
    seen_npc_names = set()

    for sc in scenario_list:
        for loc in sc.get("locations_needed", []):
            name = loc.get("name", "")
            if name and name.lower() not in seen_loc_names:
                seen_loc_names.add(name.lower())
                all_locations.append(loc)
        for npc in sc.get("npcs_needed", []):
            name = npc.get("name", "")
            if name and name.lower() not in seen_npc_names:
                seen_npc_names.add(name.lower())
                all_npcs.append(npc)

    # Check existing vault entries to avoid duplicates
    existing_locations = _get_existing_location_names(vault)
    existing_npcs = _get_existing_npc_names(vault)

    # Create missing locations
    for loc in all_locations:
        name = loc.get("name", "")
        if name.lower() in existing_locations:
            detail_log.append(f"  [SKIP] Location '{name}' already exists in vault")
            continue

        try:
            await gemini_limiter.acquire()
            loc_desc = f"{loc.get('description', name)} — {loc.get('type', 'unknown')} location"
            loc_result = await world_architect.create_location(loc_desc)
            result.locations_created += 1
            detail_log.append(f"  [CREATE] Location: {name}")
            detail_log.append(f"    {loc_result[:200]}")
        except Exception as e:
            err_msg = f"Failed to create location '{name}': {e}"
            logger.warning(err_msg)
            result.errors.append(err_msg)
            detail_log.append(f"  [ERROR] {err_msg}")

    # Create missing NPCs
    for npc in all_npcs:
        name = npc.get("name", "")
        if name.lower() in existing_npcs:
            detail_log.append(f"  [SKIP] NPC '{name}' already exists in vault")
            continue

        try:
            await gemini_limiter.acquire()
            npc_result = await world_architect.create_npc(npc.get("description", name))
            result.npcs_created += 1
            detail_log.append(f"  [CREATE] NPC: {name}")
            detail_log.append(f"    {npc_result[:200]}")
        except Exception as e:
            err_msg = f"Failed to create NPC '{name}': {e}"
            logger.warning(err_msg)
            result.errors.append(err_msg)
            detail_log.append(f"  [ERROR] {err_msg}")

    # ------------------------------------------------------------------
    # Step 3: Generate maps for locations without existing Foundry scenes
    # ------------------------------------------------------------------
    logger.info("Step 3: Generating maps...")
    detail_log.append("\n--- STEP 3: MAP GENERATION ---")

    if cartographer is not None and foundry_client and foundry_client.is_connected:
        for loc in all_locations:
            name = loc.get("name", "")
            # Check if Foundry already has a matching scene
            try:
                existing_scenes = foundry_client.search_scenes(name)
                if existing_scenes:
                    detail_log.append(f"  [SKIP] Scene for '{name}' already exists in Foundry")
                    continue
            except Exception:
                pass  # Search failed — try generating anyway

            try:
                await gemini_limiter.acquire()
                map_result = await cartographer.generate_scene(
                    location_name=name,
                    description=loc.get("description", ""),
                    grid_size=loc.get("grid_size", "30x20"),
                )
                if map_result.get("success"):
                    result.scenes_created += 1
                    detail_log.append(f"  [CREATE] Map: {name} -> {map_result.get('image_path', '?')}")
                else:
                    detail_log.append(f"  [FAIL] Map for '{name}': {map_result.get('error', 'Unknown')}")
            except Exception as e:
                err_msg = f"Map generation failed for '{name}': {e}"
                logger.warning(err_msg)
                result.errors.append(err_msg)
                detail_log.append(f"  [ERROR] {err_msg}")
    else:
        if cartographer is None:
            detail_log.append("  [SKIP] CartographerAgent not available — skipping map generation")
        else:
            detail_log.append("  [SKIP] Foundry not connected — skipping map generation")

    # ------------------------------------------------------------------
    # Step 4: Stage encounters in Foundry via FoundryArchitect
    # ------------------------------------------------------------------
    logger.info("Step 4: Staging encounters...")
    detail_log.append("\n--- STEP 4: ENCOUNTER STAGING ---")

    if foundry_client and foundry_client.is_connected:
        for sc in scenario_list:
            monsters = sc.get("monsters_needed", [])
            encounter_desc = sc.get("encounter_description", "")
            if not monsters and not encounter_desc:
                continue

            # Build a Foundry request to import monsters
            monster_names = [f"{m.get('quantity', 1)}x {m.get('name', '?')}" for m in monsters]
            request = f"Import these monsters and prepare them (do NOT start combat): {', '.join(monster_names)}"
            if encounter_desc:
                request += f"\nEncounter setup: {encounter_desc}"

            try:
                await gemini_limiter.acquire()
                arch_result = await foundry_architect.process_request(request)
                result.encounters_staged += 1
                detail_log.append(f"  [STAGE] {sc.get('name', '?')}: {monster_names}")
                detail_log.append(f"    Architect: {arch_result[:200]}")
            except Exception as e:
                err_msg = f"Encounter staging failed for '{sc.get('name', '?')}': {e}"
                logger.warning(err_msg)
                result.errors.append(err_msg)
                detail_log.append(f"  [ERROR] {err_msg}")
    else:
        detail_log.append("  [SKIP] Foundry not connected — skipping encounter staging")

    # ------------------------------------------------------------------
    # Step 5: Build reports
    # ------------------------------------------------------------------
    logger.info("Step 5: Building reports...")

    # Non-spoiler summary (what the player sees)
    summary_parts.append(f"**Session theme:** Preparation complete!")
    summary_parts.append("")

    counts = []
    if result.locations_created > 0:
        counts.append(f"📍 {result.locations_created} location{'s' if result.locations_created > 1 else ''}")
    if result.npcs_created > 0:
        counts.append(f"👤 {result.npcs_created} NPC{'s' if result.npcs_created > 1 else ''}")
    if result.scenes_created > 0:
        counts.append(f"🗺️ {result.scenes_created} map{'s' if result.scenes_created > 1 else ''}")
    if result.encounters_staged > 0:
        counts.append(f"⚔️ {result.encounters_staged} encounter{'s' if result.encounters_staged > 1 else ''}")

    if counts:
        summary_parts.append("**Created:**")
        summary_parts.extend(counts)
    else:
        summary_parts.append("Everything was already in place — no new assets needed!")

    if result.errors:
        summary_parts.append(f"\n⚠️ {len(result.errors)} issue{'s' if len(result.errors) > 1 else ''} logged to moderator channel.")

    summary_parts.append("\n*Detailed prep notes are in the moderator log.*")
    summary_parts.append("*You can avoid spoilers by not reading that channel!*")

    result.summary = "\n".join(summary_parts)
    result.details = "\n".join(detail_log)

    logger.info(
        f"Blind prep complete: {result.locations_created} locations, "
        f"{result.npcs_created} NPCs, {result.scenes_created} maps, "
        f"{result.encounters_staged} encounters, {len(result.errors)} errors"
    )

    return result


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

async def _generate_scenarios(
    description: str,
    campaign_planner,
    gemini_client,
    model_id: str,
    vault,
) -> Optional[Dict[str, Any]]:
    """Use AI to generate structured prep scenarios from the DM's description.

    Returns parsed JSON dict or None on failure.
    """
    try:
        # Build campaign context
        from tools.context_assembler import ContextAssembler
        # We'll call campaign_planner's context assembler to get the context
        campaign_context = campaign_planner.context.build_campaign_planner_context()

        prompt = SCENARIO_EXTRACTION_PROMPT.format(
            campaign_context=campaign_context,
            description=description,
        )

        await gemini_limiter.acquire()
        response = await gemini_client.aio.models.generate_content(
            model=model_id,
            contents=prompt,
            config=genai.types.GenerateContentConfig(
                temperature=0.3,
                response_mime_type="application/json",
            )
        )

        text = response.text.strip()
        # Handle markdown-wrapped JSON
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()

        scenarios = json.loads(text)
        logger.info(f"Generated {len(scenarios.get('scenarios', []))} scenarios")
        return scenarios

    except json.JSONDecodeError as e:
        logger.error(f"Scenario JSON parse error: {e}")
        return None
    except Exception as e:
        logger.error(f"Scenario generation failed: {e}", exc_info=True)
        return None


def _get_existing_location_names(vault) -> set:
    """Get lowercase names of all locations currently in the vault."""
    names = set()
    try:
        files = vault.list_files("03 - Locations")
        for f in files:
            result = vault.read_file(f)
            if result:
                fm, _ = result
                name = fm.get("name", "")
                if name:
                    names.add(name.lower())
    except Exception:
        pass
    return names


def _get_existing_npc_names(vault) -> set:
    """Get lowercase names of all NPCs currently in the vault."""
    names = set()
    try:
        files = vault.list_files("02 - NPCs")
        for f in files:
            result = vault.read_file(f)
            if result:
                fm, _ = result
                name = fm.get("name", "")
                if name:
                    names.add(name.lower())
    except Exception:
        pass
    return names
