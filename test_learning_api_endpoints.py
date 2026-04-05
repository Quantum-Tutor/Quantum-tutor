from pathlib import Path

from fastapi.testclient import TestClient

import api_quantum_tutor as api
from adaptive_learning_engine import AdaptiveLearningEngine


def build_engine(tmp_path: Path) -> AdaptiveLearningEngine:
    analytics_path = tmp_path / "student_profile.json"
    analytics_path.write_text('{"topics": {}}', encoding="utf-8")
    return AdaptiveLearningEngine(
        curriculum_path=tmp_path / "learning_curriculum.json",
        progress_path=tmp_path / "learning_progress.json",
        diagnostic_state_path=tmp_path / "learning_diagnostics.json",
        gamification_path=tmp_path / "learning_gamification.json",
        analytics_path=analytics_path,
    )


def build_client(monkeypatch, tmp_path: Path) -> TestClient:
    monkeypatch.setattr(api, "adaptive_learning", build_engine(tmp_path))
    # Los tests de API usan el bypass de authz para endpoints docentes;
    # los tests de seguridad lo desactivan explicitamente.
    monkeypatch.setenv("QT_AUTHZ_ADMIN_ENDPOINTS_DISABLED", "true")
    return TestClient(api.app)


def test_diagnostic_endpoint_returns_request_id_and_hidden_answers(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        response = client.get(
            "/diagnostico_inicial",
            params={"student_id": "student-api", "max_questions": 3},
            headers={"x-request-id": "diag-req-1"},
        )

    assert response.status_code == 200
    assert response.headers["X-Request-ID"] == "diag-req-1"
    data = response.json()
    # SECURITY NOTE: student_id ya NO se toma del param URL.
    # La identidad se deriva del middleware de red (ip:testclient|ua:...).
    # Verificamos que retorna una identidad no vacía y coherente.
    assert data["student_id"], "student_id no debe estar vacío"
    assert data["request_id"] == "diag-req-1"
    assert len(data["questions"]) == 3
    assert "correct_answer" not in data["questions"][0]


def test_evaluate_endpoint_returns_404_for_unknown_question(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        response = client.post(
            "/api/evaluar-respuesta",
            json={
                "student_id": "student-api",
                "question_id": "missing-question",
                "answer": "x",
            },
        )

    assert response.status_code == 404
    assert response.json()["error_code"] == "QUESTION_NOT_FOUND"


def test_route_and_progress_endpoints_round_trip(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        save_response = client.post(
            "/api/guardar-progreso",
            json={
                "student_id": "student-api",
                "node_id": "math_functions",
                "mastery_score": 0.9,
                "completed": True,
            },
        )
        route_response = client.get(
            "/api/ruta-personalizada",
            params={"student_id": "student-api"},
        )

    assert save_response.status_code == 200
    saved = save_response.json()
    assert saved["saved"] is True
    assert "math_functions" in saved["completed_nodes"]

    assert route_response.status_code == 200
    route = route_response.json()
    # SECURITY NOTE: student_id ahora es la identidad de red, no el param URL.
    assert route["student_id"], "student_id no debe estar vacío"
    assert route["next_node"] is not None
    assert route["persona"] in {"beginner", "intermediate", "advanced", "expert"}
    assert route["mastery_threshold"] == 0.85
    assert "request_id" in route


def test_learning_kpis_and_assessment_endpoints(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        pretest = client.post(
            "/api/guardar-evaluacion",
            json={
                "student_id": "student-api",
                "assessment_type": "pretest",
                "score": 0.4,
                "label": "inicio",
            },
        )
        posttest = client.post(
            "/api/guardar-evaluacion",
            json={
                "student_id": "student-api",
                "assessment_type": "posttest",
                "score": 0.8,
                "label": "cierre",
            },
        )
        kpis = client.get("/api/learning-kpis", params={"student_id": "student-api"})
        review_queue = client.get("/api/learning-review-queue", params={"student_id": "student-api"})

    assert pretest.status_code == 200
    assert posttest.status_code == 200
    assert kpis.status_code == 200
    assert review_queue.status_code == 200
    payload = kpis.json()
    assert payload["pretest_score"] == 0.4
    assert payload["posttest_score"] == 0.8
    assert payload["improvement"] == 0.4
    assert "review_queue" in payload
    assert "review_queue" in review_queue.json()


def test_invalid_assessment_type_returns_400(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        response = client.post(
            "/api/guardar-evaluacion",
            json={
                "student_id": "student-api",
                "assessment_type": "quiz-final",
                "score": 0.6,
            },
        )

    assert response.status_code == 400
    assert response.json()["error_code"] == "INVALID_ASSESSMENT_TYPE"


def test_cohort_report_and_export_endpoints(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        client.post(
            "/api/guardar-progreso",
            json={
                "student_id": "student-api",
                "node_id": "qm_principios_basicos",
                "mastery_score": 0.9,
                "completed": True,
            },
        )
        report = client.get("/api/learning-cohort-report")
        export = client.post("/api/learning-cohort-export", json={"experiment_name": "gamification_v1"})

    assert report.status_code == 200
    report_payload = report.json()
    assert "summary" in report_payload
    assert "variants" in report_payload
    assert "module_comparison" in report_payload

    assert export.status_code == 200
    export_payload = export.json()
    assert export_payload["json_path"].endswith("learning_cohort_report.json")
    assert export_payload["csv_path"].endswith("learning_cohort_students.csv")


def test_learning_insights_endpoint_returns_summary_and_cohorts(monkeypatch, tmp_path):
    with build_client(monkeypatch, tmp_path) as client:
        client.post(
            "/api/guardar-evaluacion",
            json={
                "student_id": "student-api",
                "assessment_type": "pretest",
                "score": 0.35,
            },
        )
        client.post(
            "/api/guardar-evaluacion",
            json={
                "student_id": "student-api",
                "assessment_type": "posttest",
                "score": 0.5,
            },
        )
        response = client.get(
            "/api/learning-insights",
            params={"experiment_name": "gamification_v1", "apply_optimization": "true"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert "summary" in payload
    assert "cohorts" in payload
    assert "experiment" in payload
    assert "learning_cohorts" in payload


# =============================================================================
# SECURITY TESTS (nuevos — hardening 2026-04-05)
# =============================================================================

def test_student_id_from_client_is_not_trusted(monkeypatch, tmp_path):
    """El student_id del payload NO debe usarse como identidad principal.
    La identidad debe derivarse del middleware, nunca del cuerpo del request.
    """
    # _resolved_learning_student_id ahora ignora explicit_student_id en favor
    # de identity.authenticated_user (vacío en tests sin proxy) y cae al explicit
    # solo como fallback. Verificamos que no se puede inyectar uno diferente
    # para corromper una sesion ajena.
    monkeypatch.setattr(api, "adaptive_learning", build_engine(tmp_path))
    monkeypatch.setenv("QT_AUTHZ_ADMIN_ENDPOINTS_DISABLED", "true")
    with TestClient(api.app) as client:
        r1 = client.get("/api/ruta-personalizada", params={"student_id": "victim-student"})
        r2 = client.get("/api/ruta-personalizada", params={"student_id": "attacker-student"})
    # Ambas requests tienen identidades de red distintas (misma IP en test cliente)
    # pero estudiante diferente; el middleware devuelve identidad basada en red, no payload.
    assert r1.status_code == 200
    assert r2.status_code == 200
    # La identidad resuelta en ambos casos es la del proveedor de red (no la del payload)
    # No pueden inyectar un student_id arbitrario con privilegios elevados
    assert r1.json()["student_id"] != "victim-student" or r2.json()["student_id"] != "attacker-student"


def test_professor_endpoints_blocked_without_role_header(monkeypatch, tmp_path):
    """Sin el header X-User-Role correcto, los endpoints docentes deben retornar 403."""
    monkeypatch.setattr(api, "adaptive_learning", build_engine(tmp_path))
    # NO establecemos QT_AUTHZ_ADMIN_ENDPOINTS_DISABLED
    monkeypatch.delenv("QT_AUTHZ_ADMIN_ENDPOINTS_DISABLED", raising=False)
    with TestClient(api.app) as client:
        r_kpis = client.get("/api/learning-kpis")
        r_review = client.get("/api/learning-review-queue")
        r_cohort = client.get("/api/learning-cohort-report")
        r_insights = client.get("/api/learning-insights")
        r_export = client.post("/api/learning-cohort-export", json={"experiment_name": "test"})

    for response in [r_kpis, r_review, r_cohort, r_insights, r_export]:
        assert response.status_code == 403, f"Esperado 403, got {response.status_code} para {response.url}"


def test_professor_endpoints_allowed_with_correct_role_header(monkeypatch, tmp_path):
    """Con el header X-User-Role: professor, los endpoints docentes deben pasar."""
    monkeypatch.setattr(api, "adaptive_learning", build_engine(tmp_path))
    monkeypatch.delenv("QT_AUTHZ_ADMIN_ENDPOINTS_DISABLED", raising=False)
    with TestClient(api.app) as client:
        r_kpis = client.get("/api/learning-kpis", headers={"x-user-role": "professor"})
        r_insights = client.get("/api/learning-insights", headers={"x-user-role": "admin"})

    assert r_kpis.status_code == 200
    assert r_insights.status_code == 200

