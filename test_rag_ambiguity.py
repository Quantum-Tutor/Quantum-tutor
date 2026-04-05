from rag_engine import RAGConnector


def test_ambiguity_boost_prioritizes_introductory_context(monkeypatch):
    monkeypatch.setattr(RAGConnector, "encoder", property(lambda self: None))

    def fake_initialize_store(self):
        self.vector_store = []

    def fake_scan_images(self):
        return {"galindo": set(), "cohen": set(), "sakurai": set()}

    monkeypatch.setattr(RAGConnector, "_initialize_store", fake_initialize_store)
    monkeypatch.setattr(RAGConnector, "_scan_available_images", fake_scan_images)

    rag = RAGConnector()
    rag.vector_store = [
        {
            "id": "intro",
            "title": "Fundamentos de mecánica cuántica",
            "text": "Introduction to the basis and principles of quantum mechanics.",
            "page_number": 1,
            "embedding": None,
        },
        {
            "id": "advanced",
            "title": "Operadores avanzados",
            "text": "Formal development of commutators and spectral decomposition.",
            "page_number": 20,
            "embedding": None,
        },
    ]

    result = rag.query("Hola", k=1)

    assert "Fundamentos" in result or "Introduction" in result
