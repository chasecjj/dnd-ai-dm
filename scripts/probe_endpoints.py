"""Probe additional Foundry VTT REST API endpoints for playlist, macro, and token features."""
import os, json, requests
from dotenv import load_dotenv
load_dotenv()
from agents.tools.foundry_tool import FoundryClient

fc = FoundryClient()
fc.connect()

base = fc.relay_url
headers = fc._headers()
params = {"clientId": fc.client_id}

def try_endpoint(method, path, body=None, extra_params=None):
    p = dict(params)
    if extra_params:
        p.update(extra_params)
    try:
        if method == "GET":
            r = requests.get(f"{base}{path}", headers=headers, params=p, timeout=8)
        else:
            r = requests.post(f"{base}{path}", headers=headers, params=p, json=body or {}, timeout=8)
        return r.status_code, r.text[:300]
    except Exception as e:
        return -1, str(e)

# --- Playlist endpoints ---
print("=" * 60)
print("PLAYLIST / AUDIO ENDPOINTS")
print("=" * 60)
playlist_eps = [
    ("GET", "/playlists"),
    ("GET", "/playlist"),
    ("POST", "/playlist/play", {"playlistName": "Michael Ghelfi Studios"}),
    ("POST", "/playlist/stop", {}),
    ("GET", "/audio"),
    ("POST", "/play-playlist", {"name": "Michael Ghelfi Studios"}),
    ("POST", "/play-sound", {"playlistId": "test", "soundId": "test"}),
    ("POST", "/stop-playlist", {}),
    ("POST", "/play-audio", {}),
    ("POST", "/stop-audio", {}),
]
for method, path, *rest in playlist_eps:
    body = rest[0] if rest else None
    code, txt = try_endpoint(method, path, body)
    is404 = "Cannot" in txt and code == 404
    if not is404:
        print(f"  {method} {path} -> {code}: {txt[:150]}")
    else:
        print(f"  {method} {path} -> 404 (not found)")

# --- Macro execution ---
print()
print("=" * 60)
print("MACRO EXECUTION ENDPOINTS")
print("=" * 60)
macro_eps = [
    ("POST", "/macro", {"uuid": "Macro.0EkAP4dWH76ICVl3"}),
    ("POST", "/execute-macro", {"uuid": "Macro.0EkAP4dWH76ICVl3"}),
    ("POST", "/execute", {"uuid": "Macro.0EkAP4dWH76ICVl3"}),
    ("POST", "/run-macro", {"uuid": "Macro.0EkAP4dWH76ICVl3"}),
    ("POST", "/run", {"uuid": "Macro.0EkAP4dWH76ICVl3"}),
    ("POST", "/macro/execute", {"uuid": "Macro.0EkAP4dWH76ICVl3"}),
    ("GET", "/macro", {"uuid": "Macro.0EkAP4dWH76ICVl3"}),
]
for method, path, *rest in macro_eps:
    body = rest[0] if rest else None
    code, txt = try_endpoint(method, path, body)
    is404 = "Cannot" in txt and code == 404
    if not is404:
        print(f"  {method} {path} -> {code}: {txt[:150]}")
    else:
        print(f"  {method} {path} -> 404 (not found)")

# --- Token operations ---
print()
print("=" * 60)
print("TOKEN / SCENE MANIPULATION ENDPOINTS")
print("=" * 60)
token_eps = [
    ("GET", "/tokens"),
    ("GET", "/token"),
    ("POST", "/token", {}),
    ("POST", "/create-token", {}),
    ("POST", "/place-token", {}),
    ("POST", "/add-token", {}),
    ("POST", "/scene/token", {}),
    ("GET", "/scene"),
    ("POST", "/scene", {}),
    ("POST", "/activate-scene", {"uuid": "Scene.rnYku67Y2KTEMhH9"}),
    ("POST", "/view-scene", {"uuid": "Scene.rnYku67Y2KTEMhH9"}),
    ("POST", "/navigate-scene", {"uuid": "Scene.rnYku67Y2KTEMhH9"}),
    ("POST", "/navigate", {"sceneId": "rnYku67Y2KTEMhH9"}),
]
for method, path, *rest in token_eps:
    body = rest[0] if rest else None
    code, txt = try_endpoint(method, path, body)
    is404 = "Cannot" in txt and code == 404
    if not is404:
        print(f"  {method} {path} -> {code}: {txt[:150]}")
    else:
        print(f"  {method} {path} -> 404 (not found)")

# --- Also check the create endpoint to see if we can create tokens on scenes ---
print()
print("=" * 60)
print("ENTITY CREATE WITH TOKEN DATA")
print("=" * 60)
# Can we create a TokenDocument?
code, txt = try_endpoint("POST", "/create", {"entityType": "Token", "data": {"name": "test"}})
print(f"  Create Token entity -> {code}: {txt[:200]}")

# Check if update on a scene can add tokens
print()
print("=== JB2A Actors ===")
r = fc.search("JB2A", filter_type="Actor")
results = r.get("results", [])
for res in results[:10]:
    print(f"  {res['name']} ({res['uuid']})")
print(f"  ... total: {len(results)}")

print()
print("=== JB2A Search (no filter) ===")
r2 = fc.search("Jules Ben Animated")
results2 = r2.get("results", [])
for res in results2[:5]:
    print(f"  [{res.get('documentType')}] {res['name']} ({res['uuid']})")

# Try getting a JB2A actor's details
if results:
    print()
    print("=== First JB2A Actor Details ===")
    try:
        details = fc.get_entity(results[0]["uuid"])
        print(json.dumps(details, indent=2, default=str)[:1000])
    except Exception as e:
        print(f"  Error: {e}")
