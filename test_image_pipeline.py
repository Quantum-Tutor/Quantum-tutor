# -*- coding: utf-8 -*-
"""
test_image_pipeline.py — Verificacion del pipeline de imagenes de libro (v5.4)
=============================================================
Verifica que:
1. ReferenceVisualizer escribe en static_web/references (mismo dir que RAGConnector)
2. query_with_images() retorna image_pages correctamente
3. get_page_image() retorna rutas validas dentro de static_web/references
"""

import os
import re
import sys
from pathlib import Path

BASE_DIR = Path(__file__).parent.absolute()
sys.path.insert(0, str(BASE_DIR))

from reference_visualizer import ReferenceVisualizer
from rag_engine import RAGConnector

EXPECTED_REFS_DIR = BASE_DIR / "static_web" / "references"
PDF_PATH = BASE_DIR / "wuolah-premium-Galindo-Pascual-Quantum-Mechanics-Vol-I.pdf"


def test_reference_visualizer_path():
    """Bug #1: ReferenceVisualizer debe escribir en static_web/references."""
    print("\n[TEST 1] ReferenceVisualizer path unificado...")
    viz = ReferenceVisualizer(str(PDF_PATH), base_dir=str(BASE_DIR))
    
    assert viz.output_dir == EXPECTED_REFS_DIR, (
        f"FAIL: output_dir={viz.output_dir}, esperado={EXPECTED_REFS_DIR}"
    )
    print(f"  PASS: output_dir={viz.output_dir}")


def test_reference_visualizer_get_page():
    """Bug #1: La ruta devuelta por get_page_image debe existir dentro de static_web/references."""
    print("\n[TEST 2] get_page_image() devuelve ruta en static_web/references...")
    viz = ReferenceVisualizer(str(PDF_PATH), base_dir=str(BASE_DIR))
    
    # Buscar primera pagina disponible en el directorio
    available = sorted(EXPECTED_REFS_DIR.glob("page_*.png"))
    if not available:
        # Generar pagina de prueba
        img_path_str = viz.get_page_image(24)
    else:
        page_num = int(available[0].stem.replace("page_", ""))
        img_path_str = viz.get_page_image(page_num)
    
    assert img_path_str is not None, "FAIL: get_page_image() devolvio None"
    img_path = Path(img_path_str)
    assert img_path.exists(), f"FAIL: El archivo no existe: {img_path}"
    assert EXPECTED_REFS_DIR in img_path.parents or img_path.parent == EXPECTED_REFS_DIR, (
        f"FAIL: La imagen esta en {img_path.parent}, no en {EXPECTED_REFS_DIR}"
    )
    print(f"  PASS: imagen en {img_path}")


def test_rag_scan_images():
    """Bug #1/#6: RAGConnector escanea imagenes en static_web/references."""
    print("\n[TEST 3] RAGConnector._scan_available_images() escanea static_web/references...")
    rag = RAGConnector(base_dir=str(BASE_DIR))
    
    assert rag.references_dir == EXPECTED_REFS_DIR, (
        f"FAIL: references_dir={rag.references_dir}, esperado={EXPECTED_REFS_DIR}"
    )
    print(f"  PASS: references_dir={rag.references_dir}")
    print(f"  INFO: Imagenes disponibles en RAG: {sorted(rag.available_images)}")

    assert isinstance(rag.available_images, dict), (
        f"FAIL: available_images no es dict: {type(rag.available_images)}"
    )
    assert {"galindo", "cohen", "sakurai"}.issubset(rag.available_images.keys()), (
        f"FAIL: claves inesperadas en available_images: {rag.available_images.keys()}"
    )

    # Verificar que cada fuente mapea a enteros de página
    for source, pages in rag.available_images.items():
        assert isinstance(pages, set), f"FAIL: {source} no es set: {type(pages)}"
        for pg in pages:
            assert isinstance(pg, int), f"FAIL: {source} contiene no-int: {type(pg)} = {pg}"
    print("  PASS: Todas las fuentes indexan paginas enteras por separado")


def test_query_with_images():
    """Bug #2/#3: query_with_images() retorna dict con context e image_pages."""
    print("\n[TEST 4] query_with_images() retorna metadatos de imagenes...")
    rag = RAGConnector(base_dir=str(BASE_DIR))
    
    result = rag.query_with_images("notacion Dirac")
    assert isinstance(result, dict), f"FAIL: resultado no es dict: {type(result)}"
    assert "context" in result, "FAIL: falta 'context' en resultado"
    assert "image_pages" in result, "FAIL: falta 'image_pages' en resultado"
    assert isinstance(result["image_pages"], list), "FAIL: image_pages no es list"
    
    print(f"  PASS: context={len(result['context'])} chars, image_pages={result['image_pages']}")
    
    # Si hay imagenes disponibles, verificar que los identificadores sean validos
    for pg in result["image_pages"]:
        if isinstance(pg, int):
            assert pg > 0, f"FAIL: numero de pagina invalido: {pg}"
            continue

        assert isinstance(pg, str), f"FAIL: image_pages contiene tipo invalido: {type(pg)} = {pg}"
        assert re.match(r"^(cohen_page|sakurai_page)_\d+$", pg), (
            f"FAIL: identificador de pagina invalido: {pg}"
        )
    print("  PASS: Todos los image_pages siguen el contrato vigente del RAG")


def test_no_duplicate_init():
    """Bug #4: RAGConnector no debe llamar _initialize_store() dos veces."""
    import unittest.mock as mock
    print("\n[TEST 5] RAGConnector no duplica _initialize_store()...")
    
    original_init = RAGConnector._initialize_store
    call_count = [0]
    
    def counting_init(self):
        call_count[0] += 1
        original_init(self)
    
    with mock.patch.object(RAGConnector, '_initialize_store', counting_init):
        RAGConnector(base_dir=str(BASE_DIR))
    
    assert call_count[0] == 1, f"FAIL: _initialize_store() llamado {call_count[0]} veces (esperado: 1)"
    print(f"  PASS: _initialize_store() llamado exactamente 1 vez")


if __name__ == "__main__":
    print("=" * 60)
    print("  Test Suite: Image Pipeline v5.4")
    print("=" * 60)
    
    tests = [
        test_reference_visualizer_path,
        test_reference_visualizer_get_page,
        test_rag_scan_images,
        test_query_with_images,
        test_no_duplicate_init,
    ]
    
    passed = 0
    failed = 0
    for test_fn in tests:
        try:
            test_fn()
            passed += 1
        except AssertionError as e:
            print(f"  {e}")
            failed += 1
        except Exception as e:
            print(f"  ERROR inesperado en {test_fn.__name__}: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "=" * 60)
    print(f"  RESULTADO: {passed}/{passed+failed} tests OK, {failed} fallidos")
    print("=" * 60)
    
    sys.exit(0 if failed == 0 else 1)
