import sys
import os
import asyncio
from dotenv import load_dotenv
from google import genai

# Add project root to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

load_dotenv()
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY')

def main():
    if not GEMINI_API_KEY:
        print("Error: GEMINI_API_KEY not set.")
        return

    client = genai.Client(api_key=GEMINI_API_KEY)
    try:
        # Pager object; iterate to get models
        print("Listing models...")
        for model in client.models.list():
            print(f"- {model.name}")
            
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    main()
