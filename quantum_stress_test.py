"""
QuantumStressTest v1.0 — Orquestador del Protocolo de Validación Científica
=============================================================================
Script principal que ejecuta las 3 dimensiones de evaluación del QuantumTutor:
  1. Precisión Simbólica (Wolfram) → CSR
  2. Fidelidad (NLI)              → Faithfulness Score
  3. Eficacia Socrática            → SCR

Genera un reporte JSON unificado y un scorecard visual en consola.
"""

import json
import sys
import os
from datetime import datetime

# Añadir el directorio actual al path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wolfram_emulator import WolframAlphaEmulator
from faithfulness_evaluator import FaithfulnessEvaluator
from socratic_evaluator import SocraticEvaluator


class QuantumStressTest:
    """
    Orquestador del protocolo completo "The Quantum Stress Test".
    Coordina las 3 dimensiones de evaluación y genera reportes unificados.
    """

    def __init__(self, config_path: str = "quantum_tutor_config.json"):
        self.config = self._load_config(config_path)
        self.results = {}
        self.timestamp = datetime.now().isoformat()

        # Pesos para la puntuación global (configurables)
        eval_config = self.config.get("evaluation_protocol", {})
        self.weights = eval_config.get("weights", {
            "faithfulness": 0.40,
            "symbolic_precision": 0.35,
            "socratic_efficacy": 0.25
        })
        self.thresholds = eval_config.get("thresholds", {
            "faithfulness": 0.85,
            "csr": 0.80,
            "scr": 0.80,
            "overall": 0.80
        })

    def _load_config(self, config_path: str) -> dict:
        """Carga la configuración del QuantumTutor."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"[WARN] {config_path} no encontrado. Usando configuración por defecto.")
            return {}

    def run_symbolic_validation(self) -> dict:
        """Ejecuta la batería de validación simbólica (Wolfram)."""
        emulator = WolframAlphaEmulator()
        return emulator.run_full_validation()

    def run_faithfulness_evaluation(self) -> dict:
        """Ejecuta la evaluación de fidelidad (NLI)."""
        min_score = self.config.get("safety_and_governance", {}).get(
            "min_faithfulness_score", 0.85)
        evaluator = FaithfulnessEvaluator(min_score=min_score)
        return evaluator.run_full_evaluation()

    def run_socratic_evaluation(self) -> dict:
        """Ejecuta el test de estrés pedagógico (Socrático)."""
        evaluator = SocraticEvaluator()
        return evaluator.run_full_evaluation()

    def calculate_overall_score(self) -> dict:
        """
        Calcula la puntuación global ponderada del QST.
        
        Fórmula: Overall = w_f × Faithfulness + w_s × CSR + w_sc × SCR
        """
        faithfulness = self.results.get("faithfulness", {}).get("summary", {})
        symbolic = self.results.get("symbolic_precision", {}).get("summary", {})
        socratic = self.results.get("socratic_efficacy", {}).get("summary", {})

        scores = {
            "faithfulness": faithfulness.get("faithfulness_score", 0),
            "symbolic_precision": symbolic.get("csr", 0),
            "socratic_efficacy": socratic.get("scr", 0)
        }

        weighted_sum = sum(
            scores[dim] * self.weights[dim]
            for dim in scores
        )

        # Determinar estados individuales
        dimension_status = {
            "faithfulness": {
                "score": scores["faithfulness"],
                "threshold": self.thresholds["faithfulness"],
                "status": "PASS" if scores["faithfulness"] >= self.thresholds["faithfulness"] else "FAIL",
                "weight": self.weights["faithfulness"]
            },
            "symbolic_precision": {
                "score": scores["symbolic_precision"],
                "threshold": self.thresholds["csr"],
                "status": "PASS" if scores["symbolic_precision"] >= self.thresholds["csr"] else "FAIL",
                "weight": self.weights["symbolic_precision"]
            },
            "socratic_efficacy": {
                "score": scores["socratic_efficacy"],
                "threshold": self.thresholds["scr"],
                "status": "PASS" if scores["socratic_efficacy"] >= self.thresholds["scr"] else "FAIL",
                "weight": self.weights["socratic_efficacy"]
            }
        }

        overall_pass = weighted_sum >= self.thresholds["overall"]

        return {
            "overall_score": round(weighted_sum, 4),
            "overall_threshold": self.thresholds["overall"],
            "overall_status": "PASS" if overall_pass else "FAIL",
            "dimensions": dimension_status,
            "weights": self.weights,
            "deployment_ready": overall_pass and all(
                d["status"] == "PASS" for d in dimension_status.values()
            )
        }

    def print_scorecard(self, overall: dict):
        """Imprime el scorecard final en consola con formato visual."""
        print("\n")
        print("╔" + "═"*68 + "╗")
        print("║" + " "*15 + "🎯 QUANTUM STRESS TEST — SCORECARD" + " "*18 + "║")
        print("║" + " "*15 + f"QuantumTutor v1.0 | {self.timestamp[:10]}" + " "*14 + "║")
        print("╠" + "═"*68 + "╣")

        for dim_key, dim_data in overall["dimensions"].items():
            dim_names = {
                "faithfulness": "Fidelidad (NLI)      ",
                "symbolic_precision": "Precisión Simbólica  ",
                "socratic_efficacy": "Eficacia Socrática   "
            }
            name = dim_names.get(dim_key, dim_key)
            score = dim_data["score"]
            threshold = dim_data["threshold"]
            status = dim_data["status"]
            weight = dim_data["weight"]
            icon = "✅" if status == "PASS" else "❌"

            bar_len = int(score * 30)
            bar = "█" * bar_len + "░" * (30 - bar_len)

            print(f"║  {icon} {name} {bar} {score:6.1%}  (≥{threshold:.0%}) ║")

        print("╠" + "═"*68 + "╣")

        overall_score = overall["overall_score"]
        overall_status = overall["overall_status"]
        deploy_ready = overall["deployment_ready"]

        icon = "✅" if overall_status == "PASS" else "❌"
        bar_len = int(overall_score * 30)
        bar = "█" * bar_len + "░" * (30 - bar_len)

        print(f"║  {icon} SCORE GLOBAL         {bar} {overall_score:6.1%}  (≥{overall['overall_threshold']:.0%}) ║")
        print("╠" + "═"*68 + "╣")

        if deploy_ready:
            print("║  🚀 ESTADO: APROBADO PARA DESPLIEGUE ACADÉMICO                     ║")
        else:
            print("║  🛑 ESTADO: NO APROBADO — REQUIERE CORRECCIONES                    ║")

        print("╚" + "═"*68 + "╝")

    def run(self) -> dict:
        """
        Ejecuta el protocolo completo del Quantum Stress Test.
        
        Returns:
            dict con todos los resultados, scores, y estado de despliegue
        """
        print("\n")
        print("╔" + "═"*68 + "╗")
        print("║     🔬 THE QUANTUM STRESS TEST — Protocolo de Validación v1.0     ║")
        print("║     QuantumTutor: Sistema Neuro-Simbólico para Física Cuántica     ║")
        print("╚" + "═"*68 + "╝")
        print(f"\n  ⏱️  Iniciando protocolo a las {self.timestamp}")
        print(f"  📋 Dimensiones a evaluar: 3")
        print(f"  📊 Pesos: Fidelidad={self.weights['faithfulness']:.0%}, "
              f"Simbólico={self.weights['symbolic_precision']:.0%}, "
              f"Socrático={self.weights['socratic_efficacy']:.0%}")

        # ── Dimensión 1: Precisión Simbólica ──────────────────────────
        print("\n\n" + "▓"*70)
        print("  DIMENSIÓN 1/3: PRECISIÓN SIMBÓLICA (WOLFRAM)")
        print("▓"*70)
        self.results["symbolic_precision"] = self.run_symbolic_validation()

        # ── Dimensión 2: Fidelidad (NLI) ─────────────────────────────
        print("\n\n" + "▓"*70)
        print("  DIMENSIÓN 2/3: FIDELIDAD (NLI)")
        print("▓"*70)
        self.results["faithfulness"] = self.run_faithfulness_evaluation()

        # ── Dimensión 3: Eficacia Socrática ───────────────────────────
        print("\n\n" + "▓"*70)
        print("  DIMENSIÓN 3/3: EFICACIA SOCRÁTICA")
        print("▓"*70)
        self.results["socratic_efficacy"] = self.run_socratic_evaluation()

        # ── Cálculo de Score Global ───────────────────────────────────
        overall = self.calculate_overall_score()
        self.results["overall"] = overall

        # ── Scorecard Final ───────────────────────────────────────────
        self.print_scorecard(overall)

        # ── Reporte completo ──────────────────────────────────────────
        full_report = {
            "metadata": {
                "test_name": "The Quantum Stress Test",
                "version": "1.0",
                "agent": self.config.get("system_metadata", {}).get(
                    "agent_name", "QuantumTutor_Simbionte_v1.0"),
                "timestamp": self.timestamp,
                "config_snapshot": {
                    "model": self.config.get("llm_config", {}).get("model", "N/A"),
                    "temperature": self.config.get("llm_config", {}).get("temperature", "N/A"),
                }
            },
            "dimensions": {
                "symbolic_precision": self.results["symbolic_precision"],
                "faithfulness": self.results["faithfulness"],
                "socratic_efficacy": self.results["socratic_efficacy"]
            },
            "overall": overall
        }

        return full_report


# ── Ejecución principal ──────────────────────────────────────────────
if __name__ == "__main__":
    print("  Cargando configuración desde quantum_tutor_config.json...")

    qst = QuantumStressTest()
    report = qst.run()

    # Guardar reporte completo
    output_path = "qst_results.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\n  📁 Reporte completo guardado en: {output_path}")
    print(f"  📊 Score Global: {report['overall']['overall_score']:.1%}")
    print(f"  {'🚀' if report['overall']['deployment_ready'] else '🛑'} "
          f"Listo para despliegue: {'SÍ' if report['overall']['deployment_ready'] else 'NO'}")
