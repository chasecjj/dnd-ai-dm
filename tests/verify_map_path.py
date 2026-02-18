
import sys
import os
from pathlib import Path

# Add project root to sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

# Mock environment variables to avoid errors during import
os.environ['DISCORD_BOT_TOKEN'] = 'mock_token'
os.environ['GEMINI_API_KEY'] = 'mock_key'

try:
    from orchestration.bot import cartographer_agent, vault
    
    expected_path = Path(vault.vault_path) / "Assets" / "Maps"
    actual_path = cartographer_agent.output_dir
    
    print(f"Expected path: {expected_path}")
    print(f"Actual path:   {actual_path}")
    
    if actual_path == expected_path:
        print("✅ SUCCESS: CartographerAgent is configured with the correct vault path.")
    else:
        print("❌ FAILURE: CartographerAgent path does not match expected vault path.")
        sys.exit(1)

except Exception as e:
    print(f"❌ ERROR: {e}")
    sys.exit(1)
