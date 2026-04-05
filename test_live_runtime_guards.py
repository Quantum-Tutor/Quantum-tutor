import types
import time
from unittest.mock import patch

from quantum_request_context import QuantumRequestContext
from quantum_tutor_orchestrator import QuantumTutorOrchestrator


async def test_greeting_short_circuits_rag_and_wolfram():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = False
    orch.client = None
    orch._key_check_done = True

    async def fail_rag(_ctx):
        raise AssertionError("RAG no deberia ejecutarse para un saludo simple.")

    async def fail_wolfram(_user_input):
        raise AssertionError("Wolfram no deberia ejecutarse para un saludo simple.")

    orch._run_rag = fail_rag
    orch._run_wolfram = fail_wolfram

    ctx = QuantumRequestContext(
        user_id="smoke",
        session_id="greeting-smoke",
        user_input="Hola",
        conversation_history=[],
    )

    response = ""
    async for chunk in orch.handle_request(ctx):
        response += chunk

    assert "Hola" in response
    assert ctx.metadata["execution_plan"] == {"run_rag": False, "run_wolfram": False}
    assert ctx.metadata["engine_status"] == "LOCAL_FALLBACK"


async def test_stream_llm_uses_local_fallback_when_provider_emits_no_text():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = True
    orch._key_check_done = True

    async def empty_stream():
        yield types.SimpleNamespace(text=None)

    async def generate_content_stream(**kwargs):
        return empty_stream()

    fake_client = types.SimpleNamespace(
        aio=types.SimpleNamespace(
            models=types.SimpleNamespace(
                generate_content_stream=generate_content_stream
            )
        )
    )
    orch.client = fake_client

    async def fake_snapshot():
        return {"client": fake_client, "api_key": "healthy-key", "model": orch.model_name}

    orch.get_client_snapshot = fake_snapshot

    ctx = QuantumRequestContext(
        user_id="smoke",
        session_id="empty-stream",
        user_input="Explica el oscilador armónico",
        conversation_history=[],
    )
    ctx.intent = "GENERAL"
    ctx.topic = "Oscilador Armónico"
    ctx.rag_data = {"context": "", "image_pages": []}

    chunks = []
    async for chunk in orch._stream_llm(ctx, "prompt"):
        chunks.append(chunk)

    response = "".join(chunks)
    assert "modo local de contingencia" in response
    assert "Oscilador Armónico" in response


async def test_startup_key_check_disables_llm_when_all_nodes_fail():
    class FakeClient:
        def __init__(self, api_key=None):
            self.api_key = api_key
            self.aio = types.SimpleNamespace(
                models=types.SimpleNamespace(generate_content=self.generate_content)
            )

        async def generate_content(self, **kwargs):
            raise RuntimeError("429 RESOURCE_EXHAUSTED")

    with patch("google.genai.Client", FakeClient):
        with patch.dict("os.environ", {"GEMINI_API_KEYS": "FAIL_A,FAIL_B"}, clear=False):
            orch = QuantumTutorOrchestrator()
            await orch._startup_key_check()

    assert orch.key_health == {"FAIL_A": "RATE_LIMIT", "FAIL_B": "RATE_LIMIT"}
    assert orch.llm_enabled is False
    assert orch.client is None
    assert orch.current_api_key == ""
    assert orch._next_key_check_at > time.time()


async def test_handle_request_rechecks_when_temporary_cooldown_expires():
    orch = QuantumTutorOrchestrator()
    orch.api_keys = ["TEMP_KEY"]
    orch.key_cooldowns = {"TEMP_KEY": 0.0}
    orch.key_health = {"TEMP_KEY": "RATE_LIMIT"}
    orch.llm_enabled = False
    orch.client = None
    orch.api_key = ""
    orch._key_check_done = True
    orch._next_key_check_at = time.time() - 1

    calls: list[bool] = []

    async def fake_startup(force: bool = False):
        calls.append(force)

    orch._startup_key_check = fake_startup

    ctx = QuantumRequestContext(
        user_id="smoke",
        session_id="recheck-after-cooldown",
        user_input="Hola",
        conversation_history=[],
    )

    response = ""
    async for chunk in orch.handle_request(ctx):
        response += chunk

    assert "Hola" in response
    assert calls == [True]
