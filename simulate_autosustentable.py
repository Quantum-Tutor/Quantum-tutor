import asyncio
import time
import json
import logging
import os
import sys

# Asegurar path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from quantum_tutor_paths import SIMULATION_OPTIMIZATION_PATH, ensure_output_dirs

# Logger para la simulación
log_format = '%(asctime)s [%(levelname)s] %(message)s'
logging.basicConfig(level=logging.INFO, format=log_format)
logger = logging.getLogger("TutorSimulation")

async def run_simulation():
    print("\n" + "="*80)
    print(" INICIANDO SIMULACIÓN DE ESTRÉS Y AUTOSUSTENTABILIDAD (v6.1) ")
    print("="*80 + "\n")

    tutor = QuantumTutorOrchestrator()
    
    # Perfiles de simulación: "Estudiante confundido con Pozo Infinito y Efecto Túnel"
    queries = [
        # 1. Base (debe usar RAG)
        "Hola, estoy empezando a estudiar la ecuación de Schrödinger. ¿Qué es?",
        # 2. Concepto específico
        "No entiendo el concepto del Pozo Infinito. ¿Por qué la energía está cuantizada?",
        # 3. Matemática / Wolfram
        "Calcula la probabilidad de encontrar la partícula en el centro del pozo para n=2",
        # 4. Forzar plateau repitiendo la duda
        "Pero sigo sin entender por qué no puede haber energía cero en el pozo infinito.",
        "De verdad me cuesta mucho, la energía de punto cero no tiene sentido clásico.",
        "Explícame otra vez lo de la energía mínima, no avanzo.",
        # 5. Cambio abrupto de tema (entropía alta)
        "Bueno, dejemos eso... ¿Qué pasa en el efecto túnel cuántico?",
    ]

    history = []
    metrics_log = []

    for i, query in enumerate(queries, 1):
        print(f"\n[{i}/{len(queries)}] ESTUDIANTE: {query}")
        
        start_time = time.perf_counter()
        
        # Ejecutar el orquestador
        result = await tutor.generate_response_async(query, conversation_history=history)
        
        latency = time.perf_counter() - start_time
        
        # Guardar en historial
        history.append({"role": "user", "content": query})
        history.append({"role": "assistant", "content": result['response']})
        
        # Extraer métricas relevantes
        rel_data = result.get('relational_data', {})
        metrics = {
            "turn": i,
            "latency_total": result['latency']['total'],
            "rag_used": result.get('context_retrieved', False),
            "wolfram_used": result.get('wolfram_used', False),
            "attractor": rel_data.get('attractor'),
            "entropy": rel_data.get('entropy'),
            "scaffolding_level": result.get('scaffolding', {}).get('label')
        }
        metrics_log.append(metrics)
        
        print(f"      [TUTOR LATENCIA]: {metrics['latency_total']:.2f}s | [RAG]: {metrics['rag_used']} | [WOLFRAM]: {metrics['wolfram_used']}")
        print(f"      [ESTADO MENTAL]: Atractor='{metrics['attractor']}', Entropía={metrics['entropy']:.2f}, Nivel Socrático='{metrics['scaffolding_level']}'")
        
        # Mostrar un fragmento breve de la respuesta
        snippet = result['response'][:150].replace('\n', ' ') + "..."
        print(f"      [RESPUESTA]: {snippet}")
        
        # Pausa breve simulando tiempo de lectura
        await asyncio.sleep(1)

    print("\n" + "="*80)
    print(" 📊 RESUMEN DE OPTIMIZACIÓN Y MÉTRICAS ")
    print("="*80)
    
    # Análisis de resultados
    total_time = sum(m['latency_total'] for m in metrics_log)
    avg_time = total_time / len(queries)
    
    print(f"\n- Tiempo Promedio de Respuesta: {avg_time:.2f}s")
    print("- Uso de RAG: " + str(sum(1 for m in metrics_log if m['rag_used'])) + f"/{len(queries)}")
    print("- Uso de Wolfram/Symbolic: " + str(sum(1 for m in metrics_log if m['wolfram_used'])) + f"/{len(queries)}")
    
    # Detección de posibles ineficiencias:
    print("\n🔍 RUTAS DE OPTIMIZACIÓN DETECTADAS:")
    
    if avg_time > 5.0:
        print("  ❌ [LATENCIA] El tiempo promedio supera los 5 segundos. Conviene considerar streaming real o paralelizar con más fuerza el RAG y el ensamblado de contexto.")
    else:
        print("  ✅ [LATENCIA] Tiempo de respuesta dentro de límites aceptables (< 5s).")
        
    plateaus = [m for m in metrics_log if m['scaffolding_level'] == 'Plateau Cognitivo']
    if plateaus:
        print(f"  ✅ [PEDAGOGÍA] Se detectó Plateau Cognitivo en el turno {plateaus[0]['turn']}, el andamiaje funciona.")
    else:
        print("  ⚠️ [PEDAGOGÍA] No se logró llegar al plateau. Revisar la heurística en LearningAnalytics, que podría estar demasiado laxa.")

    high_entropy = [m for m in metrics_log if m['entropy'] and m['entropy'] > 0.6]
    if high_entropy:
        print(f"  ✅ [ESTABILIDAD] Se detectó Entropía alta ({high_entropy[0]['entropy']:.2f}) tras el cambio de tema.")
    else:
        print("  ⚠️ [ESTABILIDAD] La entropía no sube lo suficiente al cambiar abruptamente. Ajustar el kernel relacional.")

    # Guardar reporte
    ensure_output_dirs()
    with open(SIMULATION_OPTIMIZATION_PATH, 'w', encoding='utf-8') as f:
        json.dump(metrics_log, f, indent=4)
        print(f"\n[+] Reporte completo guardado en '{SIMULATION_OPTIMIZATION_PATH}'")

if __name__ == "__main__":
    asyncio.run(run_simulation())
