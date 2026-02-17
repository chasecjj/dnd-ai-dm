"""
Probe script to discover what's available in the connected Foundry VTT world.
"""
import os, json, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from dotenv import load_dotenv
load_dotenv()

from agents.tools.foundry_tool import FoundryClient

fc = FoundryClient()
if not fc.connect():
    print("FAILED to connect to Foundry VTT relay!")
    sys.exit(1)

print(f"Connected to relay at {fc.relay_url} (client: {fc.client_id})")
print("=" * 70)

# --- Macros ---
print("\n=== MACROS ===")
r = fc.get_structure(types=['Macro'], recursive=True, include_data=False)
macros = r.get('data', {}).get('entities', {}).get('macros', [])
print(f"Found {len(macros)} macros:")
for m in macros:
    print(f"  - {m['name']} (uuid: {m['uuid']})")

# --- Playlists ---
print("\n=== PLAYLISTS ===")
r = fc.get_structure(types=['Playlist'], recursive=True, include_data=False)
packs = r.get('data', {}).get('compendiumPacks', {})
for name, pack in packs.items():
    count = len(pack.get('entities', []))
    print(f"  - {name}: {count} tracks (uuid: {pack.get('uuid', 'N/A')})")

# --- Journals ---
print("\n=== JOURNAL ENTRIES ===")
r = fc.get_structure(types=['JournalEntry'], recursive=True, include_data=False)
journals = r.get('data', {}).get('entities', {}).get('journalentrys', [])
jpacks = r.get('data', {}).get('compendiumPacks', {})
print(f"World journals: {len(journals)}")
for j in journals:
    print(f"  - {j['name']} (uuid: {j['uuid']})")
print(f"Compendium packs:")
for name, pack in jpacks.items():
    count = len(pack.get('entities', []))
    print(f"  - {name}: {count} entries")

# --- Items ---    
print("\n=== ITEM COMPENDIUMS ===")
r = fc.get_structure(types=['Item'], recursive=True, include_data=False)
ipacks = r.get('data', {}).get('compendiumPacks', {})
for name, pack in ipacks.items():
    count = len(pack.get('entities', []))
    print(f"  - {name}: {count} items (type: {pack.get('type', 'N/A')})")

# --- Roll Tables ---
print("\n=== ROLL TABLES ===")
r = fc.get_structure(types=['RollTable'], recursive=True, include_data=False)
tpacks = r.get('data', {}).get('compendiumPacks', {})
for name, pack in tpacks.items():
    count = len(pack.get('entities', []))
    print(f"  - {name}: {count} tables")

# --- Actor Compendiums ---
print("\n=== ACTOR COMPENDIUMS ===")
r = fc.get_structure(types=['Actor'], recursive=True, include_data=False)
apacks = r.get('data', {}).get('compendiumPacks', {})
for name, pack in apacks.items():
    count = len(pack.get('entities', []))
    print(f"  - {name}: {count} actors (uuid: {pack.get('uuid', 'N/A')})")

# --- Scene Compendiums ---
print("\n=== SCENE COMPENDIUMS ===")
r = fc.get_structure(types=['Scene'], recursive=True, include_data=False)
scenes_world = r.get('data', {}).get('entities', {}).get('scenes', [])
spacks = r.get('data', {}).get('compendiumPacks', {})
print(f"World scenes: {len(scenes_world)}")
for s in scenes_world:
    print(f"  - {s['name']} (uuid: {s['uuid']})")
print(f"Scene Compendium packs:")
for name, pack in spacks.items():
    count = len(pack.get('entities', []))
    print(f"  - {name}: {count} scenes")

# --- Encounters ---
print("\n=== ENCOUNTERS ===")
r = fc.get_encounters()
encounters = r.get('encounters', [])
print(f"Active encounters: {len(encounters)}")
for e in encounters:
    print(f"  - ID: {e.get('id')}, Round: {e.get('round')}, Combatants: {len(e.get('combatants', []))}")

# --- Test Roll ---
print("\n=== DICE ROLL TEST ===")
import requests
r = requests.post(
    f"{fc.relay_url}/roll",
    headers=fc._headers(),
    params={'clientId': fc.client_id},
    json={'formula': '4d6kh3'},
    timeout=10
)
data = r.json()
roll = data.get('data', {}).get('roll', {})
print(f"4d6kh3 (stat roll): {roll.get('total')} (dice: {roll.get('dice', [])})")

# --- Test Search ---
print("\n=== SEARCH TESTS ===")
for query in ['Goblin', 'Owlbear', 'Inn', 'Tavern', 'Forest']:
    r = fc.search(query)
    results = r.get('results', [])
    types_found = {}
    for res in results:
        dt = res.get('documentType', 'Unknown')
        types_found[dt] = types_found.get(dt, 0) + 1
    summary = ', '.join(f"{c}x {t}" for t, c in types_found.items())
    print(f"  '{query}': {len(results)} results ({summary})")

print("\n" + "=" * 70)
print("PROBE COMPLETE!")
