"""
Utilidad archivada para probar streaming básico de Gemini.
Conservada como herramienta de depuración histórica.
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

from quantum_tutor_runtime import DEFAULT_TEXT_MODEL

load_dotenv()

async def test_gemini():
    api_keys = os.getenv("GEMINI_API_KEYS", "").split(",")
    if not api_keys or not api_keys[0]:
        print("No API keys found")
        return
    
    client = Client(api_key=api_keys[0])
    try:
        print(f"Testing with key starting with: {api_keys[0][:5]}...")
        stream = await client.aio.models.generate_content_stream(
            model=DEFAULT_TEXT_MODEL,
            contents="Hola, responde brevemente."
        )
        async for chunk in stream:
            print(f"Chunk: {getattr(chunk, 'text', '')}")
        print("Success!")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_gemini())
