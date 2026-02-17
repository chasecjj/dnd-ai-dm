"""
Foundry VTT Connection Test

Run this to verify your Foundry REST API relay connection is working.
Usage: py tests/test_foundry_connection.py
"""

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
load_dotenv()

from agents.tools.foundry_tool import FoundryClient
import json


def pretty(data):
    """Pretty-print JSON data."""
    if isinstance(data, (dict, list)):
        return json.dumps(data, indent=2, default=str)[:2000]
    return str(data)[:2000]


def main():
    print("=" * 60)
    print("  Foundry VTT Connection Test")
    print("=" * 60)

    client = FoundryClient()

    # Check config
    print(f"\n📡 Relay URL: {client.relay_url}")
    print(f"🔑 API Key:  {'***' + client.api_key[-4:] if client.api_key else 'NOT SET'}")
    print(f"🎯 Client ID: {client.client_id or 'Will auto-discover'}")

    if not client.api_key:
        print("\n❌ FOUNDRY_API_KEY not set in .env — cannot proceed.")
        return

    # Test 1: List connected clients
    print(f"\n{'─' * 40}")
    print("TEST 1: List Connected Clients")
    print(f"{'─' * 40}")
    try:
        clients = client.get_clients()
        print(f"✅ Response:\n{pretty(clients)}")
    except Exception as e:
        print(f"❌ Failed: {e}")
        print("   Make sure Foundry VTT is running with the REST API module enabled.")
        return

    # Test 2: Connect (auto-discover clientId)
    print(f"\n{'─' * 40}")
    print("TEST 2: Connect & Validate")
    print(f"{'─' * 40}")
    if client.connect():
        print(f"✅ Connected! Client ID: {client.client_id}")
    else:
        print("❌ Connection failed.")
        return

    # Test 3: Get world structure
    print(f"\n{'─' * 40}")
    print("TEST 3: World Structure (Actors & Scenes)")
    print(f"{'─' * 40}")
    try:
        structure = client.get_structure(
            types=['Actor', 'Scene'],
            include_data=False,
            recursive=True,
        )
        print(f"✅ Response:\n{pretty(structure)}")
    except Exception as e:
        print(f"❌ Failed: {e}")

    # Test 4: Search for something
    print(f"\n{'─' * 40}")
    print("TEST 4: Search for 'player'")
    print(f"{'─' * 40}")
    try:
        results = client.search("player")
        print(f"✅ Response:\n{pretty(results)}")
    except Exception as e:
        print(f"⚠️  Search failed: {e}")
        print("   (This requires the Quick Insert module in Foundry)")

    # Test 5: Get encounters
    print(f"\n{'─' * 40}")
    print("TEST 5: Active Encounters")
    print(f"{'─' * 40}")
    try:
        encounters = client.get_encounters()
        print(f"✅ Response:\n{pretty(encounters)}")
    except Exception as e:
        print(f"⚠️  Failed: {e}")

    print(f"\n{'=' * 60}")
    print("  Connection test complete!")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
