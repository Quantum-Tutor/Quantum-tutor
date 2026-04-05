from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from wolfram_emulator import WolframAlphaEmulator


def test_wolfram_emulator_understands_natural_language_integral():
    emulator = WolframAlphaEmulator()

    result = emulator.query("Calcula la integral de e^-x desde 0 hasta infinito")

    assert result["status"] == "success"
    assert result["result_numeric"] == 1.0
    assert "e^{-x}" in result["result_latex"]


async def test_local_fallback_explains_center_node_for_n2():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = False
    orch.client = None
    orch._key_check_done = True

    async def fake_run_rag(_ctx):
        return {
            "context": "[Fuente: Cohen-Tannoudji Pagina 94]\nSquare well potential and bound states.",
            "image_pages": ["cohen_page_94"],
        }

    orch._run_rag = fake_run_rag

    result = await orch.generate_response_async(
        "Explica por que en el pozo infinito la probabilidad en el centro es cero para n=2",
        [],
    )

    response = result["response"].lower()
    assert "probabilidad" in response
    assert "nodo" in response or "sin(\\pi)" in response or "sin(π)" in response
    assert result["image_pages"] == ["cohen_page_94"]
