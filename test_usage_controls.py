import time

from quantum_request_context import QuantumRequestContext
from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from request_optimization import BackpressureDecision, RateLimitDecision, RequestBackpressureError
from security_controls import FileCircuitBreaker


async def test_handle_request_uses_response_cache_before_provider_budget():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = True
    orch.client = object()
    orch._key_check_done = True

    async def fail_rag(_ctx):
        raise AssertionError("RAG should not run on a cache hit.")

    async def fail_wolfram(_user_input):
        raise AssertionError("Wolfram should not run on a cache hit.")

    def fail_consume(_user_id, cost=1.0):
        raise AssertionError("Rate limiter should not consume on a cache hit.")

    orch._run_rag = fail_rag
    orch._run_wolfram = fail_wolfram
    orch.rate_limiter.consume = fail_consume
    orch.response_cache.lookup = lambda query, namespace: {
        "response": "Respuesta servida desde cache.",
        "match_type": "exact",
        "similarity": 1.0,
    }

    ctx = QuantumRequestContext(
        user_id="cache-user",
        session_id="cache-hit",
        user_input="Resume brevemente la dualidad onda particula",
        conversation_history=[],
    )

    response = ""
    async for chunk in orch.handle_request(ctx):
        response += chunk

    assert response == "Respuesta servida desde cache."
    assert ctx.metadata["engine_status"] == "RESPONSE_CACHE"
    assert ctx.metadata["cache"]["hit"] is True


async def test_handle_request_uses_precomputed_definition_before_rate_limit():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = True
    orch.client = object()
    orch._key_check_done = True

    def fail_consume(_user_id, cost=1.0):
        raise AssertionError("Rate limiter should not consume on a precomputed answer.")

    orch.rate_limiter.consume = fail_consume
    orch.response_cache.lookup = lambda query, namespace: None

    ctx = QuantumRequestContext(
        user_id="kb-user",
        session_id="precomputed-hit",
        user_input="Que es el oscilador armonico?",
        conversation_history=[],
    )

    response = ""
    async for chunk in orch.handle_request(ctx):
        response += chunk

    assert "Respuesta precomputada" in response
    assert "potencial cuadratico" in response
    assert ctx.metadata["engine_status"] == "PRECOMPUTED_LOCAL"
    assert ctx.metadata["deterministic"]["kind"] == "precomputed"


async def test_handle_request_uses_local_symbolic_before_rate_limit():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = True
    orch.client = object()
    orch._key_check_done = True

    def fail_consume(_user_id, cost=1.0):
        raise AssertionError("Rate limiter should not consume on a deterministic symbolic answer.")

    orch.rate_limiter.consume = fail_consume
    orch.response_cache.lookup = lambda query, namespace: None

    ctx = QuantumRequestContext(
        user_id="sym-user",
        session_id="symbolic-hit",
        user_input="Calcula el conmutador [x,p]",
        conversation_history=[],
    )

    response = ""
    async for chunk in orch.handle_request(ctx):
        response += chunk

    assert "Resolucion deterministica local" in response
    assert "i\\hbar" in response
    assert ctx.metadata["engine_status"] == "DETERMINISTIC_LOCAL"
    assert ctx.metadata["deterministic"]["kind"] == "local_symbolic"


async def test_local_response_keeps_provider_retry_visibility_when_cooldown_is_scheduled():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = False
    orch.client = None
    orch._key_check_done = True

    now = time.time()
    orch._next_key_check_at = now + 12.0
    orch.key_cooldowns = {
        "node-a": now + 12.0,
        "node-b": now - 1.0,
    }

    ctx = QuantumRequestContext(
        user_id="retry-visibility-user",
        session_id="retry-visibility",
        user_input="Que es el oscilador armonico?",
        conversation_history=[],
    )

    response = ""
    async for chunk in orch.handle_request(ctx):
        response += chunk

    assert "Respuesta precomputada" in response
    assert ctx.metadata["engine_status"] == "PRECOMPUTED_LOCAL"
    assert ctx.metadata["provider_retry"]["scheduled"] is True
    assert ctx.metadata["provider_retry"]["active_cooldown_nodes"] == 1
    assert ctx.metadata["provider_retry"]["retry_after_seconds"] > 0


async def test_handle_request_soft_rate_limit_falls_back_locally():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = True
    orch.client = object()
    orch._key_check_done = True

    async def fake_rag(_ctx):
        return {"context": "Contexto bibliografico minimo.", "image_pages": []}

    async def fake_snapshot():
        return {"client": object(), "api_key": "live-key", "model": orch.model_name}

    async def fail_reasoning(_ctx, _snapshot, _route=None):
        raise AssertionError("Reasoning should not run when the rate limiter denies the request.")

    orch._run_rag = fake_rag
    orch.get_client_snapshot = fake_snapshot
    orch._reason_about_query = fail_reasoning
    orch.response_cache.lookup = lambda query, namespace: None
    orch.response_cache.store = lambda **kwargs: None
    orch.rate_limiter.consume = lambda user_id, cost=1.0: RateLimitDecision(
        allowed=False,
        retry_after_seconds=6.0,
        remaining_tokens=0.0,
        capacity=20.0,
        refill_tokens=1.0,
        refill_seconds=3.0,
        consumed_tokens=0.0,
        bucket_id="bucket-soft-limit",
    )

    ctx = QuantumRequestContext(
        user_id="limited-user",
        session_id="soft-limit",
        user_input="Analiza el oscilador armonico en detalle",
        conversation_history=[],
    )

    response = ""
    async for chunk in orch.handle_request(ctx):
        response += chunk

    assert "Guard de consumo activo" in response
    assert "modo local de contingencia" in response
    assert ctx.metadata["engine_status"] == "RATE_LIMITED_LOCAL"
    assert ctx.metadata["rate_limit"]["limited"] is True


async def test_handle_request_soft_backpressure_falls_back_locally():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = True
    orch.client = object()
    orch._key_check_done = True

    async def fake_rag(_ctx):
        return {"context": "Contexto bibliografico minimo.", "image_pages": []}

    async def fake_snapshot():
        return {"client": object(), "api_key": "live-key", "model": orch.model_name}

    async def fake_stream(_ctx, _prompt, route=None):
        raise RequestBackpressureError(
            BackpressureDecision(
                limited=True,
                retry_after_seconds=2.5,
                queue_timeout_seconds=1.5,
                queue_depth=3,
                concurrency_limit=1,
                operation="stream",
                wait_time_seconds=1.5,
            )
        )
        yield  # pragma: no cover

    orch._run_rag = fake_rag
    orch.get_client_snapshot = fake_snapshot
    orch._stream_llm = fake_stream
    orch.response_cache.lookup = lambda query, namespace: None
    orch.response_cache.store = lambda **kwargs: None
    orch.rate_limiter.consume = lambda user_id, cost=1.0: RateLimitDecision(
        allowed=True,
        retry_after_seconds=0.0,
        remaining_tokens=19.0,
        capacity=20.0,
        refill_tokens=1.0,
        refill_seconds=3.0,
        consumed_tokens=1.0,
        bucket_id="bucket-backpressure",
    )

    ctx = QuantumRequestContext(
        user_id="busy-user",
        session_id="soft-backpressure",
        user_input="Analiza la ecuacion de Schrodinger dependiente del tiempo",
        conversation_history=[],
    )

    response = ""
    async for chunk in orch.handle_request(ctx):
        response += chunk

    assert "Backpressure activo" in response
    assert "modo local de contingencia" in response
    assert ctx.metadata["engine_status"] == "BACKPRESSURE_LOCAL"
    assert ctx.metadata["backpressure"]["limited"] is True


async def test_handle_request_uses_local_fallback_when_provider_circuit_breaker_is_open(tmp_path):
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = True
    orch.client = object()
    orch._key_check_done = True
    orch.provider_name = "gemini_text_test"
    orch.provider_circuit_breaker = FileCircuitBreaker(
        state_path=tmp_path / "provider_circuit_breakers.json",
        failure_threshold=1,
        window_seconds=30.0,
        open_seconds=20.0,
        half_open_retry_seconds=2.0,
    )
    orch.provider_circuit_breaker.record_failure(orch.provider_name, "UNAVAILABLE")

    async def fake_rag(_ctx):
        return {"context": "Contexto bibliografico minimo.", "image_pages": []}

    async def fake_snapshot():
        return {"client": object(), "api_key": "live-key", "model": orch.model_name}

    def fail_consume(_user_id, cost=1.0):
        raise AssertionError("Rate limiter should not consume when circuit breaker is open.")

    async def fail_stream(_ctx, _prompt, route=None):
        raise AssertionError("Provider stream should not run when circuit breaker is open.")
        yield  # pragma: no cover

    orch._run_rag = fake_rag
    orch.get_client_snapshot = fake_snapshot
    orch.rate_limiter.consume = fail_consume
    orch._stream_llm = fail_stream
    orch.response_cache.lookup = lambda query, namespace: None
    orch.response_cache.store = lambda **kwargs: None

    ctx = QuantumRequestContext(
        user_id="breaker-user",
        session_id="breaker-open",
        user_input="Analiza la ecuacion de Schrodinger dependiente del tiempo",
        conversation_history=[],
    )

    response = ""
    async for chunk in orch.handle_request(ctx):
        response += chunk

    assert "Circuit breaker activo" in response
    assert ctx.metadata["engine_status"] == "CIRCUIT_BREAKER_LOCAL"
    assert ctx.metadata["circuit_breaker"]["blocked"] is True


async def test_simple_queries_skip_reasoning_and_use_simple_route():
    orch = QuantumTutorOrchestrator()
    orch.llm_enabled = True
    orch.client = object()
    orch._key_check_done = True

    async def fake_rag(_ctx):
        return {"context": "", "image_pages": []}

    async def fake_snapshot():
        return {"client": object(), "api_key": "live-key", "model": orch.model_name}

    async def fail_reasoning(_ctx, _snapshot, _route=None):
        raise AssertionError("Simple queries should skip the reasoning call.")

    async def fake_stream(_ctx, _prompt, route=None):
        assert route is not None
        assert route.tier == "simple"
        assert route.reasoning_enabled is False
        yield "Respuesta breve."

    orch._run_rag = fake_rag
    orch.get_client_snapshot = fake_snapshot
    orch._reason_about_query = fail_reasoning
    orch._stream_llm = fake_stream
    orch.response_cache.lookup = lambda query, namespace: None
    orch.response_cache.store = lambda **kwargs: None
    orch.rate_limiter.consume = lambda user_id, cost=1.0: RateLimitDecision(
        allowed=True,
        retry_after_seconds=0.0,
        remaining_tokens=19.0,
        capacity=20.0,
        refill_tokens=1.0,
        refill_seconds=3.0,
        consumed_tokens=1.0,
        bucket_id="bucket-simple-route",
    )

    ctx = QuantumRequestContext(
        user_id="simple-user",
        session_id="simple-route",
        user_input="Define superposicion cuantica",
        conversation_history=[],
    )

    response = ""
    async for chunk in orch.handle_request(ctx):
        response += chunk

    assert response == "Respuesta breve."
    assert ctx.metadata["model_route"]["tier"] == "simple"
    assert ctx.metadata["rate_limit"]["allowed"] is True
