from __future__ import annotations

import json
import os
import pickle
import shutil
import uuid
from pathlib import Path
from typing import Any


BASE_DIR = Path(__file__).resolve().parent

OUTPUTS_DIR = BASE_DIR / "outputs"
OUTPUT_REPORTS_DIR = OUTPUTS_DIR / "reports"
OUTPUT_CHECKPOINTS_DIR = OUTPUTS_DIR / "checkpoints"
OUTPUT_CACHE_DIR = OUTPUTS_DIR / "cache"
OUTPUT_LOGS_DIR = OUTPUTS_DIR / "logs"
OUTPUT_STATE_DIR = OUTPUTS_DIR / "state"

QST_RESULTS_PATH = OUTPUTS_DIR / "qst_results.json"
QST_DASHBOARD_PATH = OUTPUTS_DIR / "evaluation_dashboard.html"
SYSTEM_STATUS_PATH = OUTPUTS_DIR / "system_status.json"

CASE_B_REPORT_PATH = OUTPUT_REPORTS_DIR / "case_b_simulation_results.json"
SIMULATION_OPTIMIZATION_PATH = OUTPUT_REPORTS_DIR / "simulation_optimization_report.json"
OCR_BATCH_CHECKPOINT_PATH = OUTPUT_CHECKPOINTS_DIR / "ocr_batch_checkpoint.json"

USERS_DB_PATH = OUTPUT_STATE_DIR / "users.json"
AUTH_SESSIONS_PATH = OUTPUT_STATE_DIR / "sessions.json"
AUTH_RATE_LIMITS_PATH = OUTPUT_STATE_DIR / "rate_limits.json"
STUDENT_PROFILE_PATH = OUTPUT_STATE_DIR / "student_profile.json"
API_USAGE_BUCKETS_PATH = OUTPUT_STATE_DIR / "api_usage_buckets.json"
API_EDGE_RATE_LIMITS_PATH = OUTPUT_STATE_DIR / "api_edge_rate_limits.json"
API_ABUSE_STATE_PATH = OUTPUT_STATE_DIR / "api_abuse_state.json"
PROVIDER_CIRCUIT_BREAKERS_PATH = OUTPUT_STATE_DIR / "provider_circuit_breakers.json"
LEARNING_CURRICULUM_PATH = OUTPUT_STATE_DIR / "learning_curriculum.json"
LEARNING_PROGRESS_PATH = OUTPUT_STATE_DIR / "learning_progress.json"
LEARNING_DIAGNOSTIC_STATE_PATH = OUTPUT_STATE_DIR / "learning_diagnostics.json"
LEARNING_GAMIFICATION_PATH = OUTPUT_STATE_DIR / "learning_gamification.json"
PILOT_RESULTS_PATH = OUTPUT_STATE_DIR / "pilot_evaluations.json"
LEARNING_COHORT_REPORT_PATH = OUTPUT_REPORTS_DIR / "learning_cohort_report.json"
LEARNING_COHORT_STUDENTS_CSV_PATH = OUTPUT_REPORTS_DIR / "learning_cohort_students.csv"

SEMANTIC_CACHE_PATH = OUTPUT_CACHE_DIR / "semantic_cache.json"
LLM_RESPONSE_CACHE_PATH = OUTPUT_CACHE_DIR / "llm_response_cache.json"
RAG_INDEX_CACHE_PATH = OUTPUT_CACHE_DIR / "rag_index.pkl"

RUNTIME_LOG_PATH = OUTPUT_LOGS_DIR / "quantum_tutor_system.log"
CRASH_LOG_PATH = OUTPUT_LOGS_DIR / "crash.log"
SECURITY_EVENTS_LOG_PATH = OUTPUT_LOGS_DIR / "security_events.jsonl"


def ensure_output_dirs() -> None:
    OUTPUTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_CHECKPOINTS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_LOGS_DIR.mkdir(parents=True, exist_ok=True)
    OUTPUT_STATE_DIR.mkdir(parents=True, exist_ok=True)


def resolve_runtime_path(path: Path, *legacy_names: str) -> Path:
    ensure_output_dirs()
    if path.exists():
        return path

    for legacy_name in legacy_names:
        legacy_path = BASE_DIR / legacy_name
        if not legacy_path.exists():
            continue
        try:
            shutil.copy2(legacy_path, path)
        except OSError:
            try:
                path.write_bytes(legacy_path.read_bytes())
            except OSError:
                return legacy_path
        return path

    return path


def write_json_atomic(path: Path, data: Any, **json_kwargs: Any) -> None:
    ensure_output_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    # BUGFIX: nombre de .tmp único por operación para evitar colisiones bajo concurrencia.
    tmp_path = path.with_name(path.stem + f"_{uuid.uuid4().hex[:12]}" + path.suffix + ".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as f:
            json.dump(data, f, **json_kwargs)
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def write_text_atomic(path: Path, text: str, encoding: str = "utf-8") -> None:
    ensure_output_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.stem + f"_{uuid.uuid4().hex[:12]}" + path.suffix + ".tmp")
    try:
        with tmp_path.open("w", encoding=encoding) as f:
            f.write(text)
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise


def write_pickle_atomic(path: Path, data: Any) -> None:
    ensure_output_dirs()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_name(path.stem + f"_{uuid.uuid4().hex[:12]}" + path.suffix + ".tmp")
    try:
        with tmp_path.open("wb") as f:
            pickle.dump(data, f)
        os.replace(tmp_path, path)
    except Exception:
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)
        raise
