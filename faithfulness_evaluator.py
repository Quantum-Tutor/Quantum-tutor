"""
FaithfulnessEvaluator v1.0 — Motor de Evaluación NLI para QuantumTutor
=======================================================================
Evalúa la fidelidad de las respuestas generadas contra los fragmentos
fuente del RAG, asegurando que el tutor no alucine conceptos de física.

Metodología:
  1. Descomponer la respuesta en afirmaciones atómicas (claims)
  2. Clasificar cada claim: ENTAILED / NEUTRAL / CONTRADICTED
  3. Calcular Faithfulness Score = entailed / total
"""

import json
import re
from datetime import datetime


class FaithfulnessEvaluator:
    """
    Evaluador de fidelidad basado en Inferencia de Lenguaje Natural (NLI).
    Compara respuestas generadas contra fragmentos fuente del RAG.
    """

    def __init__(self, min_score: float = 0.85):
        self.min_faithfulness_score = min_score
        self.evaluation_log = []

        # ── Dataset de evaluación: 10 pares (respuesta, fuente) ───────
        self.test_pairs = self._build_test_dataset()

    def _build_test_dataset(self) -> list:
        """
        Construye el dataset de 10 pares de evaluación que cubren:
        - 4 afirmaciones correctas (ENTAILED)
        - 3 alucinaciones inventadas (CONTRADICTED)  
        - 3 semi-verdades peligrosas (NEUTRAL / parcialmente correctas)
        """
        return [
            # ── ENTAILED (correctas, soportadas por la fuente) ────────
            {
                "id": "F-01",
                "category": "ENTAILED",
                "source_fragment": (
                    "Para una partícula en una caja monodimensional de longitud L, "
                    "las condiciones de frontera exigen que la función de onda se anule "
                    "en las paredes (x=0 y x=L). La función de onda normalizada para "
                    "el n-ésimo estado es: ψ_n(x) = √(2/L) sin(nπx/L)."
                ),
                "generated_response": (
                    "La función de onda normalizada para el estado n en un pozo "
                    "de potencial infinito de longitud L es ψ_n(x) = √(2/L) sin(nπx/L), "
                    "donde las condiciones de frontera requieren que ψ se anule en x=0 y x=L."
                ),
                "expected_claims": [
                    {"claim": "La función de onda normalizada es ψ_n(x) = √(2/L) sin(nπx/L)", "label": "ENTAILED"},
                    {"claim": "Las condiciones de frontera requieren ψ=0 en x=0 y x=L", "label": "ENTAILED"},
                ]
            },
            {
                "id": "F-02",
                "category": "ENTAILED",
                "source_fragment": (
                    "La energía asociada a cada estado está cuantizada: "
                    "E_n = n²π²ℏ²/(2mL²). Solo valores discretos de energía son permitidos."
                ),
                "generated_response": (
                    "Los niveles de energía en el pozo infinito están cuantizados según "
                    "E_n = n²π²ℏ²/(2mL²), lo que significa que la partícula solo puede "
                    "tener valores discretos de energía."
                ),
                "expected_claims": [
                    {"claim": "E_n = n²π²ℏ²/(2mL²)", "label": "ENTAILED"},
                    {"claim": "Solo valores discretos de energía son permitidos", "label": "ENTAILED"},
                ]
            },
            {
                "id": "F-03",
                "category": "ENTAILED",
                "source_fragment": (
                    "La constante de normalización A se obtiene exigiendo que la "
                    "integral de |ψ|² sobre todo el espacio sea igual a 1."
                ),
                "generated_response": (
                    "Para normalizar la función de onda, necesitamos que "
                    "∫|ψ(x)|²dx = 1 sobre todo el espacio, lo cual nos permite "
                    "determinar la constante A."
                ),
                "expected_claims": [
                    {"claim": "La integral de |ψ|² debe ser 1", "label": "ENTAILED"},
                    {"claim": "Esto determina la constante A", "label": "ENTAILED"},
                ]
            },
            {
                "id": "F-04",
                "category": "ENTAILED",
                "source_fragment": (
                    "En el nivel n=2, existe un nodo (probabilidad cero) justo "
                    "en el centro del pozo, en x = L/2."
                ),
                "generated_response": (
                    "Para el primer estado excitado (n=2), hay un nodo en x = L/2 "
                    "donde la probabilidad de encontrar la partícula es exactamente cero."
                ),
                "expected_claims": [
                    {"claim": "Para n=2 hay un nodo en x = L/2", "label": "ENTAILED"},
                    {"claim": "La probabilidad es cero en el nodo", "label": "ENTAILED"},
                ]
            },
            # ── CONTRADICTED (alucinaciones, NO soportadas) ───────────
            {
                "id": "F-05",
                "category": "CONTRADICTED",
                "source_fragment": (
                    "La energía del estado fundamental del pozo infinito es "
                    "E_1 = π²ℏ²/(2mL²), que es siempre positiva y nunca cero."
                ),
                "generated_response": (
                    "La energía mínima de una partícula en un pozo de potencial infinito "
                    "es cero, correspondiente al estado fundamental n=0."
                ),
                "expected_claims": [
                    {"claim": "La energía mínima es cero", "label": "CONTRADICTED"},
                    {"claim": "El estado fundamental es n=0", "label": "CONTRADICTED"},
                ]
            },
            {
                "id": "F-06",
                "category": "CONTRADICTED",
                "source_fragment": (
                    "El principio de incertidumbre de Heisenberg establece que "
                    "ΔxΔp ≥ ℏ/2. Es una propiedad fundamental de la mecánica cuántica."
                ),
                "generated_response": (
                    "El principio de Heisenberg dice que la posición y el momento "
                    "no se pueden medir simultáneamente porque los instrumentos de "
                    "medición perturban la partícula."
                ),
                "expected_claims": [
                    {"claim": "La limitación se debe a perturbación del instrumento", "label": "CONTRADICTED"},
                ]
            },
            {
                "id": "F-07",
                "category": "CONTRADICTED",
                "source_fragment": (
                    "El efecto túnel permite que una partícula atraviese una "
                    "barrera de potencial incluso cuando su energía es menor que "
                    "la altura de la barrera."
                ),
                "generated_response": (
                    "En el efecto túnel cuántico, la partícula gana energía "
                    "temporalmente del vacío para superar la barrera, "
                    "violando momentáneamente la conservación de energía."
                ),
                "expected_claims": [
                    {"claim": "La partícula gana energía del vacío", "label": "CONTRADICTED"},
                    {"claim": "Viola la conservación de energía", "label": "CONTRADICTED"},
                ]
            },
            # ── NEUTRAL (semi-verdades, parcialmente correctas) ───────
            {
                "id": "F-08",
                "category": "NEUTRAL",
                "source_fragment": (
                    "El conmutador [x, p] = iℏ es una relación fundamental "
                    "de la mecánica cuántica que codifica la no conmutatividad "
                    "de la posición y el momento."
                ),
                "generated_response": (
                    "El conmutador [x, p] = iℏ es análogo al paréntesis de Poisson "
                    "en mecánica clásica, {x, p} = 1, y fue descubierto por Dirac "
                    "como parte de su formulación de la mecánica cuántica."
                ),
                "expected_claims": [
                    {"claim": "[x, p] = iℏ", "label": "ENTAILED"},
                    {"claim": "Es análogo al paréntesis de Poisson", "label": "NEUTRAL"},
                    {"claim": "Fue descubierto por Dirac", "label": "NEUTRAL"},
                ]
            },
            {
                "id": "F-09",
                "category": "NEUTRAL",
                "source_fragment": (
                    "La interpretación de Born establece que |ψ(x)|² representa "
                    "la densidad de probabilidad de encontrar la partícula en x."
                ),
                "generated_response": (
                    "Según Born, |ψ|² es la densidad de probabilidad. Esto fue "
                    "controversial porque Einstein creía que la mecánica cuántica "
                    "era incompleta y debía existir una teoría de variables ocultas."
                ),
                "expected_claims": [
                    {"claim": "|ψ|² es la densidad de probabilidad", "label": "ENTAILED"},
                    {"claim": "Einstein creía que era incompleta", "label": "NEUTRAL"},
                    {"claim": "Debía existir teoría de variables ocultas", "label": "NEUTRAL"},
                ]
            },
            {
                "id": "F-10",
                "category": "NEUTRAL",
                "source_fragment": (
                    "El oscilador armónico cuántico tiene niveles de energía "
                    "E_n = (n + 1/2)ℏω, con una energía de punto cero E_0 = ℏω/2."
                ),
                "generated_response": (
                    "Los niveles de energía del oscilador armónico son E_n = (n + 1/2)ℏω. "
                    "La energía de punto cero es ℏω/2 y es una consecuencia directa "
                    "del principio de incertidumbre, como mostró Heisenberg en 1927."
                ),
                "expected_claims": [
                    {"claim": "E_n = (n + 1/2)ℏω", "label": "ENTAILED"},
                    {"claim": "E_0 = ℏω/2", "label": "ENTAILED"},
                    {"claim": "Es consecuencia del principio de incertidumbre", "label": "NEUTRAL"},
                    {"claim": "Heisenberg lo mostró en 1927", "label": "NEUTRAL"},
                ]
            },
        ]

    def _extract_claims(self, pair: dict) -> list:
        """
        Extrae las afirmaciones atómicas de un par de evaluación.
        En un sistema real, usaríamos un modelo NLI (e.g., DeBERTa).
        Aquí usamos los claims pre-anotados del dataset.
        """
        return pair["expected_claims"]

    def _classify_claim(self, claim: dict, source: str) -> str:
        """
        Clasifica un claim contra la fuente RAG.
        Retorna: ENTAILED, NEUTRAL, o CONTRADICTED.

        En producción, esto invocaría un modelo NLI. Aquí utilizamos
        las etiquetas ground truth del dataset anotado.
        """
        return claim["label"]

    def evaluate_pair(self, pair: dict) -> dict:
        """
        Evalúa un par (respuesta, fuente) individual.
        
        Returns:
            dict con claims, clasificaciones, y faithfulness score local
        """
        claims = self._extract_claims(pair)
        source = pair["source_fragment"]

        classified = []
        entailed_count = 0

        for claim in claims:
            label = self._classify_claim(claim, source)
            classified.append({
                "claim": claim["claim"],
                "classification": label
            })
            if label == "ENTAILED":
                entailed_count += 1

        total = len(classified)
        score = entailed_count / total if total > 0 else 0.0

        return {
            "pair_id": pair["id"],
            "category": pair["category"],
            "source_preview": pair["source_fragment"][:80] + "...",
            "response_preview": pair["generated_response"][:80] + "...",
            "claims": classified,
            "entailed": entailed_count,
            "total_claims": total,
            "faithfulness_score": round(score, 4)
        }

    def run_full_evaluation(self) -> dict:
        """
        Ejecuta la evaluación completa de fidelidad sobre los 10 pares.
        
        Returns:
            dict con resultados individuales, score global, y estado PASS/FAIL
        """
        print("\n" + "="*70)
        print("  🧠 FAITHFULNESS EVALUATOR — NLI CONSISTENCY ANALYSIS")
        print("="*70)

        results = []
        total_entailed = 0
        total_claims = 0

        for pair in self.test_pairs:
            eval_result = self.evaluate_pair(pair)
            results.append(eval_result)

            total_entailed += eval_result["entailed"]
            total_claims += eval_result["total_claims"]

            icon = "✅" if eval_result["faithfulness_score"] == 1.0 else \
                   "⚠️" if eval_result["faithfulness_score"] >= 0.5 else "❌"

            print(f"\n  {icon} [{eval_result['pair_id']}] ({eval_result['category']})")
            print(f"     Score: {eval_result['faithfulness_score']:.0%} "
                  f"({eval_result['entailed']}/{eval_result['total_claims']} claims)")
            for c in eval_result["claims"]:
                c_icon = {"ENTAILED": "🟢", "NEUTRAL": "🟡", "CONTRADICTED": "🔴"}[c["classification"]]
                print(f"       {c_icon} {c['classification']}: \"{c['claim'][:60]}\"")

        global_score = total_entailed / total_claims if total_claims > 0 else 0.0
        passed = global_score >= self.min_faithfulness_score

        # Calcular scores por categoría
        cat_scores = {}
        for r in results:
            cat = r["category"]
            if cat not in cat_scores:
                cat_scores[cat] = {"entailed": 0, "total": 0}
            cat_scores[cat]["entailed"] += r["entailed"]
            cat_scores[cat]["total"] += r["total_claims"]

        print(f"\n{'─'*70}")
        print(f"  📊 Faithfulness Score Global: {total_entailed}/{total_claims} = {global_score:.1%}")
        print(f"  📋 Desglose por Categoría:")
        for cat, data in cat_scores.items():
            cat_score = data["entailed"] / data["total"] if data["total"] > 0 else 0
            print(f"     · {cat}: {data['entailed']}/{data['total']} = {cat_score:.0%}")
        status_icon = "✅" if passed else "❌"
        print(f"  {status_icon} Umbral mínimo: {self.min_faithfulness_score:.0%} — "
              f"{'APROBADO' if passed else 'REPROBADO'}")
        print("="*70 + "\n")

        return {
            "dimension": "faithfulness",
            "test_name": "NLI Faithfulness Evaluation",
            "timestamp": datetime.now().isoformat(),
            "results": results,
            "summary": {
                "total_claims": total_claims,
                "entailed_claims": total_entailed,
                "contradicted_claims": sum(
                    1 for r in results for c in r["claims"] if c["classification"] == "CONTRADICTED"
                ),
                "neutral_claims": sum(
                    1 for r in results for c in r["claims"] if c["classification"] == "NEUTRAL"
                ),
                "faithfulness_score": round(global_score, 4),
                "min_threshold": self.min_faithfulness_score,
                "category_breakdown": {
                    cat: round(d["entailed"] / d["total"], 4) if d["total"] > 0 else 0
                    for cat, d in cat_scores.items()
                },
                "status": "PASS" if passed else "FAIL"
            }
        }


# ── Ejecución standalone ─────────────────────────────────────────────
if __name__ == "__main__":
    evaluator = FaithfulnessEvaluator(min_score=0.85)
    report = evaluator.run_full_evaluation()

    with open("faithfulness_results.json", "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"📁 Resultados guardados en: faithfulness_results.json")
