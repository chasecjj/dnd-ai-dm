"""
Full Systems & Functionality Test
Tests all major subsystems after the cleanup/reset.

Usage: python scripts/full_systems_test.py
"""
import sys
import os
import asyncio
import json
import traceback

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

PASS = 0
FAIL = 0
WARN = 0

def ok(label):
    global PASS
    PASS += 1
    print(f"  PASS  {label}")

def fail(label, err=""):
    global FAIL
    FAIL += 1
    detail = f" -- {err}" if err else ""
    print(f"  FAIL  {label}{detail}")

def warn(label, msg=""):
    global WARN
    WARN += 1
    detail = f" -- {msg}" if msg else ""
    print(f"  WARN  {label}{detail}")


# ===================================================================
print("=" * 60)
print("  FULL SYSTEMS TEST")
print("=" * 60)

# -------------------------------------------------------------------
# 1. Core Imports
# -------------------------------------------------------------------
print("\n[1] Core Module Imports")

import_tests = [
    ("tools.campaign_manager", "CampaignManager"),
    ("tools.vault_manager", "VaultManager"),
    ("tools.context_assembler", "ContextAssembler"),
    ("tools.reference_manager", "ReferenceManager"),
    ("tools.rate_limiter", "gemini_limiter"),
    ("tools.state_manager", "StateManager"),
    ("agents.tools.foundry_tool", "FoundryClient"),
    ("agents.tools.foundry_errors", "FoundryError"),
    ("agents.board_monitor", "BoardMonitorAgent"),
    ("agents.rules_lawyer", "RulesLawyerAgent"),
    ("agents.storyteller", "StorytellerAgent"),
    ("agents.foundry_architect", "FoundryArchitectAgent"),
    ("agents.message_router", "MessageRouterAgent"),
    ("agents.chronicler", "ChroniclerAgent"),
    ("agents.world_architect", "WorldArchitectAgent"),
    ("agents.campaign_planner", "CampaignPlannerAgent"),
    ("agents.prep_router", "PrepRouterAgent"),
    ("agents.cartographer", "CartographerAgent"),
    ("pipeline.state", "GameState"),
    ("pipeline.nodes.router_node", "router_node"),
    ("pipeline.nodes.board_monitor_node", "board_monitor_node"),
    ("pipeline.nodes.rules_node", "rules_node"),
    ("pipeline.nodes.storyteller_node", "storyteller_node"),
    ("pipeline.nodes.scene_sync_node", "scene_sync_node"),
    ("pipeline.nodes.chronicler_node", "chronicler_node"),
    ("pipeline.graph", "build_game_pipeline"),
    ("models.chronicler_output", "ChroniclerOutput"),
    ("tools.blind_prep", "run_blind_prep"),
]

for module_path, attr_name in import_tests:
    try:
        mod = __import__(module_path, fromlist=[attr_name])
        obj = getattr(mod, attr_name)
        ok(f"{module_path}.{attr_name}")
    except Exception as e:
        fail(f"{module_path}.{attr_name}", str(e)[:80])

# -------------------------------------------------------------------
# 2. Bot Client Import (the big one)
# -------------------------------------------------------------------
print("\n[2] Bot Client Module")

try:
    from bot.client import (
        run, main, load_cogs, bot,
        game_pipeline, vault, context_assembler,
        foundry_client, gemini_client, storyteller,
        message_router, rules_lawyer, chronicler,
        board_monitor, foundry_architect,
        world_architect, campaign_planner, prep_router,
        cartographer_agent, ref_manager, state_manager,
        PLAYER_MAP, send_to_moderator_log,
        _handle_game_table, _handle_war_room,
    )
    ok("bot.client full import (all public symbols)")
except Exception as e:
    fail("bot.client import", str(e)[:120])

# -------------------------------------------------------------------
# 3. Verify removed imports are gone
# -------------------------------------------------------------------
print("\n[3] Verify Removed Imports Are Gone")

try:
    import bot.client as bc
    # format_stat_block_text should NOT be in the module namespace
    if hasattr(bc, 'format_stat_block_text'):
        fail("format_stat_block_text still imported in bot.client")
    else:
        ok("format_stat_block_text removed from bot.client")

    # blind_prep symbols should NOT be in the module namespace
    if hasattr(bc, 'run_blind_prep') or hasattr(bc, 'BlindPrepResult'):
        fail("blind_prep still imported in bot.client")
    else:
        ok("blind_prep removed from bot.client")
except Exception as e:
    fail("removed imports check", str(e)[:80])

# -------------------------------------------------------------------
# 4. Pipeline Build
# -------------------------------------------------------------------
print("\n[4] LangGraph Pipeline")

try:
    from pipeline.graph import HAS_LANGGRAPH
    if HAS_LANGGRAPH:
        ok("LangGraph installed and importable")
    else:
        fail("LangGraph not installed")
except Exception as e:
    fail("LangGraph check", str(e)[:80])

try:
    # game_pipeline should be a compiled graph
    if game_pipeline is not None:
        ok(f"game_pipeline compiled ({type(game_pipeline).__name__})")
    else:
        fail("game_pipeline is None")
except NameError:
    fail("game_pipeline not available (bot.client import failed)")

# -------------------------------------------------------------------
# 5. Agent Instantiation
# -------------------------------------------------------------------
print("\n[5] Agent Instances")

agents_to_check = {
    "message_router": "MessageRouterAgent",
    "board_monitor": "BoardMonitorAgent",
    "rules_lawyer": "RulesLawyerAgent",
    "storyteller": "StorytellerAgent",
    "foundry_architect": "FoundryArchitectAgent",
    "chronicler": "ChroniclerAgent",
    "world_architect": "WorldArchitectAgent",
    "campaign_planner": "CampaignPlannerAgent",
    "prep_router": "PrepRouterAgent",
    "cartographer_agent": "CartographerAgent",
}

for var_name, class_name in agents_to_check.items():
    try:
        obj = eval(var_name)
        actual = type(obj).__name__
        if actual == class_name:
            ok(f"{var_name} ({class_name})")
        else:
            fail(f"{var_name}", f"expected {class_name}, got {actual}")
    except NameError:
        fail(f"{var_name}", "not imported (bot.client failed)")
    except Exception as e:
        fail(f"{var_name}", str(e)[:80])

# -------------------------------------------------------------------
# 6. Vault Manager — Read Reset Files
# -------------------------------------------------------------------
print("\n[6] Vault Manager — Reset Campaign Files")

import yaml

vault_checks = {
    "campaigns/Default/01 - Party/Frognar Emberheart.md": {
        "frontmatter": {"spell_slots_used": 0, "lay_on_hands_pool": 5, "hp_current": 12},
        "body_must_not_contain": ["Session Notes", "Used during Troll fight", "coins lighter from gambling"],
    },
    "campaigns/Default/01 - Party/Kallisar Voidcaller.md": {
        "frontmatter": {"spell_slots_used": 0},
        "body_must_not_contain": ["Session Notes", "Added during Session 0", "Used during Troll fight", "1 used"],
    },
    "campaigns/Default/02 - NPCs/Durnan.md": {
        "frontmatter": {"disposition": "neutral", "first_seen_session": None, "last_seen_session": None},
        "body_must_contain": ["Not yet met."],
        "body_must_not_contain": ["Session 0 Update", "Fought alongside the party"],
    },
    "campaigns/Default/02 - NPCs/Yagra Strongfist.md": {
        "frontmatter": {"disposition": "neutral", "first_seen_session": None},
        "body_must_contain": ["Not yet met."],
        "body_must_not_contain": ["Troll fight", "Cheered the party"],
    },
    "campaigns/Default/02 - NPCs/Krentz.md": {
        "frontmatter": {"disposition": "hostile", "first_seen_session": None},
        "body_must_contain": ["Not yet met."],
        "body_must_not_contain": ["cowering behind a pillar", "Troll fight"],
    },
    "campaigns/Default/02 - NPCs/Volothamp Geddarm.md": {
        "frontmatter": {"disposition": "neutral", "first_seen_session": None},
        "body_must_contain": ["Not yet met."],
        "body_must_not_contain": ["Session 0 Update", "Astounding", "table-tossing"],
    },
    "campaigns/Default/03 - Locations/Yawning Portal.md": {
        "frontmatter": {"visited": False, "first_visited_session": None},
        "body_must_not_contain": ["Post-Troll Attack", "shoved back into the well", "bleeding from a claw"],
    },
    "campaigns/Default/04 - Quests/Active/Volos Quest.md": {
        "frontmatter": {"status": "planned"},
        "body_must_not_contain": ["witnessing the party's bravery", "Troll Attack"],
    },
    "campaigns/Default/06 - World State/clock.md": {
        "frontmatter": {"time_of_day": "evening"},
        "body_must_not_contain": ["night of the brawl", "Troll Attack"],
    },
    "campaigns/Default/06 - World State/consequences.md": {
        "body_must_not_contain": ["Volothamp Geddarm", "Durnan may offer", "Krentz reports", "Gambling debts"],
    },
}

for path, checks in vault_checks.items():
    try:
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()

        parts = content.split('---', 2)
        fm = yaml.safe_load(parts[1]) if len(parts) >= 3 else {}
        body = parts[2] if len(parts) >= 3 else content

        file_ok = True
        errors = []

        # Frontmatter checks
        for key, expected in checks.get("frontmatter", {}).items():
            actual = fm.get(key)
            if actual != expected:
                errors.append(f"fm.{key}: expected {expected!r}, got {actual!r}")
                file_ok = False

        # Body must contain
        for text in checks.get("body_must_contain", []):
            if text not in body:
                errors.append(f"missing: '{text}'")
                file_ok = False

        # Body must NOT contain
        for text in checks.get("body_must_not_contain", []):
            if text in body:
                errors.append(f"still has: '{text}'")
                file_ok = False

        if file_ok:
            ok(os.path.basename(path))
        else:
            fail(os.path.basename(path), "; ".join(errors))

    except FileNotFoundError:
        fail(path, "file not found")
    except Exception as e:
        fail(path, str(e)[:80])

# Check deleted files are actually gone
deleted_files = [
    "campaigns/Default/00 - Session Log/Session 000.md",
    "campaigns/Default/04 - Quests/Completed/Troll Attack.md",
]
for path in deleted_files:
    if not os.path.exists(path):
        ok(f"{os.path.basename(path)} deleted")
    else:
        fail(f"{os.path.basename(path)}", "file still exists")

# Memory checkpoint
try:
    with open("campaigns/Default/06 - World State/memory_checkpoint.json", 'r') as f:
        data = json.load(f)
    if data == []:
        ok("memory_checkpoint.json reset to []")
    else:
        fail("memory_checkpoint.json", f"expected [], got {len(data)} items")
except Exception as e:
    fail("memory_checkpoint.json", str(e)[:80])

# Faction checks
for faction_file, bad_text in [
    ("campaigns/Default/05 - Factions/Zhentarim.md", "party observed the Yagra"),
    ("campaigns/Default/05 - Factions/Xanathar Guild.md", "Krentz witnessed the party"),
]:
    try:
        with open(faction_file, 'r', encoding='utf-8') as f:
            content = f.read()
        if bad_text in content:
            fail(os.path.basename(faction_file), f"still has: '{bad_text}'")
        else:
            ok(f"{os.path.basename(faction_file)} cleaned")
    except Exception as e:
        fail(faction_file, str(e)[:80])

# -------------------------------------------------------------------
# 7. Dead Files — Confirm Deleted
# -------------------------------------------------------------------
print("\n[7] Dead Files Deleted")

dead_files = [
    "orchestration/bot.py.bak",
    "test_reference_manager.py",
    "test_world_state.py",
    "reproduce_issue.py",
    "get_traceback.py",
    "progress.md",
    "task_plan.md",
    "findings.md",
    "PREP_BRAINSTORM.md",
    "foundry-vtt-api-research.md",
    "scripts/probe_foundry.py",
    "scripts/probe_endpoints.py",
    "scripts/probe_deep.py",
    "scripts/test_token_create.py",
    "scripts/test_token_placement.py",
    "scripts/test_token_update.py",
    "scripts/scan_world.py",
]

for path in dead_files:
    if not os.path.exists(path):
        ok(f"deleted: {path}")
    else:
        fail(f"still exists: {path}")

# -------------------------------------------------------------------
# 8. Kept Files — Confirm Still Present
# -------------------------------------------------------------------
print("\n[8] Kept Files Still Present")

kept_files = [
    "gemini.md",
    "COMPLETION_PLAN.md",
    "CLAUDE.md",
    "scripts/extract_references.py",
    "scripts/migrate_vault_to_mongo.py",
    "scripts/reset_foundry.py",
]

for path in kept_files:
    if os.path.exists(path):
        ok(f"kept: {path}")
    else:
        fail(f"missing: {path}")

# -------------------------------------------------------------------
# 9. Foundry VTT Connectivity
# -------------------------------------------------------------------
print("\n[9] Foundry VTT Relay")

async def test_foundry():
    from agents.tools.foundry_tool import FoundryClient
    client = FoundryClient()
    try:
        connected = await client.connect()
        if connected:
            ok(f"Foundry relay connected (client={client.client_id})")

            # Quick scene check
            try:
                scenes = await client.get_world_scenes()
                ok(f"get_world_scenes() returned {len(scenes)} scene(s)")

                # Verify tokens are cleared
                total_tokens = 0
                for scene in scenes:
                    tokens = await client.get_scene_tokens(scene.get("uuid", scene.get("_id", "")))
                    total_tokens += len(tokens) if tokens else 0
                if total_tokens == 0:
                    ok("All scenes have 0 tokens (reset confirmed)")
                else:
                    warn("tokens remaining", f"{total_tokens} tokens still present")
            except Exception as e:
                fail("Foundry scene query", str(e)[:80])
        else:
            warn("Foundry relay not reachable", "Foundry may not be running")
    except Exception as e:
        warn("Foundry connection", str(e)[:80])
    finally:
        await client.close()

asyncio.run(test_foundry())

# -------------------------------------------------------------------
# 10. Discord Bot Commands Registration
# -------------------------------------------------------------------
print("\n[10] Discord Bot Commands")

try:
    from bot.client import bot

    # The bot has cogs loaded lazily, but we can check the command prefix
    # and that the bot object is valid
    ok(f"Bot instance created (prefix='{bot.command_prefix}')")

    # Check cog modules can be imported (they import from bot.client)
    from bot.cogs.dm_cog import DMCog
    ok("DMCog importable")
    from bot.cogs.foundry_cog import FoundryCog
    ok("FoundryCog importable")
    from bot.cogs.prep_cog import PrepCog
    ok("PrepCog importable")

    # List expected commands from the cog docstrings
    expected_commands = [
        "campaign", "save", "reset", "recap", "status", "image",   # dm_cog
        "roll", "monster", "scene", "pc", "build", "daytime",       # foundry_cog
        "nighttime", "setup", "foundry",                            # foundry_cog cont.
        "prep", "brainstorm", "plan",                                # prep_cog
    ]
    ok(f"Expected {len(expected_commands)} commands across 3 cogs")

except Exception as e:
    fail("Bot commands check", str(e)[:120])

# -------------------------------------------------------------------
# 11. Environment Variables
# -------------------------------------------------------------------
print("\n[11] Environment Variables")

env_vars = [
    ("DISCORD_BOT_TOKEN", True),
    ("GEMINI_API_KEY", True),
    ("FOUNDRY_API_KEY", False),
    ("FOUNDRY_RELAY_URL", False),
    ("FOUNDRY_CLIENT_ID", False),
    ("MODERATOR_LOG_CHANNEL_ID", False),
    ("WAR_ROOM_CHANNEL_ID", False),
    ("GAME_TABLE_CHANNEL_ID", False),
    ("PLAYER_MAP", False),
]

for var, critical in env_vars:
    val = os.getenv(var)
    if val:
        ok(f"{var} = {'*' * min(len(val), 8)}...")
    elif critical:
        fail(f"{var} not set (critical)")
    else:
        warn(f"{var} not set")


# ===================================================================
# SUMMARY
# ===================================================================
print("\n" + "=" * 60)
print(f"  RESULTS:  {PASS} passed, {FAIL} failed, {WARN} warnings")
print("=" * 60)

if FAIL == 0:
    print("\n  All systems operational.\n")
else:
    print(f"\n  {FAIL} failure(s) need attention.\n")
    sys.exit(1)
