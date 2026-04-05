from __future__ import annotations

from pathlib import Path
from typing import Any

from adaptive_learning_engine import AdaptiveLearningEngine


BASE_DIR = Path(__file__).resolve().parent
MICRO_LESSON_TEMPLATE_PATH = BASE_DIR / "templates" / "micro_leccion.md"


def _normalize_theme(theme: str) -> str:
    return (theme or "").strip().lower().replace(" ", "_")


def _difficulty_multiplier(difficulty: str) -> int:
    mapping = {
        "easy": 1,
        "medium": 2,
        "hard": 3,
    }
    return mapping.get((difficulty or "medium").strip().lower(), 2)


def _persona_prefix(persona: str) -> str:
    normalized = (persona or "").strip().lower()
    if normalized == "expert":
        return "Justifica con lenguaje tecnico y conecta con una implicacion fisica."
    if normalized == "advanced":
        return "Incluye una interpretacion formal y una intuicion fisica breve."
    if normalized == "intermediate":
        return "Explica el razonamiento paso a paso sin saltar el concepto clave."
    return "Prioriza intuicion, lenguaje claro y un ejemplo concreto."


def generate_exercises(
    theme: str,
    difficulty: str = "medium",
    count: int = 5,
    *,
    persona: str = "beginner",
    misconceptions: list[str] | None = None,
) -> list[dict[str, Any]]:
    theme_key = _normalize_theme(theme)
    difficulty_factor = _difficulty_multiplier(difficulty)
    count = max(1, min(int(count), 20))
    misconception_list = list(misconceptions or [])
    persona_prefix = _persona_prefix(persona)
    remediation_focus = misconception_list[0] if misconception_list else ""

    exercises: list[dict[str, Any]] = []
    for index in range(1, count + 1):
        n = index + difficulty_factor
        if theme_key in {"efecto_tunel", "tunel", "tunnel"}:
            barrier = 2.0 + 0.5 * difficulty_factor
            energy = round(barrier - 0.2 * index, 2)
            exercises.append({
                "id": f"{theme_key}-{index}",
                "theme": "efecto_tunel",
                "difficulty": difficulty,
                "prompt": (
                    f"Una particula con energia {energy} eV incide sobre una barrera de "
                    f"{barrier:.1f} eV. Explica cualitativamente por que la transmision no es cero. "
                    f"{persona_prefix}"
                ),
                "hint": "Compara la solucion clasica con la penetracion de la funcion de onda en la barrera.",
                "solution": (
                    "En mecanica cuantica la funcion de onda no se anula abruptamente en la barrera; "
                    "su cola exponencial permite una amplitud de transmision distinta de cero."
                ),
                "remediation_focus": remediation_focus,
            })
            continue

        if theme_key in {"pozo_infinito", "pozo", "infinite_well"}:
            width = 1.0 + 0.1 * n
            level = min(5, 1 + difficulty_factor)
            exercises.append({
                "id": f"{theme_key}-{index}",
                "theme": "pozo_infinito",
                "difficulty": difficulty,
                "prompt": (
                    f"Para un pozo infinito de ancho {width:.1f} nm, describe como cambia la energia "
                    f"del nivel n={level} si el ancho del pozo aumenta. {persona_prefix}"
                ),
                "hint": "Recuerda la dependencia de la energia con 1/L^2.",
                "solution": (
                    "La energia disminuye al aumentar el ancho porque los niveles del pozo infinito "
                    "escalan inversamente con el cuadrado del ancho."
                ),
                "remediation_focus": remediation_focus,
            })
            continue

        if theme_key in {"conmutadores", "commutators"}:
            exercises.append({
                "id": f"{theme_key}-{index}",
                "theme": "conmutadores",
                "difficulty": difficulty,
                "prompt": (
                    f"Explica por que el conmutador [x, p] es relevante para el principio de incertidumbre "
                    f"en un ejemplo corto de {n} lineas. {persona_prefix}"
                ),
                "hint": "Relaciona no conmutatividad con imposibilidad de fijar simultaneamente ambos observables.",
                "solution": (
                    "Si [x, p] != 0, no existe una base comun de autoestados exactos para ambos observables, "
                    "lo que se traduce en una cota inferior para las dispersiones."
                ),
                "remediation_focus": remediation_focus,
            })
            continue

        exercises.append({
            "id": f"{theme_key or 'general'}-{index}",
            "theme": theme_key or "general",
            "difficulty": difficulty,
            "prompt": (
                f"Construye una explicacion breve sobre superposicion cuantica con nivel {difficulty} "
                f"y agrega un ejemplo aplicado al caso {index}. {persona_prefix}"
            ),
            "hint": "Distingue estado base, combinacion lineal y medicion.",
            "solution": (
                "Una superposicion combina amplitudes de varios estados base. Antes de medir, el sistema "
                "evoluciona como esa combinacion; al medir, se obtiene uno de los resultados permitidos."
            ),
            "remediation_focus": remediation_focus,
        })

    return exercises


def generate_micro_lesson(
    node_id: str,
    engine: AdaptiveLearningEngine | None = None,
    *,
    persona: str = "beginner",
    mastery_threshold: float = 0.85,
) -> str:
    engine = engine or AdaptiveLearningEngine()
    node = engine.curriculum_nodes.get(node_id)
    if not node:
        raise KeyError(f"Unknown curriculum node: {node_id}")

    template = MICRO_LESSON_TEMPLATE_PATH.read_text(encoding="utf-8")
    objectives = "\n".join(f"- {item}" for item in node.get("objectives", []))
    activities = "\n".join(f"- {item}" for item in node.get("modalities", []))
    prerequisite_titles = [
        engine.curriculum_nodes.get(prereq_id, {}).get("title", prereq_id)
        for prereq_id in node.get("prerequisites", [])
    ]
    prerequisites = ", ".join(prerequisite_titles) or "Sin prerrequisitos"
    persona_note = _persona_prefix(persona)

    return template.format(
        title=node["title"],
        objective=f"{node.get('summary', '')} Dominio requerido para avanzar: {round(mastery_threshold * 100, 1)}%.",
        summary=f"{node.get('summary', '')}\n\nEnfoque sugerido para esta persona: {persona_note}",
        level=node.get("level", ""),
        estimated_minutes=node.get("estimated_minutes", ""),
        objectives=objectives,
        prerequisites=prerequisites,
        activities=activities,
        simulator=node.get("simulator", "Simulador sugerido pendiente"),
    )
