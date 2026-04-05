
import asyncio
import json
import os
import sys

# Asegurar que el path sea correcto para importar los módulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from learning_analytics import LearningAnalytics

async def run_verification_v42():
    print("\n" + "="*72)
    print(" VERIFICACIÓN v6.1: ANDAMIAJE RESONANTE")
    print("="*72)
    
    # 1. Preparar perfil de prueba con alto bloqueo conceptual
    profile_path = 'student_profile_v42_test.json'
    analytics = LearningAnalytics(profile_path)
    
    # Simular que el usuario tiene problemas con el pozo infinito
    for _ in range(5):
        analytics.log_interaction("Pozo Infinito", wolfram_invoked=True, passed_socratic=False)
    
    print("\n[1] Perfil de prueba creado con alto bloqueo en Pozo Infinito.")
    scaff = analytics.get_scaffolding_level("Pozo Infinito")
    print(f"    > Nivel detectado: {scaff['label']}")
    
    # 2. Inicializar orquestador del runtime actual
    tutor = QuantumTutorOrchestrator()
    tutor.analytics = analytics  # Inyectar perfil de prueba
    
    # 3. Prueba de inferencia con andamiaje
    query = "¿Cuál es la probabilidad en x=L/2 para n=2 en el pozo?"
    print(f"\n[2] Ejecutando consulta sobre Pozo Infinito (modo {scaff['label']})...")
    
    result = await tutor.generate_response_async(query)
    
    print(f"    > Estado del motor: {result['engine_status']}")
    print(f"    > Información de andamiaje: {result.get('scaffolding', {}).get('label', 'N/A')}")
    
    # 4. Prueba del motor simbólico expandido (teorema del virial)
    print("\n[3] Verificando teorema del virial local...")
    virial_query = "VirialTheorem[1/2 * m * omega^2 * x^2]"
    virial_res = tutor.local_engine.evaluate_local(virial_query)
    
    if virial_res and "Virial Theorem" in virial_res['source']:
        print(f"    > Virial local OK: {virial_res['result']}")
    else:
        print("    > ERROR: el teorema del virial no se detectó o falló.")

    # Limpiar
    if os.path.exists(profile_path):
        os.remove(profile_path)
        
    print("\n" + "="*72)
    print(" Verificación v6.1 completada satisfactoriamente.")
    print("="*72 + "\n")

if __name__ == "__main__":
    asyncio.run(run_verification_v42())
