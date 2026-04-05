"""
test_key_rotation.py
Tests del mecanismo de rotación de claves del orquestador.
Incluye test de seguridad: nodo INVALID no debe detener la rotación (bug fix break→continue).
"""
import asyncio
import sys
import os
import time
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from quantum_tutor_orchestrator import QuantumTutorOrchestrator


async def test_rotation():
    print("\n" + "="*60)
    print("  TEST DE ROTACION DEL RUNTIME ACTUAL (Simulacion 429)")
    print("="*60)

    # Mock de claves
    os.environ["GEMINI_API_KEYS"] = "KEY_MOCK_1,KEY_MOCK_2"
    
    orch = QuantumTutorOrchestrator()
    print(f"[*] Orquestador cargado con {len(orch.api_keys)} llaves mock.")

    # Mock del cliente de Gemini para que falle la primera vez con 429
    call_count = 0
    
    async def mock_generate_content_stream(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count <= 1:
            print(f"    [MOCK] Simulando 429 RESOURCE_EXHAUSTED en Nodo {orch.key_index}...")
            raise Exception("429 Resource exhausted: Quota exceeded")
        print(f"    [MOCK] Nodo {orch.key_index} respondiendo correctamente.")
        
        async def stream_generator():
            yield type('Chunk', (), {'text': "Rotación exitosa"})()
        return stream_generator()

    with patch('google.genai.Client') as mock_client:
        instance = mock_client.return_value
        instance.aio.models.generate_content_stream = mock_generate_content_stream
        
        orch.client = instance
        
        print("\n[STEP 1] Ejecutando consulta con fallo provocado...")
        res, stream = await orch.generate_response_stream_async("Explica algo complejo", [])
        
        response = ""
        async for chunk in stream:
            response += chunk
            
        print(f"\n[RESULTADO]")
        safe_resp = response[:50].encode("ascii", "ignore").decode("ascii")
        print(f"- Respuesta recibida: {safe_resp}...")
        
        if orch.key_index == 1 and orch.key_cooldowns["KEY_MOCK_1"] > time.time():
            print("\n[OK] TEST EXITOSO: El orquestador rotó al Nodo 1 y puso el Nodo 0 en cooldown.")
        else:
            print("\n[FAIL] TEST FALLIDO: No se detectó la rotación esperada.")


# =============================================================================
# SECURITY TEST — hardening 2026-04-05 (break→continue fix)
# =============================================================================

def test_key_rotation_skips_invalid_key_and_continues_to_next():
    """Regresión: rotate_client con key INVALID debe continuar iterando,
    nunca detenerse en el primer nodo INVALID (bug original usaba break).

    Esquema:
        KEY_0 → OK (actual, falla en el request)
        KEY_1 → INVALID (debe saltarse con continue)
        KEY_2 → OK (debe activarse como nuevo nodo)
    """
    os.environ["GEMINI_API_KEYS"] = "KEY_0,KEY_1,KEY_2"

    with patch("google.genai.Client"):
        orch = QuantumTutorOrchestrator()

    orch.api_keys = ["KEY_0", "KEY_1", "KEY_2"]
    orch.key_index = 0
    orch.api_key = "KEY_0"
    orch.key_cooldowns = {"KEY_0": 0.0, "KEY_1": 0.0, "KEY_2": 0.0}
    orch.key_health = {
        "KEY_0": "RATE_LIMIT",   # falla actual
        "KEY_1": "INVALID",      # debe saltarse con continue (no break)
        "KEY_2": "OK",           # debe activarse
    }
    # Simular cooldown en KEY_0 para que no sea elegida
    orch.key_cooldowns["KEY_0"] = time.time() + 60.0

    with patch("google.genai.Client") as mock_client:
        orch.client = mock_client.return_value
        asyncio.run(orch.rotate_client())

    assert orch.api_key == "KEY_2", (
        f"rotate_client debe saltar KEY_1 (INVALID) y activar KEY_2, "
        f"pero activó: {orch.api_key}"
    )
    assert orch.key_index == 2


def test_key_rotation_raises_when_all_nodes_exhausted():
    """Si todos los nodos están en cooldown o son INVALID, debe lanzar excepción."""
    os.environ["GEMINI_API_KEYS"] = "KEY_0,KEY_1"

    with patch("google.genai.Client"):
        orch = QuantumTutorOrchestrator()

    orch.api_keys = ["KEY_0", "KEY_1"]
    orch.key_index = 0
    orch.key_cooldowns = {
        "KEY_0": time.time() + 60.0,
        "KEY_1": time.time() + 60.0,
    }
    orch.key_health = {"KEY_0": "RATE_LIMIT", "KEY_1": "RATE_LIMIT"}

    import pytest
    with pytest.raises(Exception, match="RESOURCE_EXHAUSTED_ALL_NODES"):
        asyncio.run(orch.rotate_client())


if __name__ == "__main__":
    asyncio.run(test_rotation())
