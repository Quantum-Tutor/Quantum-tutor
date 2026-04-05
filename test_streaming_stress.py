from quantum_tutor_orchestrator import QuantumTutorOrchestrator


async def test_streaming_response_contract_updates_metadata():
    tutor = QuantumTutorOrchestrator()
    tutor.llm_enabled = False
    tutor.api_keys = []
    tutor.client = None
    tutor._key_check_done = True

    async def fake_run_rag(ctx):
        return {
            "context": "[Fuente: Capitulo 2]\nDerivacion de la densidad de corriente de probabilidad.",
            "image_pages": [],
        }

    tutor._run_rag = fake_run_rag

    metadata, stream_iter = await tutor.generate_response_stream_async(
        user_input="Deriva la densidad de corriente de probabilidad"
    )

    chunks = []
    async for chunk in stream_iter:
        chunks.append(chunk)

    full_text = "".join(chunks)
    assert full_text
    assert metadata["context_retrieved"] is True
    assert metadata["latency"]["total"] >= 0
    assert "densidad de corriente" in full_text.lower()
