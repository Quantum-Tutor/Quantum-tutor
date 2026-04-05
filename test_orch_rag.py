from quantum_tutor_orchestrator import QuantumTutorOrchestrator


async def test_orchestrator_uses_rag_context_in_fallback():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = False

    async def fake_run_rag(ctx):
        return {
            "context": "[Fuente: Galindo-Pascual Pagina 47]\nParticula en una caja o pozo infinito.",
            "image_pages": [47],
        }

    orch._run_rag = fake_run_rag

    result = await orch.generate_response_async(
        "Explica la particula en una caja o pozo de potencial infinito",
        [],
    )

    assert result["context_retrieved"] is True
    assert result["image_pages"] == [47]
    assert "pozo infinito" in result["response"].lower()
