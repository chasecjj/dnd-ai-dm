"""
Foundry VTT Reset Script
Clears tokens, ends encounters, and resets lighting via the REST API relay.

Usage: python scripts/reset_foundry.py
Requires: Foundry relay running at localhost:3010
"""
import asyncio
import os
import sys

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

from agents.tools.foundry_tool import FoundryClient


async def main():
    client = FoundryClient()

    print("Connecting to Foundry VTT relay...")
    if not await client.connect():
        print("ERROR: Could not connect to Foundry relay. Is it running?")
        return

    print(f"Connected! Client ID: {client.client_id}\n")

    # --- End active encounters ---
    print("=== Ending Active Encounters ===")
    try:
        result = await client.end_encounter()
        print(f"  End encounter result: {result}")
    except Exception as e:
        print(f"  No active encounter or error: {e}")

    # --- Get all world scenes ---
    print("\n=== Fetching World Scenes ===")
    scenes = await client.get_world_scenes()
    if not scenes:
        print("  No scenes found.")
    else:
        print(f"  Found {len(scenes)} scene(s)")

    # --- Clear tokens from each scene ---
    total_tokens_deleted = 0
    for scene in scenes:
        scene_name = scene.get("name", "Unknown")
        scene_uuid = scene.get("uuid", scene.get("_id", ""))
        print(f"\n--- Scene: {scene_name} ({scene_uuid}) ---")

        try:
            tokens = await client.get_scene_tokens(scene_uuid)
            if not tokens:
                print("  No tokens in this scene.")
            else:
                print(f"  Found {len(tokens)} token(s), deleting...")
                for token in tokens:
                    token_name = token.get("name", "Unknown")
                    token_uuid = token.get("uuid", token.get("_id", ""))
                    try:
                        await client.delete_entity(token_uuid)
                        print(f"    Deleted: {token_name}")
                        total_tokens_deleted += 1
                    except Exception as e:
                        print(f"    Failed to delete {token_name}: {e}")
        except Exception as e:
            print(f"  Error getting tokens: {e}")

        # Reset lighting to daylight
        try:
            await client.update_scene_lighting(scene_uuid, darkness=0.0)
            print(f"  Lighting reset to daylight (darkness=0.0)")
        except Exception as e:
            print(f"  Error resetting lighting: {e}")

    # --- Summary ---
    print(f"\n{'='*40}")
    print(f"RESET COMPLETE")
    print(f"  Scenes processed: {len(scenes)}")
    print(f"  Tokens deleted:   {total_tokens_deleted}")
    print(f"  Encounters ended: 1 (attempted)")
    print(f"  Lighting reset:   {len(scenes)} scene(s)")
    print(f"{'='*40}")

    await client.close()


if __name__ == "__main__":
    asyncio.run(main())
