import json
from pathlib import Path

from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from quantum_tutor_paths import OCR_BATCH_CHECKPOINT_PATH
from quantum_tutor_runtime import DEFAULT_TEXT_MODEL, RUNTIME_VERSION


BASE_DIR = Path(__file__).resolve().parent


def test_runtime_metadata_matches_config_file():
    config_path = BASE_DIR / "quantum_tutor_config.json"
    config = json.loads(config_path.read_text(encoding="utf-8"))

    assert config["system_metadata"]["version"] == RUNTIME_VERSION
    assert config["llm_config"]["model"] == DEFAULT_TEXT_MODEL
    assert config["evaluation_protocol"]["output"]["report_path"].startswith("outputs/")
    assert config["evaluation_protocol"]["output"]["dashboard_path"].startswith("outputs/")
    assert OCR_BATCH_CHECKPOINT_PATH.relative_to(BASE_DIR).as_posix().startswith("outputs/")


def test_orchestrator_reports_canonical_runtime_version():
    orch = QuantumTutorOrchestrator(base_dir=BASE_DIR)

    assert orch.version == RUNTIME_VERSION
    assert orch.config["version"] == RUNTIME_VERSION
    assert orch.model_name == DEFAULT_TEXT_MODEL
