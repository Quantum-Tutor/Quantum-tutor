import uuid
from pathlib import Path
from types import SimpleNamespace

from fastapi.testclient import TestClient

import api_quantum_tutor as api
from api_security import APISecurityManager


class FakeTutor:
    def __init__(self, metadata=None, chunks=None):
        self.rag = SimpleNamespace(vector_store=[{"id": "chunk"}])
        self.calls = []
        self.metadata = metadata or {
            "topic": "General",
            "wolfram_used": False,
            "context_retrieved": True,
            "image_pages": [],
            "latency": {"total": 0.01},
        }
        self.chunks = chunks or ["Respuesta ", "de prueba"]

    async def generate_response_stream_async(self, message, conversation_history=None, **kwargs):
        self.calls.append({
            "message": message,
            "conversation_history": conversation_history,
            "kwargs": kwargs,
        })

        async def stream():
            for chunk in self.chunks:
                yield chunk
        return dict(self.metadata), stream()


class FailingTutor:
    def __init__(self):
        self.rag = SimpleNamespace(vector_store=[{"id": "chunk"}])

    async def generate_response_stream_async(self, message, conversation_history=None, **kwargs):
        raise RuntimeError("core exploded")


class RateLimitedTutor:
    def __init__(self):
        self.rag = SimpleNamespace(vector_store=[{"id": "chunk"}])

    async def generate_response_stream_async(self, message, conversation_history=None, **kwargs):
        metadata = {
            "rate_limit": {
                "limited": True,
                "retry_after_seconds": 3.2,
            }
        }

        async def stream():
            yield "[ERROR SISTEMICO]: rate limited"

        return metadata, stream()


class BackpressureTutor:
    def __init__(self):
        self.rag = SimpleNamespace(vector_store=[{"id": "chunk"}])

    async def generate_response_stream_async(self, message, conversation_history=None, **kwargs):
        metadata = {
            "backpressure": {
                "limited": True,
                "retry_after_seconds": 2.1,
            }
        }

        async def stream():
            yield "[ERROR SISTEMICO]: backpressure"

        return metadata, stream()


class FakeAnalytics:
    def __init__(self):
        self.logged = []

    def log_interaction(self, topic, wolfram_invoked, passed_socratic):
        self.logged.append({
            "topic": topic,
            "wolfram_invoked": wolfram_invoked,
            "passed_socratic": passed_socratic,
        })

    def get_misconception_clusters(self):
        return {
            "Error_Calculo": [],
            "Error_Conceptual": ["Oscilador Armónico"],
            "Falla_Base": [],
            "Dominado": ["Pozo Infinito"],
        }


class FakeVisionParser:
    def parse_derivation_image(self, image_path):
        return [
            {
                "step": 1,
                "latex": "x^2",
                "description": "Paso correcto",
                "error_flag": False,
            },
            {
                "step": 2,
                "latex": "-2i\\hbar x",
                "description": "Error de signo",
                "error_flag": True,
                "error_reason": "El signo correcto es positivo.",
            },
        ]


def build_security_manager(tmp_path: Path | None = None):
    if tmp_path:
        edge_path = tmp_path / "api_edge_rate_limits.json"
        abuse_path = tmp_path / "api_abuse_state.json"
    else:
        edge_path = Path.cwd() / f"api_edge_rate_limits_{uuid.uuid4().hex}.json"
        abuse_path = Path.cwd() / f"api_abuse_state_{uuid.uuid4().hex}.json"
    return APISecurityManager(edge_state_path=edge_path, abuse_state_path=abuse_path)


def build_client(monkeypatch, tutor=None, analytics=None, vision_parser=None, security_manager=None):
    monkeypatch.setattr(api, "tutor", tutor if tutor is not None else FakeTutor())
    monkeypatch.setattr(api, "analytics", analytics if analytics is not None else FakeAnalytics())
    monkeypatch.setattr(api, "vision_parser", vision_parser if vision_parser is not None else FakeVisionParser())
    monkeypatch.setattr(api, "security", security_manager if security_manager is not None else build_security_manager())
    return TestClient(api.app)


def test_startup_snapshot_reports_multi_key_runtime(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "ACTIVEKEY001,BACKUPKEY002")
    monkeypatch.setattr(
        api,
        "tutor",
        SimpleNamespace(
            rag=SimpleNamespace(vector_store=[{"id": "chunk"}]),
            llm_enabled=True,
            client=object(),
            current_api_key="ACTIVEKEY001",
            key_health={"ACTIVEKEY001": "OK", "BACKUPKEY002": "ERROR"},
        ),
    )

    snapshot = api._startup_snapshot()

    assert snapshot["status"] == "READY"
    assert snapshot["gemini_ok"] is True
    assert snapshot["gemini_configured"] is True
    assert snapshot["gemini_node_count"] == 2
    assert snapshot["gemini_active_key"] == "ACTIVE...001"
    assert snapshot["gemini_runtime"] == "HYBRID_RELATIONAL"
    assert snapshot["gemini_key_health"]["BACKUPKEY002"] == "ERROR"


def test_startup_snapshot_degrades_when_llm_runtime_is_down(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEYS", "ACTIVEKEY001")
    monkeypatch.setattr(
        api,
        "tutor",
        SimpleNamespace(
            rag=SimpleNamespace(vector_store=[{"id": "chunk"}]),
            llm_enabled=False,
            client=None,
            current_api_key="",
            key_health={"ACTIVEKEY001": "ERROR"},
        ),
    )

    snapshot = api._startup_snapshot()

    assert snapshot["status"] == "DEGRADED"
    assert snapshot["gemini_ok"] is False
    assert snapshot["gemini_configured"] is True
    assert snapshot["gemini_node_count"] == 1
    assert snapshot["gemini_active_key"] == ""
    assert snapshot["gemini_runtime"] == "LOCAL_FALLBACK"


def test_chat_rejects_empty_query(monkeypatch):
    with build_client(monkeypatch) as client:
        response = client.post("/api/chat", json={"message": "", "history": []})

    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "EMPTY_QUERY"
    assert "request_id" in data


def test_health_reports_runtime_and_request_id(monkeypatch):
    with build_client(monkeypatch) as client:
        response = client.get("/health", headers={"x-request-id": "edge-health-1"})

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "edge-health-1"
    data = response.json()
    assert data["status"] == "ok"
    assert data["request_id"] == "edge-health-1"
    assert "runtime_status" in data


def test_chat_rejects_too_long_query(monkeypatch):
    with build_client(monkeypatch) as client:
        response = client.post("/api/chat", json={"message": "A" * 5000, "history": []})

    assert response.status_code == 400
    data = response.json()
    assert data["error_code"] == "QUERY_TOO_LONG"
    assert "request_id" in data


def test_chat_success_returns_metadata_and_analytics(monkeypatch):
    fake_analytics = FakeAnalytics()
    with build_client(monkeypatch, analytics=fake_analytics) as client:
        response = client.post(
            "/api/chat",
            json={
                "message": "¿Qué es el oscilador armónico?",
                "history": [{"role": "user", "content": "Hola"}],
            },
        )

    assert response.status_code == 200
    data = response.json()
    assert data["response"] == "Respuesta de prueba"
    assert data["analytics"]["topic"] == "Oscilador Armónico"
    assert data["analytics"]["misconception_clusters"]["Dominado"] == ["Pozo Infinito"]
    assert "request_id" in data
    assert fake_analytics.logged[0]["topic"] == "Oscilador Armónico"


def test_chat_ignores_untrusted_forwarded_identity_headers(monkeypatch, tmp_path):
    fake_tutor = FakeTutor()
    with build_client(monkeypatch, tutor=fake_tutor, security_manager=build_security_manager(tmp_path)) as client:
        response = client.post(
            "/api/chat",
            headers={
                "x-user-id": "spoofed-user",
                "x-forwarded-for": "203.0.113.10",
                "user-agent": "QuantumTutorTest/1.0",
            },
            json={
                "message": "Explica la dualidad onda particula",
                "history": [],
                "user_id": "payload-user",
            },
        )

    assert response.status_code == 200
    routed_user_id = fake_tutor.calls[0]["kwargs"]["user_id"]
    assert routed_user_id.startswith("ip:")
    assert "spoofed-user" not in routed_user_id
    assert "payload-user" not in routed_user_id
    assert "203.0.113.10" not in routed_user_id


def test_chat_uses_authenticated_user_from_trusted_proxy(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_TRUST_PROXY_HEADERS", "true")
    monkeypatch.setenv("QT_TRUSTED_PROXY_RANGES", "testclient")
    fake_tutor = FakeTutor()
    security_manager = build_security_manager(tmp_path)

    with build_client(monkeypatch, tutor=fake_tutor, security_manager=security_manager) as client:
        response = client.post(
            "/api/chat",
            headers={
                "x-authenticated-user": "student@example.com",
                "x-forwarded-for": "203.0.113.11",
                "user-agent": "QuantumTutorTest/1.0",
            },
            json={
                "message": "Explica el oscilador armonico",
                "history": [],
                "user_id": "payload-user",
            },
        )

    assert response.status_code == 200
    assert fake_tutor.calls[0]["kwargs"]["user_id"] == "user:student@example.com"


def test_chat_returns_internal_error_when_core_fails(monkeypatch):
    with build_client(monkeypatch, tutor=FailingTutor()) as client:
        response = client.post("/api/chat", json={"message": "Explícame el espín", "history": []})

    assert response.status_code == 500
    data = response.json()
    assert data["error_code"] == "INTERNAL_CORE_ERROR"
    assert "request_id" in data


def test_chat_returns_core_not_initialized_when_missing(monkeypatch):
    monkeypatch.setattr(api, "tutor", None)
    monkeypatch.setattr(api, "analytics", FakeAnalytics())
    monkeypatch.setattr(api, "vision_parser", FakeVisionParser())

    with TestClient(api.app) as client:
        response = client.post("/api/chat", json={"message": "Explícame el espín", "history": []})

    assert response.status_code == 500
    data = response.json()
    assert data["error_code"] == "CORE_NOT_INITIALIZED"


def test_chat_returns_429_and_retry_after_when_quota_guard_trips(monkeypatch):
    with build_client(monkeypatch, tutor=RateLimitedTutor()) as client:
        response = client.post("/api/chat", json={"message": "Explica el espin", "history": []})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "4"
    data = response.json()
    assert data["error_code"] == "RATE_LIMITED"
    assert data["retry_after_seconds"] == 3.2


def test_chat_returns_429_and_retry_after_when_backpressure_trips(monkeypatch):
    with build_client(monkeypatch, tutor=BackpressureTutor()) as client:
        response = client.post("/api/chat", json={"message": "Analiza la ecuacion de Schrodinger", "history": []})

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "3"
    data = response.json()
    assert data["error_code"] == "BACKPRESSURE"
    assert data["retry_after_seconds"] == 2.1


def test_chat_edge_rate_limit_returns_429_before_core(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_EDGE_CHAT_CAPACITY", "1")
    monkeypatch.setenv("QT_EDGE_CHAT_REFILL_TOKENS", "1")
    monkeypatch.setenv("QT_EDGE_CHAT_REFILL_SECONDS", "3600")
    fake_tutor = FakeTutor()
    security_manager = build_security_manager(tmp_path)

    with build_client(monkeypatch, tutor=fake_tutor, security_manager=security_manager) as client:
        first = client.post("/api/chat", json={"message": "Primera consulta", "history": []})
        second = client.post("/api/chat", json={"message": "Segunda consulta", "history": []})

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.json()["error_code"] == "EDGE_RATE_LIMITED"
    assert "Retry-After" in second.headers
    assert len(fake_tutor.calls) == 1


def test_chat_temporarily_blocks_origin_after_repeated_edge_abuse(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_EDGE_CHAT_CAPACITY", "1")
    monkeypatch.setenv("QT_EDGE_CHAT_REFILL_TOKENS", "1")
    monkeypatch.setenv("QT_EDGE_CHAT_REFILL_SECONDS", "3600")
    monkeypatch.setenv("QT_ABUSE_BLOCK_THRESHOLD", "10")
    fake_tutor = FakeTutor()
    security_manager = build_security_manager(tmp_path)

    with build_client(monkeypatch, tutor=fake_tutor, security_manager=security_manager) as client:
        first = client.post("/api/chat", json={"message": "Primera consulta", "history": []})
        second = client.post("/api/chat", json={"message": "Segunda consulta", "history": []})
        third = client.post("/api/chat", json={"message": "Tercera consulta", "history": []})

    assert first.status_code == 200
    assert second.status_code == 429
    assert third.status_code == 403
    assert third.json()["error_code"] == "TEMPORARILY_BLOCKED"
    assert "Retry-After" in third.headers
    assert len(fake_tutor.calls) == 1


def test_chat_error_reuses_gateway_request_id(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_EDGE_CHAT_CAPACITY", "1")
    monkeypatch.setenv("QT_EDGE_CHAT_REFILL_TOKENS", "1")
    monkeypatch.setenv("QT_EDGE_CHAT_REFILL_SECONDS", "3600")
    fake_tutor = FakeTutor()
    security_manager = build_security_manager(tmp_path)

    with build_client(monkeypatch, tutor=fake_tutor, security_manager=security_manager) as client:
        client.post("/api/chat", json={"message": "Primera consulta", "history": []})
        response = client.post(
            "/api/chat",
            json={"message": "Segunda consulta", "history": []},
            headers={"x-request-id": "edge-req-123"},
        )

    assert response.status_code == 429
    assert response.json()["request_id"] == "edge-req-123"


def test_chat_rejects_excessive_history_before_core(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_API_MAX_HISTORY_MESSAGES", "1")
    fake_tutor = FakeTutor()
    security_manager = build_security_manager(tmp_path)

    with build_client(monkeypatch, tutor=fake_tutor, security_manager=security_manager) as client:
        response = client.post(
            "/api/chat",
            json={
                "message": "Explica el espin",
                "history": [
                    {"role": "user", "content": "hola"},
                    {"role": "assistant", "content": "respuesta previa"},
                ],
            },
        )

    assert response.status_code == 400
    assert response.json()["error_code"] == "HISTORY_TOO_LONG"
    assert fake_tutor.calls == []


def test_vision_endpoint_builds_prompt(monkeypatch):
    with build_client(monkeypatch) as client:
        response = client.post(
            "/api/vision",
            files={"file": ("derivacion.png", b"fake-image-bytes", "image/png")},
        )

    assert response.status_code == 200
    data = response.json()
    assert len(data["steps"]) == 2
    assert "Paso 1" in data["vision_prompt"]
    assert "ERROR DETECTADO" in data["vision_prompt"]


def test_vision_rejects_unsupported_media_type(monkeypatch, tmp_path):
    with build_client(monkeypatch, security_manager=build_security_manager(tmp_path)) as client:
        response = client.post(
            "/api/vision",
            files={"file": ("notes.txt", b"not-an-image", "text/plain")},
        )

    assert response.status_code == 415
    assert response.json()["error_code"] == "UNSUPPORTED_MEDIA_TYPE"


def test_vision_rejects_oversized_upload(monkeypatch, tmp_path):
    monkeypatch.setenv("QT_VISION_MAX_UPLOAD_BYTES", "4")
    security_manager = build_security_manager(tmp_path)

    with build_client(monkeypatch, security_manager=security_manager) as client:
        response = client.post(
            "/api/vision",
            files={"file": ("derivacion.png", b"12345", "image/png")},
        )

    assert response.status_code == 413
    assert response.json()["error_code"] == "IMAGE_TOO_LARGE"


def test_cors_settings_default_to_local_origins(monkeypatch):
    monkeypatch.delenv("QUANTUM_TUTOR_CORS_ORIGINS", raising=False)
    monkeypatch.delenv("CORS_ALLOWED_ORIGINS", raising=False)

    settings = api._cors_settings()

    assert "http://127.0.0.1:8501" in settings["allow_origins"]
    assert settings["allow_credentials"] is True


def test_cors_settings_wildcard_disables_credentials(monkeypatch):
    monkeypatch.setenv("QUANTUM_TUTOR_CORS_ORIGINS", "*")

    settings = api._cors_settings()

    assert settings["allow_origins"] == ["*"]
    assert settings["allow_credentials"] is False
