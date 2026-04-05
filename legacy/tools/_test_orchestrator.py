"""
Prueba archivada del orquestador durante etapas tempranas del proyecto.
Se conserva como referencia de depuración histórica.
"""

import asyncio
import time
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from quantum_tutor_orchestrator import QuantumTutorOrchestrator

sys.stdout.reconfigure(encoding='utf-8')

async def main():
    print("Iniciando Orchestrator v2 Test...", flush=True)
    orchestrator = QuantumTutorOrchestrator(base_dir=ROOT_DIR)
    
    prompt = "Como explicarias la normalizacion de la funcion de onda en un pozo finito de manera pedagogica?"
    print(f"\n=> Prompt: {prompt}", flush=True)
    print("=> Esperando stream...", flush=True)
    
    try:
        resp_meta, stream = await orchestrator.generate_response_stream_async(prompt, [])
        print(f"Metadatos iniciales: {resp_meta}", flush=True)
        
        start = time.perf_counter()
        async for chunk in stream:
            if chunk == "⚡_ROTATION_SIGNAL_⚡":
                print("\n[ROTANDO CLAVE]", flush=True)
                continue
            print(chunk, end="", flush=True)
        
        print(f"\n\n=> Stream completado en {time.perf_counter() - start:.2f}s", flush=True)
    except Exception as e:
        print(f"\n=> Error fatal en la prueba: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
