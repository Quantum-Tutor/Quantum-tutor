from galindo_page_map import resolve_galindo_reference
from rag_engine import RAGConnector


def _build_rag(monkeypatch):
    resolved_ref = resolve_galindo_reference(ocr_page=145)
    monkeypatch.setattr(RAGConnector, "encoder", property(lambda self: None))
    monkeypatch.setattr(RAGConnector, "_initialize_store", lambda self: None)
    monkeypatch.setattr(
        RAGConnector,
        "_scan_available_images",
        lambda self: {"galindo": {resolved_ref["asset_page"]}, "cohen": set(), "sakurai": set()},
    )
    return RAGConnector()


def test_galindo_ingestion_filters_noise_and_indexes_sections(monkeypatch):
    rag = _build_rag(monkeypatch)
    content = """
## Pagina 0
WUOLAH reservados todos los derechos universidad de granada galindo p pascual.

## Pagina 101
La ecuacion de Schrodinger introduce la dinamica cuantica mediante el Hamiltoniano H y
la funcion de onda psi. Este bloque conserva el vocabulario fisico relevante y describe
como evoluciona el sistema cuando el estado depende del tiempo y de los observables.

## Pagina 145
El pozo de potencial infinito cuantico impone condiciones de frontera estrictas. La
funcion de onda del sistema produce niveles de energia discretos y permite estudiar el
primer estado excitado, la cuantizacion y la forma de los autovalores del Hamiltoniano.
"""

    rag._ingest_content(content, source="Galindo-Pascual")
    stats = rag.get_stats()

    assert stats["total_chunks"] == 2
    assert "Pagina 101" in stats["sections"]
    assert "Pagina 145" in stats["sections"]
    assert all("WUOLAH" not in chunk["text"] for chunk in rag.vector_store)


def test_galindo_query_returns_matching_context(monkeypatch):
    rag = _build_rag(monkeypatch)
    content = """
## Pagina 101
La ecuacion de Schrodinger introduce la dinamica cuantica mediante el Hamiltoniano H y
la funcion de onda psi. Este bloque conserva el vocabulario fisico relevante y describe
como evoluciona el sistema cuando el estado depende del tiempo y de los observables.

## Pagina 145
El pozo de potencial infinito cuantico impone condiciones de frontera estrictas. La
funcion de onda del sistema produce niveles de energia discretos y permite estudiar el
primer estado excitado, la cuantizacion y la forma de los autovalores del Hamiltoniano.
"""

    rag._ingest_content(content, source="Galindo-Pascual")
    result = rag.query("Pozo de potencial infinito", k=1)

    expected_page = resolve_galindo_reference(ocr_page=145)["display_page"]

    assert "Galindo-Pascual" in result
    assert "pozo de potencial infinito" in result.lower()
    if expected_page > 0:
        assert f"Pagina {expected_page}" in result
