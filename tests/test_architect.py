import sys
import os
import asyncio
# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from dotenv import load_dotenv
from google import genai
from agents.foundry_architect import FoundryArchitectAgent

# Load environment
load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

async def main():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not set.")
        return

    client = genai.Client(api_key=GEMINI_API_KEY)
    architect = FoundryArchitectAgent(client)

    print("--- Testing Foundry Architect ---")
    prompt = "Create an encounter with 2 Orcs guarding a chest."
    print(f"Prompt: {prompt}")
    
    # Check if Foundry URL is reachable or just mock it?
    # For this test, we might see 'API Error' if Foundry isn't running, but we'll see the Plan generation.
    
    response = await architect.process_request(prompt)
    print("\nResponse:")
    print(response)

if __name__ == "__main__":
    asyncio.run(main())
