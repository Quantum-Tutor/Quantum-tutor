from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from tool_scheduler import ToolScheduler, ToolRegistry
from quantum_request_context import QuantumRequestContext


async def test_scheduler_metadata_for_math_query():
    orch = QuantumTutorOrchestrator(scheduler=ToolScheduler(ToolRegistry()))
    ctx = QuantumRequestContext(
        user_id="test",
        session_id="integration::math",
        user_input="Calcula la integral de e^-x desde 0 a infinito",
        conversation_history=[],
        relational=None,
        analytics=None,
    )

    async for _ in orch.handle_request(ctx):
        pass

    assert "wolfram" in ctx.metadata.get("scheduler", {}).get("selected", [])
    assert ctx.metadata.get("execution_plan", {}).get("run_wolfram") is True


async def test_scheduler_metadata_for_definition_query():
    orch = QuantumTutorOrchestrator(scheduler=ToolScheduler(ToolRegistry()))
    ctx = QuantumRequestContext(
        user_id="test",
        session_id="integration::definition",
        user_input="Explica el concepto de funcion de onda",
        conversation_history=[],
        relational=None,
        analytics=None,
    )

    async for _ in orch.handle_request(ctx):
        pass

    assert "rag" in ctx.metadata.get("scheduler", {}).get("selected", [])
    assert ctx.metadata.get("execution_plan", {}).get("run_rag") is True
