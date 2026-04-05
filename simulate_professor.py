
import asyncio
import os
import sys
from quantum_tutor_orchestrator import QuantumTutorOrchestrator

async def simulate():
    print("\n" + "=" * 80)
    print(" SIMULACIÓN DE INTERACCIÓN: ROL PROFESOR DE CUÁNTICA")
    print("=" * 80)
    
    tutor = QuantumTutorOrchestrator()
    
    # Consulta de nivel avanzado (Profesor)
    query = (
        "Estimado colega, estoy revisando el formalismo de paridad en potenciales simétricos. "
        "¿Podría explicarme cómo la invarianza bajo reflexión espacial del Hamiltoniano en un pozo infinito centrado "
        "en el origen condiciona la paridad de los estados estacionarios, y qué implicaciones tiene esto para el valor "
        "esperado de la posición?"
    )
    
    print(f"\n[PROFESOR]: {query}\n")
    print("-" * 80)
    
    result, stream = await tutor.generate_response_stream_async(query)
    
    print(f"\n[LATENCIA_IO]: {result['latency']['io_fetch']}s")
    print(f"\n[TUTOR (Catedrático Emérito)]:\n")
    
    async for chunk in stream:
        try:
            print(chunk, end="", flush=True)
        except UnicodeEncodeError:
            print(chunk.encode('ascii', 'replace').decode('ascii'), end="", flush=True)
    
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(simulate())
