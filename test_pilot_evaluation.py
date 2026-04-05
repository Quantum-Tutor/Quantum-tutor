import pytest
from fastapi.testclient import TestClient
import json

from api_quantum_tutor import app
from external_evaluation import pilot_db

client = TestClient(app)

def test_external_evaluation_creates_pilot_record():
    with TestClient(app) as client:
        # Mocking evaluation in LLM evaluator if necessary or just asserting endpoint handles it:
        res = client.post(
            "/api/external-evaluation",
            json={
                "user_id": "student-test-pilot",
                "test_type": "pretest",
                "question_id": "pre_q1",
                "answer": "La función angular de la matriz hermítica"
            },
            headers={"X-User-Role": "student"}
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "success"
        assert "score" in data
        assert "justification" in data


def test_pilot_results_requires_admin():
    with TestClient(app) as client:
        # Petición como student (debería denegar)
        res_fail = client.get("/api/pilot-results", headers={"X-User-Role": "student"})
        assert res_fail.status_code == 403

        # Petición como admin
        res_ok = client.get("/api/pilot-results", headers={"X-User-Role": "admin"})
        assert res_ok.status_code == 200
        data = res_ok.json()
        assert "mean_pretest" in data
        assert "correlation_internal_external" in data

