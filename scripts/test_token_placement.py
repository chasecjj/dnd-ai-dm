"""Test token placement strategies after relay upgrade."""
import sys, json
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from agents.tools.foundry_tool import FoundryClient
import requests

fc = FoundryClient()
fc.connect()
print("Connected:", fc.is_connected)

base = fc.relay_url
h = fc._headers()
p = {'clientId': fc.client_id}

# Test 1: Create a JournalEntry as a command queue
print("\n--- Creating AI Command Queue JournalEntry ---")
try:
    r = fc.create_entity('JournalEntry', {
        'name': 'AI Command Queue',
    })
    print(f"Result: {json.dumps(r, indent=2, default=str)[:500]}")
    queue_uuid = r.get('uuid', '')
    print(f"Queue UUID: {queue_uuid}")
except Exception as e:
    print(f"Create JournalEntry error: {e}")
    queue_uuid = None

# Test 2: Create a world actor from a compendium one
print("\n--- Creating world actor from compendium ---")
try:
    # First get compendium goblin data
    goblin = fc.get_entity('Compendium.dnd5e.monsters.TjWQOgI3A4UAl7lC')
    goblin_data = goblin.get('data', {})
    
    # Create a new actor with the same data
    create_data = {
        'name': 'Test Goblin Scout',
        'type': 'npc',
        'img': goblin_data.get('img', ''),
        'system': goblin_data.get('system', {}),
    }
    r2 = fc.create_entity('Actor', create_data)
    print(f"Created actor: {json.dumps(r2, indent=2, default=str)[:500]}")
    new_actor_uuid = r2.get('uuid', '')
    new_actor_id = ''
    if isinstance(r2.get('entity'), list) and r2['entity']:
        new_actor_id = r2['entity'][0].get('_id', '')
    print(f"New actor UUID: {new_actor_uuid}, ID: {new_actor_id}")
except Exception as e:
    print(f"Create actor error: {e}")
    new_actor_uuid = None
    new_actor_id = None

# Test 3: Try update_entity on scene to add a token
if new_actor_id:
    print("\n--- Trying to add token via update_entity on scene ---")
    try:
        # Get existing scene data first
        scene_data = fc.get_entity('Scene.rnYku67Y2KTEMhH9').get('data', {})
        existing_tokens = scene_data.get('tokens', [])
        
        # Build a new token entry
        new_token = {
            'name': 'Test Goblin Scout',
            'actorId': new_actor_id,
            'x': 5000,
            'y': 1500,
            'width': 1,
            'height': 1,
            'texture': {'src': 'systems/dnd5e/tokens/humanoid/Goblin.webp'},
            'disposition': -1,
            'hidden': False,
            'actorLink': False,
            'bar1': {'attribute': 'attributes.hp'},
        }
        
        # Try updating scene with new token list
        all_tokens = existing_tokens + [new_token]
        r3 = fc.update_entity('Scene.rnYku67Y2KTEMhH9', {'tokens': all_tokens})
        print(f"Update result: {json.dumps(r3, indent=2, default=str)[:500]}")
    except Exception as e:
        print(f"Token update error: {e}")

# Test 4: Check updated token count
print("\n--- Current scene tokens ---")
tokens = fc.get_scene_tokens('Scene.rnYku67Y2KTEMhH9')
print(f"Token count: {len(tokens)}")
for t in tokens:
    print(f"  {t.get('name', '?')} at ({t.get('x')}, {t.get('y')}) actor={t.get('actorId')}")

# Test 5: Try different /macro path variants
print("\n--- Probing ALL possible macro/execute endpoints ---")
macro_variants = [
    ('POST', '/macro'),
    ('POST', '/execute'),
    ('POST', '/run-macro'),
    ('POST', '/execute-macro'),
    ('POST', '/api/macro'),
    ('POST', '/api/execute'),
    ('POST', '/macro/execute'),
    ('GET', '/macro/list'),
    ('POST', '/command'),
    ('POST', '/script'),
    ('POST', '/eval'),
]
for method, path in macro_variants:
    try:
        r = requests.request(method, f'{base}{path}', headers=h, params=p,
                           json={'command': 'return 42'}, timeout=5)
        status = r.status_code
        is_404 = status == 404 and 'Cannot' in r.text
        if not is_404:
            print(f"  {method} {path} -> {status}: {r.text[:200]}")
        # Don't print 404s to keep output clean
    except requests.Timeout:
        print(f"  {method} {path} -> TIMEOUT (may have executed!)")
    except Exception as e:
        print(f"  {method} {path} -> Error: {e}")

print("\n--- All non-404 endpoints checked ---")
