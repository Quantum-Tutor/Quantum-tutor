from rag_engine import RAGConnector
from galindo_page_map import resolve_galindo_reference


def _build_test_rag(monkeypatch, vector_store, image_pages):
    monkeypatch.setattr(RAGConnector, "encoder", property(lambda self: None))
    monkeypatch.setattr(RAGConnector, "_initialize_store", lambda self: setattr(self, "vector_store", []))
    monkeypatch.setattr(
        RAGConnector,
        "_scan_available_images",
        lambda self: {"galindo": set(), "cohen": set(image_pages), "sakurai": set()},
    )

    rag = RAGConnector()
    rag.vector_store = vector_store
    return rag


def test_visual_query_prioritizes_real_well_content_over_reader_guides(monkeypatch):
    rag = _build_test_rag(
        monkeypatch,
        [
            {
                "id": "reader-guide",
                "title": "Pagina C_182 COMPLEMENTS OF CHAPTER II, READER'S GUIDE",
                "text": "GII: AN APPLICATION OF THE PROPERTIES OF THE TENSOR PRODUCT: THE TWO-DIMENSIONAL INFINITE WELL.",
                "page_number": 182,
                "embedding": None,
                "char_count": 110,
                "has_equations": False,
            },
            {
                "id": "well-content",
                "title": "Pagina C_382 Bound states in a potential well of arbitrary shape",
                "text": (
                    "In complement HI, we studied, for a special case "
                    "(finite or infinite square well), the bound states of a particle in a potential well."
                ),
                "page_number": 382,
                "embedding": None,
                "char_count": 160,
                "has_equations": False,
            },
        ],
        image_pages={182, 382},
    )

    result = rag.query_with_images("imagenes del pozo infinito", k=1)

    assert result["image_pages"] == ["cohen_page_382"]
    assert "reader's guide" not in result["context"].lower()


def test_visual_query_suppresses_administrative_image_refs_without_direct_support(monkeypatch):
    rag = _build_test_rag(
        monkeypatch,
        [
            {
                "id": "reader-guide",
                "title": "Pagina C_182 COMPLEMENTS OF CHAPTER II, READER'S GUIDE",
                "text": "GII: AN APPLICATION OF THE PROPERTIES OF THE TENSOR PRODUCT: THE TWO-DIMENSIONAL INFINITE WELL.",
                "page_number": 182,
                "embedding": None,
                "char_count": 110,
                "has_equations": False,
            }
        ],
        image_pages={182},
    )

    result = rag.query_with_images("imagenes del pozo infinito", k=1)

    assert result["image_pages"] == []


def test_visual_query_prefers_explicit_infinite_square_well_pages_over_related_square_well_hits(monkeypatch):
    rag = _build_test_rag(
        monkeypatch,
        [
            {
                "id": "finite-well",
                "title": "Pagina C_94 Bound states: square well potential",
                "text": "Square well potential of finite depth with matching conditions at the boundaries.",
                "page_number": 94,
                "embedding": None,
                "char_count": 120,
                "has_equations": False,
            },
            {
                "id": "exercise",
                "title": "Pagina C_108 Exercises",
                "text": "Interpret physically a square well centered at x = 0 and discuss the bound state.",
                "page_number": 108,
                "embedding": None,
                "char_count": 110,
                "has_equations": False,
            },
            {
                "id": "explicit-infinite-well",
                "title": "Pagina C_382 Bound states in a potential well of arbitrary shape",
                "text": (
                    "For a special case, the infinite square well (particle in a box), "
                    "the bound states follow from the one-dimensional infinite well analysis."
                ),
                "page_number": 382,
                "embedding": None,
                "char_count": 165,
                "has_equations": False,
            },
        ],
        image_pages={94, 108, 382},
    )

    result = rag.query_with_images("imagenes del pozo infinito", k=3)

    assert result["image_pages"] == ["cohen_page_382"]
    assert "pagina 94" not in result["context"].lower()
    assert "pagina 108" not in result["context"].lower()


def test_visual_query_infers_page_number_from_legacy_galindo_titles(monkeypatch):
    resolved_ref = resolve_galindo_reference(display_page=140)
    monkeypatch.setattr(RAGConnector, "encoder", property(lambda self: None))
    monkeypatch.setattr(RAGConnector, "_initialize_store", lambda self: setattr(self, "vector_store", []))
    monkeypatch.setattr(
        RAGConnector,
        "_scan_available_images",
        lambda self: {"galindo": {resolved_ref["asset_page"]}, "cohen": set(), "sakurai": set()},
    )

    rag = RAGConnector()
    rag.vector_store = [
        {
            "id": "legacy-galindo",
            "title": (
                "140 4. One-Dimensional Problems the normalizable wave functions "
                "and the energies for this infinite square well are ..."
            ),
            "text": (
                "The infinite square well has discrete bound states and the "
                "wave functions vanish at the impenetrable walls."
            ),
            "page_number": None,
            "embedding": None,
            "char_count": 155,
            "has_equations": False,
        }
    ]

    result = rag.query_with_images("imagenes del pozo infinito", k=1)

    assert result["image_pages"] == [140]
    assert "galindo-pascual pagina 140" in result["context"].lower()
    assert f"references/{resolved_ref['image_id']}.png" in result["context"].lower()
