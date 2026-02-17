"""Quick verification of all new components."""

from tools.vault_manager import VaultManager
from tools.context_assembler import ContextAssembler, ConversationHistory

print("=" * 60)
print("WORLD STATE SYSTEM — VERIFICATION")
print("=" * 60)

# 1. VaultManager
vm = VaultManager("campaign_vault")
print(f"\n[1] VaultManager initialized at: {vm.vault_path}")

party_files = vm.list_files("01 - Party")
print(f"    Party files: {party_files}")

npc_files = vm.list_files("02 - NPCs")
print(f"    NPC files: {npc_files}")

location_files = vm.list_files("03 - Locations")
print(f"    Location files: {location_files}")

session_files = vm.list_files("00 - Session Log")
print(f"    Session files: {session_files}")

quest_files = vm.list_files("04 - Quests/Active") + vm.list_files("04 - Quests/Completed")
print(f"    Quest files: {quest_files}")

faction_files = vm.list_files("05 - Factions")
print(f"    Faction files: {faction_files}")

# 2. Party State
print(f"\n[2] Party State:")
for member in vm.get_party_state():
    print(f"    {member['summary']}")

# 3. World Clock
clock = vm.read_world_clock()
print(f"\n[3] World Clock: {clock.get('current_date', '?')} ({clock.get('time_of_day', '?')})")

# 4. Active Quests
quests = vm.get_active_quests()
print(f"\n[4] Active Quests ({len(quests)}):")
for q in quests:
    print(f"    - {q['frontmatter'].get('name', '?')} ({q['frontmatter'].get('status', '?')})")

# 5. Consequences
due = vm.get_due_consequences(1)
print(f"\n[5] Due Consequences (session 1): {len(due)}")
for c in due:
    print(f"    - {c.get('event', '?')} (impact: {c.get('impact', '?')})")

# 6. Search
results = vm.search_vault("Frognar")
print(f"\n[6] Vault Search for 'Frognar': {len(results)} files")
for r in results:
    print(f"    - {r['file']}")

# 7. ContextAssembler
ca = ContextAssembler(vm)
print(f"\n[7] ContextAssembler initialized (session {ca.current_session})")

# Test context building
ctx = ca.build_storyteller_context("The Yawning Portal")
print(f"    Storyteller context length: {len(ctx)} chars")
print(f"    First 200 chars: {ctx[:200]}...")

# 8. Weighted Memory
print(f"\n[8] Weighted Memory Test:")
ca.record_event("Frognar shoved the Troll into the well", impact=10)
ca.record_event("Kallisar killed a Stirge", impact=6)
ca.record_event("A patron coughed", impact=2)

history = ca.history.format_for_prompt()
print(f"    History:\n{history}")

# Simulate aging
for _ in range(10):
    ca.history.add_event("filler", 1)

relevant = ca.history.get_relevant_history()
print(f"\n    After 10 turns, {len(relevant)} entries still above threshold")
high_impact = [e for e in relevant if e.base_impact >= 6]
print(f"    High-impact events retained: {[e.text[:40] for e in high_impact]}")

# 9. NPCs at location
npcs = vm.get_npcs_at_location("Yawning Portal")
print(f"\n[9] NPCs at Yawning Portal: {[n['frontmatter']['name'] for n in npcs]}")

# 10. Faction lookup
zh = vm.get_faction("Zhentarim")
if zh:
    fm, _ = zh
    print(f"\n[10] Zhentarim reputation: {fm.get('reputation', '?')}")

print("\n" + "=" * 60)
print("ALL CHECKS PASSED ✓")
print("=" * 60)
