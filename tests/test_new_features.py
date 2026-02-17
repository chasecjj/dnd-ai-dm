"""Test new FoundryClient features against the live Foundry VTT relay."""
import sys, json, os
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from agents.tools.foundry_tool import FoundryClient, format_stat_block_text

fc = FoundryClient()
if not fc.connect():
    print("❌ Cannot connect to Foundry VTT relay!")
    sys.exit(1)

print("✅ Connected to relay\n")

# ── Test 1: roll_dice ─────────────────────────────────────────────
print("=" * 50)
print("TEST 1: roll_dice('1d20+5')")
print("=" * 50)
try:
    r = fc.roll_dice("1d20+5")
    print(f"  Total: {r['total']}")
    print(f"  Formula: {r['formula']}")
    print(f"  Dice: {r['dice']}")
    print(f"  Critical: {r['isCritical']}")
    print(f"  Fumble: {r['isFumble']}")
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

# ── Test 2: search_actors ────────────────────────────────────────
print("\n" + "=" * 50)
print("TEST 2: search_actors('Goblin')")
print("=" * 50)
try:
    results = fc.search_actors("Goblin")
    print(f"  Found {len(results)} results")
    for r in results[:3]:
        print(f"    {r['name']} ({r['uuid']})")
    print("  ✅ PASS" if results else "  ⚠️ No results (search may need Quick Insert)")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

# ── Test 3: search_scenes ────────────────────────────────────────
print("\n" + "=" * 50)
print("TEST 3: search_scenes('Forest')")
print("=" * 50)
try:
    results = fc.search_scenes("Forest")
    print(f"  Found {len(results)} results")
    for r in results[:3]:
        print(f"    {r['name']} ({r.get('packageName', 'World')})")
    print("  ✅ PASS" if results else "  ⚠️ No results")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

# ── Test 4: get_actor_stat_block ─────────────────────────────────
print("\n" + "=" * 50)
print("TEST 4: get_actor_stat_block (Goblin from compendium)")
print("=" * 50)
try:
    stat = fc.get_actor_stat_block("Compendium.dnd5e.monsters.TjWQOgI3A4UAl7lC")
    print(f"  Name: {stat['name']}")
    print(f"  AC: {stat['ac']}")
    print(f"  HP: {stat['hp']}")
    print(f"  CR: {stat['cr']}")
    ab = stat['abilities']
    for a in ['str', 'dex', 'con', 'int', 'wis', 'cha']:
        print(f"    {a.upper()}: {ab[a]['value']} ({ab[a]['mod']:+d})")
    print(f"  Features: {stat['features'][:5]}")
    print(f"  Equipment: {stat['equipment'][:5]}")
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

# ── Test 5: format_stat_block_text ───────────────────────────────
print("\n" + "=" * 50)
print("TEST 5: format_stat_block_text")
print("=" * 50)
try:
    stat = fc.get_actor_stat_block("Compendium.dnd5e.monsters.TjWQOgI3A4UAl7lC")
    text = format_stat_block_text(stat)
    print(text)
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

# ── Test 6: get_world_actors ─────────────────────────────────────
print("\n" + "=" * 50)
print("TEST 6: get_world_actors")
print("=" * 50)
try:
    actors = fc.get_world_actors()
    print(f"  Found {len(actors)} world actors")
    for a in actors:
        print(f"    {a['name']} ({a['uuid']})")
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

# ── Test 7: get_scene_tokens ─────────────────────────────────────
print("\n" + "=" * 50)
print("TEST 7: get_scene_tokens('Scene.rnYku67Y2KTEMhH9')")
print("=" * 50)
try:
    tokens = fc.get_scene_tokens("Scene.rnYku67Y2KTEMhH9")
    print(f"  Found {len(tokens)} tokens")
    for t in tokens:
        print(f"    {t.get('name', '?')} at ({t.get('x')}, {t.get('y')})")
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

# ── Test 8: update_scene_lighting ─────────────────────────────────
print("\n" + "=" * 50)
print("TEST 8: update_scene_lighting (set to 0.5)")
print("=" * 50)
try:
    r = fc.update_scene_lighting("Scene.rnYku67Y2KTEMhH9", darkness=0.5)
    print(f"  Result: {json.dumps(r, indent=2, default=str)[:500]}")
    print("  ✅ PASS")
    # Reset to 0
    fc.update_scene_lighting("Scene.rnYku67Y2KTEMhH9", darkness=0.0)
    print("  (Reset to 0.0)")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

# ── Test 9: get_world_scenes ────────────────────────────────────
print("\n" + "=" * 50)
print("TEST 9: get_world_scenes")
print("=" * 50)
try:
    scenes = fc.get_world_scenes()
    print(f"  Found {len(scenes)} world scenes")
    for s in scenes:
        print(f"    {s['name']} ({s['uuid']})")
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

# ── Test 10: get_playlist_info ───────────────────────────────────
print("\n" + "=" * 50)
print("TEST 10: get_playlist_info")
print("=" * 50)
try:
    playlists = fc.get_playlist_info()
    print(f"  Found {len(playlists)} playlists")
    for p in playlists[:5]:
        print(f"    {p['name']} ({p['track_count']} tracks)")
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

# ── Test 11: Player Character ────────────────────────────────────
print("\n" + "=" * 50)
print("TEST 11: get_actor_stat_block (Player Character)")
print("=" * 50)
try:
    stat = fc.get_actor_stat_block("Actor.0CvIaotWAGFF3stO")
    print(format_stat_block_text(stat))
    print("  ✅ PASS")
except Exception as e:
    print(f"  ❌ FAIL: {e}")

print("\n" + "=" * 50)
print("ALL TESTS COMPLETE")
print("=" * 50)
