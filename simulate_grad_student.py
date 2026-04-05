
import asyncio
import os
import sys
import json
from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from learning_analytics import LearningAnalytics

async def simulate_grad_student():
    print("\n" + "=" * 80)
    print(" SIMULACIÓN v6.1: INTERACCIÓN DE NIVEL POSTGRADO (AUTÓNOMO)")
    print("=" * 80)
    
    # 1. Preparar perfil de postgrado (sin bloqueo, alta maestría)
    profile_path = 'grad_student_profile.json'
    analytics = LearningAnalytics(profile_path)
    
    # Simular historial de éxito en temas base para activar modo autónomo
    analytics.log_interaction("Ec. Schrödinger", wolfram_invoked=False, passed_socratic=True)
    analytics.log_interaction("Espacio de Hilbert", wolfram_invoked=False, passed_socratic=True)
    
    tutor = QuantumTutorOrchestrator()
    tutor.analytics = analytics
    
    # 2. Consulta de nivel de postgrado
    query = (
        "Estimado doctor, estoy analizando la relación entre el Teorema del Virial y la estabilidad "
        "de estados ligados en potenciales de tipo ley de potencia $V(r) = ar^k$. "
        "¿Podría mostrarme la derivación del valor esperado de la energía cinética en términos de la potencial "
        "para el oscilador armónico tridimensional, y cómo esto se conecta con la ecuación de continuidad "
        "en la representación de momentos?"
    )
    
    print(f"\n[ESTUDIANTE POSTGRADO]: {query}\n")
    print("-" * 80)
    
    # 3. Generar respuesta
    result = await tutor.generate_response_async(query)
    
    scaff = result.get('scaffolding', {})
    print(f"\n[SISTEMA]: Modo {scaff.get('label', 'N/A')} Activo")
    print(f"[LATENCIA]: {result['latency']['total']}s")
    print(f"\n[TUTOR (Modo avanzado)]:\n")
    
    response = result['response']
    try:
        print(response)
    except UnicodeEncodeError:
        print(response.encode('ascii', 'replace').decode('ascii'))
    
    # Limpiar
    if os.path.exists(profile_path):
        os.remove(profile_path)
        
    print("\n" + "=" * 80)

if __name__ == "__main__":
    asyncio.run(simulate_grad_student())
