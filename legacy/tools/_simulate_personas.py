"""
Simulación archivada de perfiles/personas para revisión manual del tutor.
Se conserva como referencia histórica.
"""

import asyncio
import time
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from quantum_tutor_runtime import APP_NAME, RUNTIME_VERSION

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    print(f"# Evaluación de Personas - {APP_NAME} {RUNTIME_VERSION}", flush=True)
    orchestrator = QuantumTutorOrchestrator(base_dir=str(ROOT_DIR))
    
    test_cases = [
        {
            "name": "Profesor (Pedagógico)",
            "prompt": "Como explicarias la normalizacion de la funcion de onda en un pozo finito de manera pedagogica?",
            "expected_wolfram": False
        },
        {
            "name": "Investigador (Simbólico / Formal)",
            "prompt": "Halla la normalizacion de la funcion de onda A*exp(-|x|/b). Usa rigor matematico.",
            "expected_wolfram": True
        },
        {
            "name": "Público General (Analogía)",
            "prompt": "Que significa que dos particulas esten entrelazadas? Usa una analogia de la vida diaria.",
            "expected_wolfram": False
        }
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n## Test {i}: {test['name']}", flush=True)
        print(f"**Prompt:** {test['prompt']}", flush=True)
        
        try:
            start = time.perf_counter()
            resp_meta, stream = await orchestrator.generate_response_stream_async(test['prompt'], [])
            
            print(f"\n**Metadatos extraídos:**", flush=True)
            print(f"- Tópico RAG: {resp_meta.get('topic')}", flush=True)
            print(f"- RAG Context Retrieved: {resp_meta.get('context_retrieved')}", flush=True)
            print(f"- Wolfram Used: {resp_meta.get('wolfram_used')} (Expected: {test['expected_wolfram']})", flush=True)
            
            print("\n**Streaming Response:**", flush=True)
            print("---START---", flush=True)
            async for chunk in stream:
                if chunk == "⚡_ROTATION_SIGNAL_⚡":
                    print("[API KEY ROTATION]", flush=True)
                    continue
                print(chunk, end="", flush=True)
            print("\n---END---", flush=True)
            
            latency = time.perf_counter() - start
            print(f"\n*Latencia total: {latency:.2f}s*", flush=True)
            
        except Exception as e:
            print(f"\n=> Error en Test {i}: {e}", flush=True)
        
        print("\n" + "="*50 + "\n", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
