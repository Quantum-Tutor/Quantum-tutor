from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from local_symbolic_engine import LocalSymbolicEngine
from request_optimization import normalize_query


@dataclass
class DeterministicMatch:
    kind: str
    response: str
    metadata: dict[str, Any]


class DeterministicResponder:
    """
    Offline responder for common educational prompts and small symbolic tasks.
    """

    def __init__(self, local_engine: Optional[LocalSymbolicEngine] = None):
        self.local_engine = local_engine or LocalSymbolicEngine()
        self.precomputed_entries = [
            {
                "id": "def_integral",
                "starts_with": ("que es una integral", "que es la integral", "explica una integral"),
                "response": (
                    "Respuesta precomputada:\n\n"
                    "Una integral representa acumulacion continua. En fisica cuantica suele aparecer para sumar "
                    "aportaciones infinitesimales, por ejemplo al normalizar una funcion de onda o al calcular "
                    "valores esperados.\n\n"
                    "Idea minima:\n"
                    "$$ \\int_a^b f(x)\\,dx $$\n\n"
                    "Si quieres, el siguiente paso puede ser verla como area geometrica, como operador inverso de la "
                    "derivada, o aplicada a una funcion de onda."
                ),
            },
            {
                "id": "def_oscilador",
                "starts_with": (
                    "que es el oscilador armonico",
                    "explica el oscilador armonico",
                    "define el oscilador armonico",
                ),
                "response": (
                    "Respuesta precomputada:\n\n"
                    "El oscilador armonico cuantico es el modelo donde la particula siente un potencial cuadratico:\n\n"
                    "$$ V(x)=\\frac{1}{2}m\\omega^2 x^2 $$\n\n"
                    "Es central porque aproxima vibraciones pequenas alrededor de un equilibrio y porque sus niveles "
                    "de energia estan cuantizados:\n\n"
                    "$$ E_n=\\hbar\\omega\\left(n+\\frac{1}{2}\\right) $$\n\n"
                    "Tambien es el punto de entrada natural para operadores de creacion y aniquilacion."
                ),
            },
            {
                "id": "def_pozo_infinito",
                "starts_with": (
                    "que es el pozo infinito",
                    "explica el pozo infinito",
                    "define el pozo infinito",
                ),
                "response": (
                    "Respuesta precomputada:\n\n"
                    "El pozo infinito es el modelo de una particula confinada entre paredes impenetrables. "
                    "Dentro del pozo el potencial es constante y fuera es infinito, asi que la funcion de onda "
                    "debe anularse en los bordes.\n\n"
                    "Las autofunciones estacionarias toman la forma:\n\n"
                    "$$ \\psi_n(x)=\\sqrt{\\frac{2}{L}}\\sin\\left(\\frac{n\\pi x}{L}\\right) $$\n\n"
                    "y las energias son discretas:\n\n"
                    "$$ E_n=\\frac{n^2\\pi^2\\hbar^2}{2mL^2} $$"
                ),
            },
            {
                "id": "def_conmutador",
                "starts_with": (
                    "que es un conmutador",
                    "explica el conmutador",
                    "define un conmutador",
                ),
                "response": (
                    "Respuesta precomputada:\n\n"
                    "El conmutador entre dos operadores mide si el orden importa al aplicarlos:\n\n"
                    "$$ [A,B]=AB-BA $$\n\n"
                    "Si el conmutador vale cero, los observables compatibles comparten una estructura algebraica mas "
                    "simple. En mecanica cuantica el ejemplo canonico es:\n\n"
                    "$$ [\\hat{x},\\hat{p}] = i\\hbar $$\n\n"
                    "y de ahi nace la relacion de incertidumbre."
                ),
            },
        ]

    def match(self, query: str, topic: str = "General", intent: str = "GENERAL", history_turns: int = 0) -> Optional[DeterministicMatch]:
        normalized = normalize_query(query)

        if intent != "GENERAL":
            return None

        precomputed = self._match_precomputed(normalized, history_turns)
        if precomputed:
            return precomputed

        symbolic = self._match_symbolic(normalized)
        if symbolic:
            return symbolic

        return None

    def _match_precomputed(self, normalized_query: str, history_turns: int) -> Optional[DeterministicMatch]:
        if history_turns > 0:
            return None

        for entry in self.precomputed_entries:
            if any(normalized_query.startswith(prefix) for prefix in entry["starts_with"]):
                return DeterministicMatch(
                    kind="precomputed",
                    response=entry["response"],
                    metadata={
                        "entry_id": entry["id"],
                        "source": "precomputed_kb",
                        "engine_status": "PRECOMPUTED_LOCAL",
                    },
                )
        return None

    def _match_symbolic(self, normalized_query: str) -> Optional[DeterministicMatch]:
        expression = self._translate_symbolic_query(normalized_query)
        if not expression:
            return None

        result = self.local_engine.evaluate_local(expression)
        if not result:
            return None

        response = self._build_symbolic_response(normalized_query, expression, result)
        return DeterministicMatch(
            kind="local_symbolic",
            response=response,
            metadata={
                "expression": expression,
                "source": result.get("source", "SymPy (Local)"),
                "engine_status": "DETERMINISTIC_LOCAL",
                "latex": result.get("latex"),
            },
        )

    def _translate_symbolic_query(self, normalized_query: str) -> Optional[str]:
        if (
            "conmutador" in normalized_query
            and "[x,p]" in normalized_query.replace(" ", "")
        ):
            return "Commutator[x, p]"

        if (
            "integral" in normalized_query
            and ("e^-x" in normalized_query or "exp(-x)" in normalized_query or "e^{-x}" in normalized_query)
            and "0" in normalized_query
            and ("infinito" in normalized_query or "infinity" in normalized_query)
        ):
            return "Integrate[Exp[-x], {x, 0, Infinity}]"

        if (
            "probabilidad" in normalized_query
            and "pozo" in normalized_query
            and ("n=2" in normalized_query or "n 2" in normalized_query)
            and ("l/4" in normalized_query or "cuarto" in normalized_query)
            and ("3l/4" in normalized_query or "tres cuartos" in normalized_query)
        ):
            return "Integrate[(Sqrt[2/L] Sin[2 Pi x / L])^2, {x, L/4, 3L/4}]"

        return None

    def _build_symbolic_response(self, normalized_query: str, expression: str, result: dict[str, Any]) -> str:
        parts = [
            "Resolucion deterministica local:",
            f"`{expression}`",
            "",
            "Resultado:",
        ]

        latex = result.get("latex")
        if latex:
            parts.append(f"$$ {latex} $$")
        else:
            parts.append(f"`{result.get('result', '')}`")

        if expression == "Commutator[x, p]":
            parts.append("")
            parts.append(
                "Interpretacion: posicion y momento no conmutan, asi que el orden de aplicacion importa. "
                "Esa estructura algebraica es la base de la incertidumbre canonica."
            )
        elif "Exp[-x]" in expression:
            parts.append("")
            parts.append(
                "Interpretacion: el area total bajo la exponencial en ese dominio es finita y vale 1, "
                "asi que ya actua como una distribucion normalizada."
            )
        elif "Sin[2 Pi x / L]" in expression:
            parts.append("")
            parts.append(
                "Interpretacion: para el estado n=2, la probabilidad integrada entre L/4 y 3L/4 da la mitad del total."
            )

        parts.append("")
        parts.append(f"Fuente local: {result.get('source', 'SymPy (Local)')}.")
        return "\n".join(parts)
