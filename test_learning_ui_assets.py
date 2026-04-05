from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def test_static_web_includes_learning_journey_panel():
    html = (BASE_DIR / "static_web" / "index.html").read_text(encoding="utf-8")

    assert 'id="learning-level"' in html
    assert 'id="learning-points"' in html
    assert 'id="learning-next-node"' in html
    assert 'id="learning-next-milestone"' in html
    assert 'id="learning-diagnostic-btn"' in html


def test_static_web_app_calls_learning_endpoints():
    js = (BASE_DIR / "static_web" / "app.js").read_text(encoding="utf-8")

    assert "/api/diagnostico-inicial" in js
    assert "/api/evaluar-respuesta" in js
    assert "/api/ruta-personalizada" in js
    assert "refreshLearningJourney" in js
    assert "startLearningDiagnostic" in js
    assert "submitLearningDiagnostic" in js


def test_streamlit_app_exposes_admin_dashboard():
    app_py = (BASE_DIR / "app_quantum_tutor.py").read_text(encoding="utf-8")

    assert "Admin Dashboard" in app_py
    assert "build_dashboard_view" in app_py
    assert "_render_learning_intelligence_dashboard" in app_py
