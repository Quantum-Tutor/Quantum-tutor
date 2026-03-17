"""
Prueba de Ingesta Real: Galindo & Pascual — Quantum Mechanics I
================================================================
Ejecuta el pipeline de ingesta sobre contenido representativo del
libro "Quantum Mechanics I" (Galindo & Pascual, Springer 1990)
y produce un analisis detallado de fragmentacion para validar que
las ecuaciones de Schrodinger no se cortan entre chunks.
"""

import json
import sys
import os
import re
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from ingest import DocumentIngestionPipeline


class RealIngestionTest:
    """Test de ingesta real sobre material academico de Galindo & Pascual."""

    def __init__(self):
        self.pipeline = DocumentIngestionPipeline()
        self.results = {}

    def load_real_document(self, file_path: str) -> str:
        """Carga un documento Markdown real del filesystem."""
        print(f"\n[REAL] Leyendo documento real: {file_path}")
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        print(f"[REAL] Documento cargado: {len(content)} caracteres, "
              f"{content.count(chr(10))} lineas")
        return content

    def analyze_equation_integrity(self, chunks: list) -> dict:
        """
        Analiza en detalle la integridad de las ecuaciones en los chunks.
        Verifica que ninguna formula LaTeX ha sido cortada entre chunks.
        """
        print("\n[ANALISIS] Verificando integridad de ecuaciones...")

        report = {
            "total_chunks": len(chunks),
            "equations_by_chunk": [],
            "broken_display_equations": [],
            "broken_inline_equations": [],
            "cross_chunk_formulas": [],
        }

        for chunk_data in chunks:
            text = chunk_data["text"]
            meta = chunk_data["metadata"]

            # Contar $ y $$ para verificar paridad
            display_count = text.count("$$")
            inline_dollars = len(re.findall(r'(?<!\$)\$(?!\$)', text))

            display_ok = display_count % 2 == 0
            inline_ok = inline_dollars % 2 == 0

            # Extraer ecuaciones display individuales
            display_eqs = re.findall(r'\$\$(.*?)\$\$', text, re.DOTALL)

            # Verificar ecuaciones clave
            key_formulas = {
                "Schrodinger": r'i\\hbar.*\\partial.*\\psi',
                "Pozo infinito psi": r'\\sqrt.*\\frac.*\\sin',
                "Energia cuantizada": r'E_n.*=.*\\frac.*\\hbar',
                "Conmutador": r'\\hat\{x\}.*\\hat\{p\}',
                "Incertidumbre": r'\\Delta.*\\geq.*\\frac.*\\hbar',
                "Oscilador": r'\\hbar\\omega.*\\hat',
                "Tunel": r'\\sinh.*\\kappa',
                "Normalizacion": r'\\int.*\\infty.*dx.*=.*1',
            }

            formulas_found = []
            for name, pattern in key_formulas.items():
                if re.search(pattern, text):
                    formulas_found.append(name)

            chunk_report = {
                "chunk_id": meta["chunk_index"],
                "section": meta["section_title"],
                "char_count": meta["char_count"],
                "display_equations": len(display_eqs),
                "display_balanced": display_ok,
                "inline_balanced": inline_ok,
                "integrity": "OK" if (display_ok and inline_ok) else "BROKEN",
                "key_formulas": formulas_found,
            }
            report["equations_by_chunk"].append(chunk_report)

            if not display_ok:
                report["broken_display_equations"].append({
                    "chunk": meta["chunk_index"],
                    "section": meta["section_title"],
                    "display_dollar_count": display_count
                })
            if not inline_ok:
                report["broken_inline_equations"].append({
                    "chunk": meta["chunk_index"],
                    "section": meta["section_title"],
                    "inline_dollar_count": inline_dollars
                })

        # Estadisticas
        total_display = sum(c["display_equations"] for c in report["equations_by_chunk"])
        broken_count = len(report["broken_display_equations"]) + len(report["broken_inline_equations"])

        report["summary"] = {
            "total_display_equations": total_display,
            "total_broken": broken_count,
            "equation_integrity_rate": round(
                1 - (broken_count / len(chunks)) if chunks else 1, 4
            ),
            "verdict": "PASS" if broken_count == 0 else "FAIL"
        }

        return report

    def run(self) -> dict:
        """Ejecuta la prueba de ingesta real completa."""
        print("\n")
        print("=" * 72)
        print("  PRUEBA DE INGESTA REAL: Galindo & Pascual")
        print("  Quantum Mechanics I (Springer, 1990)")
        print("=" * 72)

        # Cargar documento real
        doc_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            "material_curso", "galindo_pascual_qm1_sample.md"
        )
        content = self.load_real_document(doc_path)

        # Chunking semantico
        chunks = self.pipeline.semantic_chunking(content)
        self.pipeline.embed_and_store(chunks)

        # Analisis de fragmentacion estandar
        frag_stats = self.pipeline.analyze_fragmentation()

        # Analisis de integridad de ecuaciones
        eq_report = self.analyze_equation_integrity(chunks)

        # Imprimir reporte detallado
        print(f"\n{'=' * 72}")
        print(f"  REPORTE DETALLADO DE FRAGMENTACION")
        print(f"{'=' * 72}")

        print(f"\n  Chunks generados: {eq_report['total_chunks']}")
        print(f"  Ecuaciones display totales: {eq_report['summary']['total_display_equations']}")
        print(f"  Ecuaciones rotas: {eq_report['summary']['total_broken']}")
        print(f"  Tasa de integridad: {eq_report['summary']['equation_integrity_rate']:.0%}")

        print(f"\n  Detalle por chunk:")
        print(f"  {'ID':<5} {'Seccion':<40} {'Chars':<8} {'Eqs':<6} {'Estado':<8} {'Formulas Clave'}")
        print(f"  {'─'*5} {'─'*40} {'─'*8} {'─'*6} {'─'*8} {'─'*30}")

        for c in eq_report["equations_by_chunk"]:
            icon = "[OK]" if c["integrity"] == "OK" else "[!!]"
            formulas = ", ".join(c["key_formulas"][:3]) if c["key_formulas"] else "-"
            section = c["section"][:38] if len(c["section"]) > 38 else c["section"]
            print(f"  {c['chunk_id']:<5} {section:<40} {c['char_count']:<8} "
                  f"{c['display_equations']:<6} {icon:<8} {formulas}")

        # Verificacion de formulas clave
        print(f"\n  Verificacion de formulas criticas:")
        all_formulas = set()
        for c in eq_report["equations_by_chunk"]:
            all_formulas.update(c["key_formulas"])

        expected_formulas = [
            "Schrodinger", "Pozo infinito psi", "Energia cuantizada",
            "Conmutador", "Incertidumbre", "Oscilador", "Tunel", "Normalizacion"
        ]

        for formula in expected_formulas:
            found = formula in all_formulas
            icon = "[OK]" if found else "[MISS]"
            print(f"    {icon} {formula}")

        found_count = sum(1 for f in expected_formulas if f in all_formulas)
        print(f"\n    Cobertura de formulas: {found_count}/{len(expected_formulas)} = "
              f"{found_count/len(expected_formulas):.0%}")

        # Config check
        print(f"\n  Recomendacion de configuracion:")
        avg_size = frag_stats.get("avg_chunk_size", 0)
        if avg_size < 300:
            print(f"    [WARN] Chunks demasiado cortos ({avg_size:.0f} chars). "
                  f"Aumentar chunk_size en quantum_tutor_config.json")
            print(f"    Recomendacion: min_chunk_size = 400, max_chunk_size = 2000")
        elif avg_size > 2000:
            print(f"    [WARN] Chunks demasiado largos ({avg_size:.0f} chars). "
                  f"Reducir para mejorar precision del RAG")
        else:
            print(f"    [OK] Tamano promedio {avg_size:.0f} chars esta en rango optimo")

        verdict = eq_report["summary"]["verdict"]
        verdict_icon = "[PASS]" if verdict == "PASS" else "[FAIL]"

        print(f"\n{'=' * 72}")
        print(f"  {verdict_icon} VEREDICTO FINAL: {'APROBADO' if verdict == 'PASS' else 'REPROBADO'}")
        print(f"  Integridad de ecuaciones: {eq_report['summary']['equation_integrity_rate']:.0%}")
        print(f"  Calidad de fragmentacion: {frag_stats.get('fragmentation_quality', 'N/A')}")
        print(f"  Cobertura de formulas: {found_count}/{len(expected_formulas)}")
        print(f"{'=' * 72}\n")

        # Guardar reporte
        full_report = {
            "test_name": "Real Ingestion Test - Galindo & Pascual QM1",
            "timestamp": datetime.now().isoformat(),
            "document": doc_path,
            "fragmentation": frag_stats,
            "equation_integrity": eq_report,
            "verdict": verdict
        }

        with open("real_ingestion_results.json", "w", encoding="utf-8") as f:
            json.dump(full_report, f, indent=2, ensure_ascii=False, default=str)

        print(f"  Reporte guardado en: real_ingestion_results.json\n")
        return full_report


if __name__ == "__main__":
    test = RealIngestionTest()
    test.run()
