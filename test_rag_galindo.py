"""
Test RAG con contenido real de Galindo & Pascual
Alimenta el motor RAG con los chunks reales extraidos del PDF
y ejecuta consultas de prueba para validar la busqueda semantica.
"""
import json
import os
import sys

# Cargar el RAG engine y el pipeline de ingesta
from rag_engine import RAGConnector
from ingest import DocumentIngestionPipeline

def test_real_rag():
    print("\n" + "=" * 72)
    print("  RAG SEARCH TEST — Galindo & Pascual (Contenido Real)")
    print("=" * 72)

    # 1. Ingerir el PDF real
    pdf_path = os.path.join(os.path.dirname(__file__), "books",
                            "wuolah-premium-Galindo-Pascual-Quantum-Mechanics-Vol-I.pdf")

    if not os.path.exists(pdf_path):
        print(f"[ERROR] PDF no encontrado en: {pdf_path}")
        return

    pipeline = DocumentIngestionPipeline()
    content = pipeline.read_document(pdf_path)

    print(f"\n[INFO] Texto extraido: {len(content)} caracteres")

    # 2. Inyectar contenido real al RAG Engine
    rag = RAGConnector()
    rag.vector_store = []  # Limpiar fallback
    rag._ingest_content(content)

    stats = rag.get_stats()
    print(f"[INFO] Vector Store cargado: {stats['total_chunks']} chunks reales")
    print(f"[INFO] Total caracteres indexados: {stats['total_chars']}")

    # 3. Consultas de prueba contra Galindo & Pascual real
    test_queries = [
        "Ecuacion de Schrodinger",
        "Pozo de potencial infinito",
        "Conmutadores y operadores cuanticos",
        "Efecto tunel",
        "Oscilador armonico cuantico",
        "Principio de incertidumbre Heisenberg",
        "Momento angular orbital",
        "Espacio de Hilbert",
        "Autovalores y autovectores",
        "Perturbaciones y teoria de perturbaciones",
    ]

    print(f"\n{'─' * 72}")
    print(f"  Ejecutando {len(test_queries)} consultas contra contenido REAL:")
    print(f"{'─' * 72}")

    results_summary = []

    for q in test_queries:
        result = rag.query(q, k=2)
        # Extraer score del primer resultado
        log_entry = rag.query_log[-1] if rag.query_log else {}
        score = log_entry.get("top_score", 0)
        sections = log_entry.get("sections", [])

        # Mostrar un preview limpio del resultado
        if result:
            # Tomar las primeras lineas utiles (no la metadata)
            lines = result.split("\n")
            text_lines = [l for l in lines if l.strip() and not l.startswith("[Doc:")]
            preview = " ".join(text_lines[:3])[:200]
        else:
            preview = "(sin resultados)"

        status = "HIT" if score > 0.05 else "MISS"

        print(f"\n  [{status}] Q: \"{q}\"")
        print(f"       Score: {score:.4f} | Secciones: {sections[:2]}")
        print(f"       Preview: {preview}...")

        results_summary.append({
            "query": q,
            "score": score,
            "status": status,
            "sections": sections[:2],
        })

    # 4. Resumen final
    hits = sum(1 for r in results_summary if r["status"] == "HIT")
    total = len(results_summary)

    print(f"\n{'=' * 72}")
    print(f"  RESULTADO RAG REAL: {hits}/{total} consultas con HIT")
    print(f"  Hit Rate: {hits/total*100:.0f}%")
    print(f"  Chunks indexados: {stats['total_chunks']} (desde PDF real)")
    print(f"{'=' * 72}\n")

    return results_summary


if __name__ == "__main__":
    test_real_rag()
