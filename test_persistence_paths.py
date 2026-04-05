from pathlib import Path

from learning_analytics import LearningAnalytics
from quantum_tutor_paths import (
    AUTH_RATE_LIMITS_PATH,
    AUTH_SESSIONS_PATH,
    BASE_DIR,
    CRASH_LOG_PATH,
    RAG_INDEX_CACHE_PATH,
    RUNTIME_LOG_PATH,
    SEMANTIC_CACHE_PATH,
    STUDENT_PROFILE_PATH,
    USERS_DB_PATH,
)
from rag_engine import RAGConnector
from semantic_cache import SemanticCache


def test_runtime_persistence_paths_live_under_outputs():
    paths = [
        USERS_DB_PATH,
        AUTH_SESSIONS_PATH,
        AUTH_RATE_LIMITS_PATH,
        STUDENT_PROFILE_PATH,
        SEMANTIC_CACHE_PATH,
        RAG_INDEX_CACHE_PATH,
        RUNTIME_LOG_PATH,
        CRASH_LOG_PATH,
    ]

    for path in paths:
        assert path.relative_to(BASE_DIR).as_posix().startswith("outputs/")


def test_learning_analytics_defaults_to_outputs_state_path():
    analytics = LearningAnalytics()

    assert analytics.db_path == STUDENT_PROFILE_PATH


def test_semantic_cache_defaults_to_outputs_cache_path():
    cache = SemanticCache()

    assert cache.cache_file == SEMANTIC_CACHE_PATH


def test_rag_connector_uses_outputs_cache_under_repo_root(monkeypatch):
    def fake_initialize_store(self):
        self.vector_store = []

    def fake_scan_images(self):
        return {"galindo": set(), "cohen": set(), "sakurai": set()}

    monkeypatch.setattr(RAGConnector, "_initialize_store", fake_initialize_store)
    monkeypatch.setattr(RAGConnector, "_scan_available_images", fake_scan_images)

    rag = RAGConnector(base_dir=BASE_DIR)

    assert rag.index_cache_path == RAG_INDEX_CACHE_PATH


def test_rag_connector_uses_local_outputs_cache_for_custom_base_dir(monkeypatch, tmp_path):
    def fake_initialize_store(self):
        self.vector_store = []

    def fake_scan_images(self):
        return {"galindo": set(), "cohen": set(), "sakurai": set()}

    monkeypatch.setattr(RAGConnector, "_initialize_store", fake_initialize_store)
    monkeypatch.setattr(RAGConnector, "_scan_available_images", fake_scan_images)

    rag = RAGConnector(base_dir=tmp_path)

    assert rag.index_cache_path == Path(tmp_path) / "outputs" / "cache" / "rag_index.pkl"


# =============================================================================
# SECURITY TEST — hardening 2026-04-05 (atomic writes con UUID único)
# =============================================================================

def test_atomic_write_json_produces_unique_tmp_names(tmp_path):
    """Dos escrituras simultáneas a la misma ruta deben usar .tmp distintos.
    Verifica que el nombre del .tmp contiene un UUID hex (no es fijo).
    """
    import threading
    from quantum_tutor_paths import write_json_atomic

    target = tmp_path / "concurrent_test.json"
    tmp_names_seen = []
    lock = threading.Lock()

    original_open = open

    def capturing_open(path, *args, **kwargs):
        path_str = str(path)
        if path_str.endswith(".tmp") and "concurrent_test" in path_str:
            with lock:
                tmp_names_seen.append(path_str)
        return original_open(path, *args, **kwargs)

    import builtins
    original_builtin_open = builtins.open
    builtins.open = capturing_open

    try:
        errors = []

        def write_worker(data):
            try:
                write_json_atomic(target, data)
            except Exception as e:
                with lock:
                    errors.append(str(e))

        t1 = threading.Thread(target=write_worker, args=({"writer": "A", "val": 1},))
        t2 = threading.Thread(target=write_worker, args=({"writer": "B", "val": 2},))
        t1.start()
        t2.start()
        t1.join()
        t2.join()
    finally:
        builtins.open = original_builtin_open

    assert not errors, f"Errores durante escritura concurrente: {errors}"
    assert target.exists(), "El archivo final debe existir"

    # Los nombres de .tmp deben ser distintos entre sí (UUID único por op)
    if len(tmp_names_seen) >= 2:
        assert tmp_names_seen[0] != tmp_names_seen[1], (
            f"Los .tmp deben tener nombres únicos, ambos fueron: {tmp_names_seen[0]}"
        )

    # El archivo final debe ser JSON válido
    import json
    content = json.loads(target.read_text(encoding="utf-8"))
    assert "writer" in content


def test_atomic_write_cleans_up_tmp_on_failure(tmp_path, monkeypatch):
    """Si la escritura falla a mitad de camino, el .tmp debe limpiarse."""
    from quantum_tutor_paths import write_json_atomic
    import json as json_mod

    target = tmp_path / "fail_test.json"

    # Simular error en json.dump
    original_dump = json_mod.dump

    call_count = {"n": 0}

    def failing_dump(*args, **kwargs):
        call_count["n"] += 1
        raise IOError("Simulated write failure")

    monkeypatch.setattr("json.dump", failing_dump)

    import pytest
    with pytest.raises(IOError):
        write_json_atomic(target, {"key": "value"})

    # No debe quedar ningún .tmp huérfano
    tmp_files = list(tmp_path.glob("*.tmp"))
    assert tmp_files == [], f"No deben quedar .tmp huérfanos, encontrados: {tmp_files}"

