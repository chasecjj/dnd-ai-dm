"""Test adding a token to a scene via update_entity."""
import sys, json
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from agents.tools.foundry_tool import FoundryClient

fc = FoundryClient()
fc.connect()

SCENE_UUID = 'Scene.rnYku67Y2KTEMhH9'
ACTOR_UUID = 'Actor.R1yM4W5kXNXDSfaQ'  # Test Goblin Scout we just created

# Get the actor ID (short form needed for token actorId)
actor = fc.get_entity(ACTOR_UUID)
actor_id = actor['data']['_id']
actor_name = actor['data']['name']
actor_img = actor['data'].get('img', '')
print(f"Actor: {actor_name} (ID: {actor_id})")

# Get the actor's prototypeToken data for proper token rendering
proto = actor['data'].get('prototypeToken', {})
print(f"Prototype token texture: {proto.get('texture', {}).get('src', 'N/A')}")

# Get existing scene tokens
scene = fc.get_entity(SCENE_UUID)
existing_tokens = scene['data'].get('tokens', [])
print(f"\nExisting tokens: {len(existing_tokens)}")

# Build token data
new_token = {
    'name': actor_name,
    'actorId': actor_id,
    'x': 3500,
    'y': 1800,
    'width': proto.get('width', 1),
    'height': proto.get('height', 1),
    'texture': proto.get('texture', {'src': actor_img}),
    'disposition': proto.get('disposition', -1),
    'hidden': False,
    'actorLink': False,
    'bar1': {'attribute': 'attributes.hp'},
    'displayBars': 40,  # Show bars on hover
    'displayName': 30,  # Show name on hover
}

# Attempt 1: Add to embedded token array via update
print("\n--- Attempt: update_entity with tokens array ---")
all_tokens = existing_tokens + [new_token]
try:
    result = fc.update_entity(SCENE_UUID, {'tokens': all_tokens})
    print(f"Result type: {result.get('type', '?')}")
    if result.get('error'):
        print(f"Error: {result.get('error')}")
    elif result.get('entity'):
        entity_data = result['entity']
        if isinstance(entity_data, list):
            ntokens = len(entity_data[0].get('tokens', []))
        elif isinstance(entity_data, dict):
            ntokens = len(entity_data.get('tokens', []))
        else:
            ntokens = '?'
        print(f"Scene now has {ntokens} tokens")
    print(f"Full result: {json.dumps(result, indent=2, default=str)[:800]}")
except Exception as e:
    print(f"Error: {e}")

# Check final state
print("\n--- Final token check ---")
tokens_after = fc.get_scene_tokens(SCENE_UUID)
print(f"Token count after: {len(tokens_after)}")
for t in tokens_after:
    print(f"  {t.get('name', '?')} at ({t.get('x')}, {t.get('y')})")
