import asyncio
import random
import uuid
import time
import os

from quantum_request_context import QuantumRequestContext
from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from session_manager import SessionStore, create_session_state

# =========================
# CONFIG
# =========================

N_USERS = 5  # Reducido para no quemar toda la cuota de la API de golpe en el primer test
REQUESTS_PER_USER = 2

TEST_QUERIES = [
    "explica el principio de incertidumbre",
    "∫ e^{-x^2} dx",
    "normaliza la función de onda",
    "explica el oscilador armónico",
    "calcula d/dx (x^2 e^x)"
]

# =========================
# INIT
# =========================
config = {
    "api_keys": [k.strip() for k in os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", "")).split(",") if k.strip()],
    "model": "gemini-2.0-flash"
}

orchestrator = QuantumTutorOrchestrator(config_path="quantum_tutor_config.json", base_dir=".")
session_store = SessionStore(ttl_seconds=3600)

async def simulate_user(user_id: int):
    session_id = str(uuid.uuid4())

    for i in range(REQUESTS_PER_USER):
        query = random.choice(TEST_QUERIES)

        session_data = await session_store.get_or_create(
            session_id,
            lambda: create_session_state(".")
        )

        ctx = QuantumRequestContext(
            user_id=f"user_{user_id}",
            session_id=session_id,
            user_input=query,
            conversation_history=[],

            relational=session_data["relational"],
            analytics=session_data["analytics"],
            semantic_cache=session_data["cache"]
        )

        start = time.perf_counter()

        try:
            stream = orchestrator.handle_request(ctx)
            full_response = ""

            async for chunk in stream:
                if random.random() < 0.05:  # 5% chance of canceling
                    ctx.mark_cancelled()
                    break
                full_response += chunk

            latency = time.perf_counter() - start

            if ctx.cancelled:
                 print(f"[USER {user_id}] CANCELED | {latency:.2f}s")
            else:
                 print(f"[USER {user_id}] OK | {latency:.2f}s | len={len(full_response)}")

            if "Resultado computacional" in full_response:
                if full_response.count("Resultado computacional") > 1:
                    print(f"  --> [USER {user_id}] ⚠️ DUPLICATE WOLFRAM IN STREAM")
                else:
                    print(f"  --> [USER {user_id}] ✔ Late Fusion OK")

        except Exception as e:
            print(f"[USER {user_id}] ERROR: {e}")

        await asyncio.sleep(random.uniform(0.5, 2.0))

async def main():
    print(f"Iniciando Stress Test: {N_USERS} users, {REQUESTS_PER_USER} req/user")
    tasks = [
        asyncio.create_task(simulate_user(i))
        for i in range(N_USERS)
    ]
    await asyncio.gather(*tasks)
    print("Test completado.")

if __name__ == "__main__":
    asyncio.run(main())
