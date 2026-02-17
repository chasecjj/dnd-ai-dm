import asyncio
import os
import json
import logging
from agents.tools.foundry_tool import FoundryClient

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TestTokenCreate")

async def test_create_token():
    client = FoundryClient()
    if not client.connect():
        logger.error("Failed to connect to Foundry Relay.")
        return

    # 1. Get a Scene
    scenes = client.get_world_scenes()
    if not scenes:
        logger.error("No scenes found.")
        return
    
    # Pick the first active scene or just the first scene
    active_scenes = [s for s in scenes if s.get('active')]
    target_scene = active_scenes[0] if active_scenes else scenes[0]
    scene_uuid = target_scene['uuid']
    logger.info(f"Target Scene: {target_scene.get('name')} ({scene_uuid})")

    # 2. Get an Actor
    actors = client.get_world_actors()
    if not actors:
        logger.error("No actors found.")
        return
    target_actor = actors[0]
    actor_uuid = target_actor['uuid']
    actor_id = target_actor.get('_id')
    logger.info(f"Target Actor: {target_actor.get('name')} ({actor_uuid})")

    # 3. Attempt to create a Token via create_entity
    # We will try passing parentUuid in the data payload, or check if create_entity needs modification
    
    token_data = {
        "name": "Test Token (Created)",
        "actorId": actor_id,
        "x": 1000,
        "y": 1000,
        "img": target_actor.get("img", "icons/svg/mystery-man.svg"),
        # Try passing parent properties in data if supported by relay
        "parent": scene_uuid,
        "parentUuid": scene_uuid,
        "sceneId": target_scene.get('_id') 
    }

    logger.info("Attempting create_entity('Token', ...)")
    try:
        # Note: create_entity is synchronous in the tool but uses requests
        # The tool creates a 'Token' entity.
        # If the relay supports creating embedded documents via /create, it might need 'parentUuid' at the top level?
        # But create_entity wraps it in 'data'.
        
        # Let's try raw POST to see if we can control the body structure more directly if needed
        # But first, try the existing tool method.
        
        # We need to manually construct the body to include parentUuid ifcreate_entity doesn't support it.
        # So we will use client._post directly to test different payloads.
        
        # Test 1: Standard create_entity (might fail if relay expects top-level parent)
        # client.create_entity("Token", token_data) -> sends { entityType: "Token", data: token_data }
        
        response = client.create_entity("Token", token_data)
        logger.info(f"Response: {response}")
        
    except Exception as e:
        logger.error(f"Standard create_entity failed: {e}")

    # Test 2: Try specific payload with parentUuid at top level
    try:
        logger.info("Attempting custom POST with parentUuid...")
        body = {
            "entityType": "Token",
            "data": {
                "name": "Test Token (Custom)",
                "actorId": actor_id,
                "x": 1200,
                "y": 1200,
                "img": target_actor.get("img"),
            },
            "parentUuid": scene_uuid, # Hypothetical field
            "parentId": target_scene.get('_id') # Hypothetical field
        }
        # We use _post from client
        response = client._post('/create', body=body)
        logger.info(f"Custom Response: {response}")

    except Exception as e:
        logger.error(f"Custom POST failed: {e}")

if __name__ == "__main__":
    # The client uses synchronous requests, so we don't strictly need asyncio unless we were using the async agent code
    # But for consistency with the agent execution which calls async methods (agent wraps them?), 
    # actually FoundryClient is sync.
    # We'll just run it.
    loop = asyncio.new_event_loop()
    loop.run_until_complete(test_create_token())
