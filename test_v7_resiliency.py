import asyncio

from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from tool_scheduler import ToolScheduler, ToolRegistry
from quantum_request_context import QuantumRequestContext


async def test_handle_request_tolerates_empty_metadata():
    orch = QuantumTutorOrchestrator(scheduler=ToolScheduler(ToolRegistry()))
    orch.llm_enabled = False
    orch.api_keys = []
    orch.client = None
    orch._key_check_done = True

    async def fake_run_rag(ctx):
        return {"context": "Oscilador armonico en modo fallback.", "image_pages": []}

    orch._run_rag = fake_run_rag

    ctx = QuantumRequestContext(
        user_id="test",
        session_id="sess_meta",
        user_input="explica oscilador",
        conversation_history=[],
        relational=None,
        analytics=None,
    )
    ctx.metadata = {}

    chunks = []
    async for chunk in orch.handle_request(ctx):
        chunks.append(chunk)

    assert "".join(chunks)
    assert "scheduler" in ctx.metadata
    assert "execution_plan" in ctx.metadata


async def test_safe_execute_pipeline_converts_timeout_to_controlled_output():
    orch = QuantumTutorOrchestrator(scheduler=ToolScheduler(ToolRegistry()))
    orch.api_keys = []
    orch.client = None
    orch._key_check_done = True
    ctx = QuantumRequestContext(
        user_id="test",
        session_id="sess_timeout",
        user_input="calcula probabilidad",
        conversation_history=[],
        relational=None,
        analytics=None,
    )

    async def timeout_pipeline(_ctx):
        if False:
            yield ""
        raise asyncio.TimeoutError()

    orch._execute_pipeline = timeout_pipeline

    chunks = []
    async for chunk in orch._safe_execute_pipeline(ctx):
        chunks.append(chunk)

    assert ctx.cancelled is True
    assert any("Timeout" in chunk or "espera" in chunk for chunk in chunks)
