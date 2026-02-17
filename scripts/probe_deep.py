"""Test relay endpoints: /macro, /update (PUT), /session, and token creation strategies."""
import sys, json
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from agents.tools.foundry_tool import FoundryClient
import requests

fc = FoundryClient()
fc.connect()
base = fc.relay_url
h = fc._headers()
p = {'clientId': fc.client_id}

# --- Test 1: /macro endpoint (execute arbitrary JS in Foundry) ---
print("=" * 60)
print("TEST 1: POST /macro — Execute JavaScript in Foundry")
print("=" * 60)
try:
    r = requests.post(f'{base}/macro', headers=h, params=p,
                      json={'command': 'return canvas.scene?.name || "no scene"'},
                      timeout=10)
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.text[:500]}")
except requests.Timeout:
    print("  TIMEOUT (command may have executed)")
except Exception as e:
    print(f"  Error: {e}")

# --- Test 2: /macro to create a token programmatically ---
print()
print("=" * 60)
print("TEST 2: /macro — Create token via Foundry macro")
print("=" * 60)
macro_js = """
const scene = game.scenes.get("rnYku67Y2KTEMhH9");
if (!scene) return "Scene not found";
const actor = game.actors.get("v3OCG0dO8d5KQM5g");
if (!actor) return "Actor not found";
const tokenData = await actor.getTokenDocument({x: 4500, y: 1500});
const created = await scene.createEmbeddedDocuments("Token", [tokenData]);
return `Created token: ${created[0].name} at (${created[0].x}, ${created[0].y})`;
"""
try:
    r = requests.post(f'{base}/macro', headers=h, params=p,
                      json={'command': macro_js},
                      timeout=15)
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.text[:500]}")
except requests.Timeout:
    print("  TIMEOUT")
except Exception as e:
    print(f"  Error: {e}")

# --- Test 3: /session endpoint ---
print()
print("=" * 60)
print("TEST 3: GET /session")
print("=" * 60)
try:
    r = requests.get(f'{base}/session', headers=h, params=p, timeout=10)
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.text[:500]}")
except Exception as e:
    print(f"  Error: {e}")

# --- Test 4: Verify update method works ---
print()
print("=" * 60)
print("TEST 4: update_entity (existing method) — verify it works")
print("=" * 60)
try:
    r = fc.update_entity('Scene.rnYku67Y2KTEMhH9', {'environment': {'darknessLevel': 0.1}})
    print(f"  Result type: {r.get('type', '?')}")
    fc.update_entity('Scene.rnYku67Y2KTEMhH9', {'environment': {'darknessLevel': 0.0}})
    print("  ✅ update_entity works fine (reset darkness)")
except Exception as e:
    print(f"  ❌ Error: {e}")

# --- Test 5: Check what HTTP method /update uses ---
print()
print("=" * 60)
print("TEST 5: What HTTP methods does /update support?")
print("=" * 60)
for method in ['GET', 'POST', 'PUT', 'PATCH']:
    try:
        r = requests.request(method, f'{base}/update', headers=h, params=p,
                           json={'uuid': 'Scene.rnYku67Y2KTEMhH9', 'data': {}},
                           timeout=5)
        print(f"  {method}: {r.status_code} ({r.text[:100]})")
    except Exception as e:
        print(f"  {method}: Error ({e})")

# --- Test 6: Check token count after potential macro creation ---
print()
print("=" * 60)
print("TEST 6: Scene tokens (check if macro created one)")
print("=" * 60)
tokens = fc.get_scene_tokens('Scene.rnYku67Y2KTEMhH9')
print(f"  Token count: {len(tokens)}")
for t in tokens:
    print(f"    {t.get('name', '?')} at ({t.get('x')}, {t.get('y')})")
