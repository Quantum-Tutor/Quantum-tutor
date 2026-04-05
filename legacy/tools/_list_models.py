"""
Utilidad archivada para listar modelos Gemini desde una key local.
Conservada solo como referencia de depuración temprana.
"""

import os
import asyncio
import sys
from pathlib import Path
from google.genai import Client
from dotenv import load_dotenv

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

load_dotenv()

async def list_models():
    api_keys = os.getenv("GEMINI_API_KEYS", "").split(",")
    if not api_keys or not api_keys[0]:
        print("No API keys found")
        return
    
    client = Client(api_key=api_keys[0])
    try:
        print(f"Listing models for key starting with: {api_keys[0][:5]}...")
        models = await client.aio.models.list()
        for m in models:
            print(f"- {m.name} ({m.supported_actions})")
        print("Done!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(list_models())
