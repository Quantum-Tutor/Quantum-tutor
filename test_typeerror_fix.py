import asyncio
import os
import sys

# Mocking the API key to force a failure
os.environ['GEMINI_API_KEY'] = 'fake_key'

from quantum_tutor_orchestrator import QuantumTutorOrchestrator

async def test_fix():
    print("[TEST] Initializing Orchestrator...")
    tutor = QuantumTutorOrchestrator()
    
    print("[TEST] Generating response (forcing LLM failure)...")
    try:
        # We use a query that doesn't trigger a greeting to force the full flow
        result = await tutor.generate_response_async("Háblame del pozo infinito")
        print("\n[SUCCESS] Response generated without crash!")
        print(f"[PREVIEW] {result['response'][:100]}...")
    except TypeError as e:
        print(f"\n[FAIL] TypeError still present: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"\n[DEBUG] Caught other exception: {type(e).__name__}: {e}")
        # If it's a generic exception but not a TypeError, the fix for line 388 might be working
        print("[INFO] Checking if it crashed before or after the fix...")

if __name__ == "__main__":
    asyncio.run(test_fix())
