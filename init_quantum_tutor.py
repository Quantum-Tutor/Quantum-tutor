import json

def load_config():
    with open('quantum_tutor_config.json', 'r') as f:
        return json.load(f)

def initialize_agent():
    print("🚀 Iniciando Secuencia Boot de QuantumTutor...\n")
    config = load_config()
    
    print(f"[{config['system_metadata']['agent_name']} - {config['system_metadata']['version']}]")
    print(f"Arquitectura: {config['system_metadata']['architecture']}")
    print(f"Modelo Core: {config['llm_config']['model']} (Temp: {config['llm_config']['temperature']})")
    
    print(f"\n🧠 Motor RAG Configurado:")
    print(f"   Vector Store: {config['rag_parameters']['vector_store']}")
    print(f"   Embedding Model: {config['rag_parameters']['embedding_model']}")
    print(f"   Chunk Strategy: {config['rag_parameters']['chunk_strategy']}")
    
    print("\n⚙️ Integraciones Simbólicas Activas:")
    for tool in config['tool_definitions']:
        print(f"   - Tool: {tool['tool_name']}")
        print(f"     Descripción: {tool['description']}")
        print(f"     Reglas de uso estricto en: {', '.join(tool['enforce_usage_on'])}")
        
    print("\n🛡️ Guardrails y Seguridad:")
    print(f"   Score mínimo de Faithfulness: {config['safety_and_governance']['min_faithfulness_score']}")
    
    print("\n✅ QuantumTutor está listo para la simulación.")
    print("Puedes usar 'simulation.md' para ejecutar el caso de prueba: El Caso del Pozo Infinito.")

if __name__ == "__main__":
    initialize_agent()
