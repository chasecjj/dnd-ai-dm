"""Quick scan of world entities"""
import sys, json
sys.path.insert(0, '.')
from dotenv import load_dotenv
load_dotenv()
from agents.tools.foundry_tool import FoundryClient

fc = FoundryClient()
fc.connect()

# World actors
r = fc.get_structure(types=['Actor'], recursive=True, include_data=False)
actors = r.get('data', {}).get('entities', {}).get('actors', [])
print(f"World actors ({len(actors)}):")
for a in actors:
    print(f"  {a['name']}  uuid={a['uuid']}")

# World items
r2 = fc.get_structure(types=['Item'], recursive=True, include_data=False)
items = r2.get('data', {}).get('entities', {}).get('items', [])
print(f"\nWorld items ({len(items)}):")
for i in items:
    print(f"  {i['name']}  uuid={i['uuid']}")

# Scene with full token list
scene = fc.get_entity('Scene.rnYku67Y2KTEMhH9')
tokens = scene.get('data', {}).get('tokens', [])
print(f"\nScene tokens ({len(tokens)}):")
for t in tokens:
    print(f"  {t.get('name', '?')} at ({t.get('x')}, {t.get('y')}) actor={t.get('actorId')}")
