import pytest

from tool_scheduler import ToolScheduler, ToolRegistry
from quantum_request_context import QuantumRequestContext


@pytest.fixture
def scheduler():
    return ToolScheduler(ToolRegistry())


@pytest.mark.parametrize(
    "query, expected_tools",
    [
        ("x^2 integral", {"wolfram"}),
        ("explica la funcion de onda", {"rag"}),
        ("deriva e^x", {"wolfram"}),
        ("que es el operador Hamiltoniano", {"rag"}),
        ("calcula la probabilidad", {"wolfram", "rag"}),
    ],
)
def test_scheduler_dataset(query, expected_tools, scheduler):
    ctx = QuantumRequestContext(
        user_id="test",
        session_id=f"dataset::{query}",
        user_input=query,
        conversation_history=[],
        relational=None,
        analytics=None,
    )

    plan = scheduler.plan(ctx)
    actual = set(ctx.metadata["scheduler"]["selected"])

    assert expected_tools.issubset(actual)
    if "wolfram" in expected_tools:
        assert plan.run_wolfram is True
    if "rag" in expected_tools:
        assert plan.run_rag is True
