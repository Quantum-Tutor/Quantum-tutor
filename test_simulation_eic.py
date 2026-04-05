import pytest

from quantum_tutor_orchestrator import QuantumTutorOrchestrator


@pytest.mark.parametrize(
    "query, expected_topic, expected_visual, expected_run_wolfram",
    [
        ("Que es el pozo de potencial infinito?", "Pozo Infinito", False, False),
        ("Necesito calcular la energia del primer estado excitado en un pozo de 1nm", "Pozo Infinito", False, True),
        ("Muestrame la figura 5.1 del libro", "General", True, False),
        ("SISTEMA: RIGOR CHECK sobre el pozo de potencial", "Pozo Infinito", False, False),
    ],
)
async def test_simulation(query, expected_topic, expected_visual, expected_run_wolfram):
    tutor = QuantumTutorOrchestrator()
    tutor.llm_enabled = False
    tutor.api_keys = []
    tutor.client = None
    tutor._key_check_done = True

    async def fake_run_rag(ctx):
        image_pages = [51] if "figura" in ctx.user_input.lower() else []
        return {
            "context": f"[Fuente: Simulada]\nContexto para: {ctx.user_input}",
            "image_pages": image_pages,
        }

    async def fake_run_wolfram(user_input):
        if "calcula" in user_input.lower():
            return {"status": "success", "result_numeric": "E2"}
        return None

    tutor._run_rag = fake_run_rag
    tutor._run_wolfram = fake_run_wolfram

    result = await tutor.generate_response_async(query)

    assert result["topic"] == expected_topic
    assert bool(result["image_pages"]) is expected_visual
    assert result["execution_plan"]["run_wolfram"] is expected_run_wolfram
    assert result["wolfram_used"] is expected_run_wolfram
    assert result["response"]
