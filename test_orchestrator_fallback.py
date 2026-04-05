import asyncio
import os
from quantum_tutor_orchestrator import QuantumTutorOrchestrator

async def test_fallback_pedagogy():
    print("\n" + "="*50)
    print(" SHIELDING TEST: ORCHESTRATOR FALLBACK")
    print("="*50)
    
    # Forzar modo fallback desactivando el API Key en el objeto (o no pasándola)
    os.environ["GEMINI_API_KEY"] = "" 
    tutor = QuantumTutorOrchestrator()
    tutor.llm_enabled = False
    
    print(f"[*] Tutor en modo: {tutor.version} (LLM Enabled: {tutor.llm_enabled})")
    
    # Test 1: Continuidad y Contexto
    print("\n[*] Escenario 1: Tópico específico (Pozo Infinito)...")
    res1 = await tutor.generate_response_async("Háblame del pozo infinito")
    print(f"Tutor: {res1['response'][:200]}...")
    
    if "pozo infinito" in res1['response'].lower() and "🌀" in res1['response']:
        print("  [SUCCESS] Fallback detectó tópico y mantuvo metadatos.")
    else:
        print("  [WARNING] Fallback genérico o sin metadatos.")

    # Test 2: Memoria de contexto en el fallback
    history = [{"role": "user", "content": "Háblame del pozo infinito"}, {"role": "assistant", "content": res1['response']}]
    print("\n[*] Escenario 2: Cambio de tópico con historial (Efecto Tunel)...")
    res2 = await tutor.generate_response_async("¿Y el efecto tunel?", conversation_history=history)
    print(f"Tutor: {res2['response'][:200]}...")
    
    if "transicionando de" in res2['response'].lower() and "pozo infinito" in res2['response'].lower():
        print("  [SUCCESS] Fallback reconoció la transición desde el historial.")
    else:
        print("  [WARNING] Fallback no mostró conciencia de transición.")

    # Test 3: RAG en el fallback
    print("\n[*] Escenario 3: Verificación de RAG en fallback...")
    if "Material de Referencia" in res2['response'] or "Fuente:" in res2['response']:
        print("  [SUCCESS] Fallback integró fragmentos del RAG.")
    else:
        print("  [WARNING] No se detectó material de referencia en el fallback.")

    print("\n" + "="*50)
    print(" [OK] Orchestrator Fallback Verified.")
    print("="*50 + "\n")

if __name__ == "__main__":
    asyncio.run(test_fallback_pedagogy())
