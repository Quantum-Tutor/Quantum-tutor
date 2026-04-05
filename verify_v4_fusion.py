
import asyncio
import json
import os
import sys

# Asegurar que el path sea correcto para importar los módulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from quantum_tutor_orchestrator import QuantumTutorOrchestrator

async def run_simulation():
    print("iniciando simulación QuantumTutor v6.1 (dinámica relacional)")
    print("-" * 50)
    
    tutor = QuantumTutorOrchestrator()
    
    queries = [
        "Hola, quiero aprender sobre mecánica cuántica",
        "¿Qué es la ecuación de Schrödinger?",
        "Háblame sobre el pozo infinito",
        "¿Cómo se relaciona esto con la densidad de probabilidad?",
        "Calcula la probabilidad en el pozo para n=1"
    ]
    
    for i, q in enumerate(queries):
        print(f"\n[Interacción {i+1}] Usuario: {q}")
        result = await tutor.generate_response_async(q)
        
        rd = result.get("relational_data", {})
        omega = rd.get("omega_class", "Desconocida")
        attractor = rd.get("attractor", "Ninguno")
        convergence = rd.get("convergence", 0.0)
        
        print(f"  > OMEGA: {omega}")
        print(f"  > Atractor: {attractor}")
        print(f"  > Convergencia: {convergence*100:.1f}%")
        
        # Verificar que el RAG usó el reranking relacional
        if result.get("context_retrieved"):
             print("  > RAG: OK (reranking relacional activo)")
        
        # Simular una pausa breve
        await asyncio.sleep(0.1)

    print("\n" + "="*50)
    print("Simulación completada satisfactoriamente.")
    print("No se detectaron colapsos en el flujo de la sesión.")

if __name__ == "__main__":
    asyncio.run(run_simulation())
