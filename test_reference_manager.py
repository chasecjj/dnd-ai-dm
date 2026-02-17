"""Quick verification of the ReferenceManager."""

from tools.reference_manager import ReferenceManager

print("=" * 60)
print("REFERENCE MANAGER — VERIFICATION")
print("=" * 60)

rm = ReferenceManager()
stats = rm.get_stats()
print(f"\n[1] Stats: {stats}")

# Test 1: Rules search - spell
print(f"\n{'=' * 60}")
print("[2] Rules search: 'fireball'")
print("=" * 60)
result = rm.search_rules("fireball", max_results=1, max_tokens=300)
print(result[:500] if result else "NO RESULTS")

# Test 2: Rules search - monster
print(f"\n{'=' * 60}")
print("[3] Rules search: 'troll regeneration'")
print("=" * 60)
result = rm.search_rules("troll regeneration", max_results=1, max_tokens=300)
print(result[:500] if result else "NO RESULTS")

# Test 3: Lore search - location
print(f"\n{'=' * 60}")
print("[4] Lore search: 'yawning portal'")
print("=" * 60)
result = rm.search_lore("yawning portal", max_results=1, max_tokens=300)
print(result[:500] if result else "NO RESULTS")

# Test 4: Lore search - faction
print(f"\n{'=' * 60}")
print("[5] Lore search: 'zhentarim waterdeep'")
print("=" * 60)
result = rm.search_lore("zhentarim waterdeep", max_results=1, max_tokens=300)
print(result[:500] if result else "NO RESULTS")

# Test 5: Asset search
print(f"\n{'=' * 60}")
print("[6] Asset search: 'troll'")
print("=" * 60)
assets = rm.find_asset("troll", max_results=3)
for asset in assets:
    print(f"  {asset['book_slug']} p.{asset['page']} — {asset['size_bytes']} bytes ({asset['width']}x{asset['height']})")
    print(f"  Context: {asset['context'][:80]}")

# Test 6: Rules search - grapple
print(f"\n{'=' * 60}")
print("[7] Rules search: 'grapple'")
print("=" * 60)
result = rm.search_rules("grapple", max_results=1, max_tokens=300)
print(result[:500] if result else "NO RESULTS")

# Test 7: ContextAssembler integration
print(f"\n{'=' * 60}")
print("[8] ContextAssembler with references")
print("=" * 60)
from tools.vault_manager import VaultManager
from tools.context_assembler import ContextAssembler

vault = VaultManager("campaign_vault")
ca = ContextAssembler(vault, reference_manager=rm)
ca.set_query("I cast fireball at the trolls")

ctx = ca.build_rules_lawyer_context()
# Check for reference section
if "Rules Reference" in ctx:
    ref_start = ctx.index("Rules Reference")
    print(f"Rules context contains reference section at char {ref_start}")
    print(f"Total context length: {len(ctx)} chars")
else:
    print("WARNING: No reference section in rules context!")

ctx = ca.build_storyteller_context("The Yawning Portal")
if "Lore Reference" in ctx:
    ref_start = ctx.index("Lore Reference")
    print(f"Storyteller context contains lore reference section at char {ref_start}")
    print(f"Total context length: {len(ctx)} chars")
else:
    print("WARNING: No lore reference section in storyteller context!")

print("\n" + "=" * 60)
print("ALL CHECKS COMPLETE ✓")
print("=" * 60)
