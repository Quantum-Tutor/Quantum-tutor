from pathlib import Path

from rag_engine import RAGConnector


def test_rag_connector_initializes_with_explicit_config(monkeypatch):
    def fake_initialize_store(self):
        self.vector_store = []

    def fake_scan_images(self):
        return {"galindo": set(), "cohen": set(), "sakurai": set()}

    monkeypatch.setattr(RAGConnector, "_initialize_store", fake_initialize_store)
    monkeypatch.setattr(RAGConnector, "_scan_available_images", fake_scan_images)

    base_dir = Path(__file__).resolve().parent
    config_path = str((base_dir / "quantum_tutor_config.json")).replace("/", "\\")

    rag = RAGConnector(config_path=config_path, base_dir=base_dir)

    assert rag.config_path.name == "quantum_tutor_config.json"
    assert rag.available_images == {"galindo": set(), "cohen": set(), "sakurai": set()}
    assert rag.vector_store == []
