"""Verify that the modified agent and bot files can be imported without syntax errors."""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

print("--- Verifying FoundryArchitectAgent ---")
try:
    from agents.foundry_architect import FoundryArchitectAgent
    print("✅ Successfully imported FoundryArchitectAgent")
except ImportError as e:
    print(f"❌ Failed to import FoundryArchitectAgent: {e}")
except SyntaxError as e:
    print(f"❌ Syntax error in FoundryArchitectAgent: {e}")
except Exception as e:
    print(f"❌ Error importing FoundryArchitectAgent: {e}")

print("\n--- Verifying Bot ---")
try:
    from orchestration import bot
    print("✅ Successfully imported bot module")
except ImportError as e:
    print(f"❌ Failed to import bot: {e}")
except SyntaxError as e:
    print(f"❌ Syntax error in bot: {e}")
except Exception as e:
    # Bot import might fail due to missing env vars or discord connection, 
    # but we just want to check for SyntaxErrors in the new code
    if "SyntaxError" in str(e):
        print(f"❌ Syntax error in bot: {e}")
    else:
        print(f"⚠️ Import failed (likely env/connection), but syntax seems okay: {e}")

print("\nVerification complete.")
