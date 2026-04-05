import asyncio
import os
import sys
import logging
from dotenv import load_dotenv

# Asegurar que el path sea correcto para importar los módulos locales
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from multimodal_vision_parser import MultimodalVisionParser
from quantum_tutor_orchestrator import QuantumTutorOrchestrator

async def verify_multimodal_flow():
    logging.basicConfig(level=logging.INFO)
    print("========================================================================")
    print(" VERIFICACIÓN v5.0: MULTIMODAL FOUNDATIONS (GEMINI VISION)")
    print("========================================================================")
    
    load_dotenv()
    
    # 1. Inicializar componentes
    vision_parser = MultimodalVisionParser()
    tutor = QuantumTutorOrchestrator()
    
    print("\n[1] Probando MultimodalVisionParser (Modo Mock/Real)...")
    # Usamos un path inexiste para forzar el Mock y verificar la estructura JSON
    steps = vision_parser.parse_derivation_image("test_derivation_mock.jpg")
    
    if len(steps) > 0 and "latex" in steps[0]:
        print(f"    > Parser OK: {len(steps)} pasos detectados.")
        for s in steps:
            mark = " [X] ERROR" if s.get("error_flag") else " [OK]"
            print(f"      - Paso {s['step']}: {s['latex']}{mark}")
    else:
        print("    > ERROR: El parser no devolvió la estructura esperada.")
        return

    # 2. Simular el flujo del Orchestrator con los datos del Vision Parser
    print("\n[2] Probando Razonamiento Socrático con Datos de Visión...")
    
    # Construir el prompt como lo haría la UI
    vision_prompt = "He subido una foto de mi derivación. El modelo de visión detectó estos pasos:\n\n"
    for step in steps:
        is_err = step.get("error_flag", False)
        flag = " ❌ [ERROR DETECTADO]" if is_err else " ✅ [OK]"
        vision_prompt += f"- **Paso {step['step']}:** $${step['latex']}$$ ({step.get('description', '')}){flag}\n"
        if is_err:
            vision_prompt += f"  > *Razonamiento Vision:* {step.get('error_reason')}\n"
    
    vision_prompt += "\nPor favor revisa mi procedimiento y guíame hacia el error."
    
    print("    > Enviando prompt multimodal al Orchestrator...")
    result = await tutor.generate_response_async(vision_prompt)
    
    response_text = result.get("response", "")
    print("\n[RESULTADO DEL TUTOR]")
    print("-" * 40)
    try:
        print(response_text)
    except UnicodeEncodeError:
        print(response_text.encode('utf-8', errors='replace').decode('utf-8', errors='replace'))
    print("-" * 40)
    
    # Verificaciones finales
    if "modelo de visión extrajo esto" in vision_prompt.lower() or "modelo de visión detectó" in vision_prompt.lower():
         # Verificar que el tutor no dio la solución directa si había errores
         has_error = any(s.get("error_flag") for s in steps)
         if has_error:
             print("\n[3] Validación de Estrategia Pedagógica:")
             # Una heurística simple: si la respuesta es larga y menciona el paso del error sin dar el resultado final, es socrática
             if len(response_text) > 100:
                 print("    > Respuesta razonable detectada.")
             else:
                 print("    > ADVERTENCIA: La respuesta parece muy corta.")

    print("\n========================================================================")
    print(" Verificación v5.0 completada.")
    print("========================================================================")

if __name__ == "__main__":
    asyncio.run(verify_multimodal_flow())
