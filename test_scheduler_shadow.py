import pytest

from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from tool_scheduler import ToolScheduler, ToolRegistry
from quantum_request_context import QuantumRequestContext


@pytest.mark.parametrize(
    "query, expected_tools",
    [
        ("commutator de x", {"wolfram"}),
        ("como funciona el pozo infinito", {"rag"}),
        ("x^2 integral", {"wolfram"}),
        ("explica que es 1+1", {"wolfram"}),
    ],
)
async def test_shadow_queries_keep_scheduler_metadata(query, expected_tools):
    orch = QuantumTutorOrchestrator(scheduler=ToolScheduler(ToolRegistry()))
    orch.llm_enabled = False
    orch.api_keys = []
    orch.client = None
    orch._key_check_done = True

    async def fake_run_rag(ctx):
        return {"context": "Contexto sintetico.", "image_pages": []}

    async def fake_run_wolfram(user_input):
        return {"status": "success", "result_numeric": "1"}

    orch._run_rag = fake_run_rag
    orch._run_wolfram = fake_run_wolfram

    ctx = QuantumRequestContext(
        user_id="test",
        session_id=f"shadow::{query}",
        user_input=query,
        conversation_history=[],
        relational=None,
        analytics=None,
    )

    async for _ in orch.handle_request(ctx):
        pass

    selected = set(ctx.metadata.get("scheduler", {}).get("selected", []))
    assert expected_tools.issubset(selected)
    assert "execution_plan" in ctx.metadata
