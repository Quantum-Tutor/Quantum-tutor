
import asyncio
import json
import os
import sys

# Asegurar que el path sea correcto para importar los módulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from learning_analytics import LearningAnalytics

async def run_verification_v43():
    print("\n" + "="*72)
    print(" VERIFICACIÓN v6.1: CONVERGENCIA SINTÉTICA")
    print("="*72)
    
    # 1. Prueba de plateau en LearningAnalytics
    profile_path = 'student_profile_v43_test.json'
    analytics = LearningAnalytics(profile_path)
    
    print("\n[1] Verificando detección de plateau...")
    for i in range(4):  # Superar el umbral de 3
        analytics.log_interaction("Efecto Túnel", wolfram_invoked=True, passed_socratic=False)
        
    is_plateau = analytics.is_on_plateau("Efecto Túnel")
    scaff = analytics.get_scaffolding_level("Efecto Túnel")
    
    if is_plateau and scaff['label'] == "Plateau Cognitivo":
        print(f"    > Plateau detectado OK (consecutivos: {analytics.profile['topics']['Efecto Túnel']['consecutive_struggle']})")
        print(f"    > Etiqueta de andamiaje OK: {scaff['label']}")
    else:
        print(f"    > ERROR en detección de plateau: is_plateau={is_plateau}, label={scaff['label']}")

    # 2. Prueba de entropía en RelationalMind
    print("\n[2] Verificando entropía epistémica...")
    tutor = QuantumTutorOrchestrator()
    tutor.analytics = analytics
    
    # Activar un par de conceptos para generar entropía
    tutor.relational.update_state("Pozo Infinito", interaction_weight=0.5)
    tutor.relational.update_state("Efecto Túnel", interaction_weight=0.3)
    
    data = tutor.relational.get_affinity_data()
    entropy = data['entropy']
    stability = data['stability']
    
    print(f"    > Entropía (H): {entropy:.4f}")
    print(f"    > Estabilidad: {stability:.4f}")
    
    if entropy > 0 and stability >= 0:
        print("    > Métricas relacionales del runtime actual OK")
    else:
        print("    > ERROR en métricas relacionales.")

    # 3. Prueba de inferencia (simulada / heurística)
    print("\n[3] Verificando inferencia con métricas de plateau...")
    query = "No entiendo por qué la partícula pasa la barrera."
    result = await tutor.generate_response_async(query)
    
    response = result['response']
    if "PLATEAU" in response:
         print("    > Marca de plateau en la respuesta OK")
    if "H:" in response:
         print("    > Métrica de entropía en la respuesta OK")

    # Limpiar
    if os.path.exists(profile_path):
        os.remove(profile_path)
        
    print("\n" + "="*72)
    print(" Verificación v6.1 completada.")
    print("="*72 + "\n")

if __name__ == "__main__":
    asyncio.run(run_verification_v43())
