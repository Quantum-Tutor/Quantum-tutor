from quantum_tutor_orchestrator import QuantumTutorOrchestrator


async def test_visual_request_exposes_image_pages():
    tutor = QuantumTutorOrchestrator()
    tutor.llm_enabled = False

    async def fake_run_rag(ctx):
        return {
            "context": "[Fuente: Galindo-Pascual Pagina 24]\nPozo infinito con referencia visual.",
            "image_pages": ["cohen_page_10", 24],
        }

    tutor._run_rag = fake_run_rag

    result = await tutor.generate_response_async(
        "podria ver las imagenes del libro que hablan del pozo infinito?"
    )

    assert result["context_retrieved"] is True
    assert result["image_pages"] == ["cohen_page_10", 24]
    assert "referencias visuales" in result["response"].lower()
