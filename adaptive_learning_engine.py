from __future__ import annotations

import csv
import hashlib
import json
import re
import time
import unicodedata
from io import StringIO
from pathlib import Path
from typing import Any

from quantum_tutor_paths import (
    LEARNING_COHORT_REPORT_PATH,
    LEARNING_COHORT_STUDENTS_CSV_PATH,
    LEARNING_CURRICULUM_PATH,
    LEARNING_DIAGNOSTIC_STATE_PATH,
    LEARNING_GAMIFICATION_PATH,
    LEARNING_PROGRESS_PATH,
    STUDENT_PROFILE_PATH,
    ensure_output_dirs,
    resolve_runtime_path,
    write_json_atomic,
    write_text_atomic,
)


LEVEL_ORDER = {
    "beginner": 0,
    "intermediate": 1,
    "advanced": 2,
}

DEFAULT_GAMIFICATION_EXPERIMENT = "gamification_v1"
MASTERY_THRESHOLD = 0.85
SPACED_REVIEW_BASE_SECONDS = 24 * 60 * 60
DEFAULT_EXPERIMENT_WINDOW_DAYS = 14
DEFAULT_EXPERIMENT_MIN_SAMPLE = 100
DEFAULT_EXPERIMENT_PRIMARY_METRIC = "learning_gain"
DIFFICULTY_ORDER = ["easy", "medium", "hard"]

MISCONCEPTION_PATTERNS = {
    "onda_particula_literal": [
        "la funcion de onda es una particula",
        "la onda es la particula",
        "colapso literal",
    ],
    "medicion_destruye_realidad": [
        "medir destruye la particula",
        "la medicion crea la realidad",
        "la medicion inventa el estado",
    ],
    "tunel_superluminal": [
        "tunel mas rapido que la luz",
        "atraviesa instantaneamente",
        "el tunel rompe relatividad",
    ],
}

MISCONCEPTION_NODE_MAP = {
    "onda_particula_literal": "qm_onda_funcion_onda",
    "medicion_destruye_realidad": "qm_medicion_cuantica",
    "tunel_superluminal": "qm_efecto_tunel",
}


BADGE_CATALOG = {
    "diagnostic_complete": {
        "id": "mapa-inicial",
        "label": "Mapa Inicial",
        "description": "Completo el diagnostico adaptativo inicial.",
    },
    "starter_foundations": {
        "id": "fundamentos-cuanticos",
        "label": "Fundamentos Cuanticos",
        "description": "Completo la base conceptual de entrada.",
    },
    "schrodinger_ready": {
        "id": "ecuacion-dominada",
        "label": "Ecuacion Dominada",
        "description": "Desbloqueo el bloque formal de Schroedinger.",
    },
    "measurement_practitioner": {
        "id": "medicion-cuanti-lab",
        "label": "Measurement Lab",
        "description": "Consolido medicion, tunel y analisis experimental.",
    },
    "quantum_applications": {
        "id": "aplicaciones-cuanticas",
        "label": "Aplicaciones Cuanticas",
        "description": "Llego al tramo de entrelazamiento y computacion cuantica.",
    },
}


DEFAULT_CURRICULUM: dict[str, Any] = {
    "version": "adaptive-learning-v1",
    "levels": [
        {
            "id": "beginner",
            "label": "Principiante",
            "description": "Base intuitiva con foco en analogias, simulacion y vocabulario esencial.",
        },
        {
            "id": "intermediate",
            "label": "Intermedio",
            "description": "Formalismo matematico y lectura de fenomenos cuanticos centrales.",
        },
        {
            "id": "advanced",
            "label": "Avanzado",
            "description": "Aplicaciones, laboratorios y conexiones con computacion cuantica.",
        },
    ],
    "milestones": [
        {
            "id": "starter_foundations",
            "label": "Starter Foundations",
            "required_nodes": [
                "qm_principios_basicos",
                "qm_onda_funcion_onda",
            ],
        },
        {
            "id": "schrodinger_ready",
            "label": "Schrodinger Ready",
            "required_nodes": [
                "qm_superposicion_operadores",
                "qm_ecuacion_schrodinger",
            ],
        },
        {
            "id": "measurement_practitioner",
            "label": "Measurement Practitioner",
            "required_nodes": [
                "qm_medicion_cuantica",
                "qm_efecto_tunel",
            ],
        },
        {
            "id": "quantum_applications",
            "label": "Quantum Applications",
            "required_nodes": [
                "qm_entrelazamiento",
                "qm_computacion_cuantica",
            ],
        },
    ],
    "nodes": [
        {
            "id": "qm_principios_basicos",
            "title": "Principios Basicos",
            "level": "beginner",
            "skill": "foundations",
            "estimated_minutes": 20,
            "prerequisites": [],
            "modalities": ["micro_lesson", "simulation", "guided_quiz"],
            "milestone_id": "starter_foundations",
            "summary": "Introduce dualidad onda-particula, probabilidad y lenguaje cuantico inicial.",
            "objectives": [
                "Distinguir entre modelo clasico y cuantico.",
                "Reconocer la interpretacion probabilistica basica.",
            ],
            "simulator": "Polarizadores o doble rendija virtual",
        },
        {
            "id": "qm_atomos_electrones",
            "title": "Atomos y Electrones",
            "level": "beginner",
            "skill": "foundations",
            "estimated_minutes": 25,
            "prerequisites": ["qm_principios_basicos"],
            "modalities": ["micro_lesson", "visualization", "guided_quiz"],
            "milestone_id": "starter_foundations",
            "summary": "Conecta orbitales, cuantizacion y transiciones con intuicion fisica.",
            "objectives": [
                "Describir cuantizacion de energia en sistemas atomicos.",
                "Relacionar transiciones con absorcion o emision.",
            ],
            "simulator": "Modelo atomico interactivo",
        },
        {
            "id": "qm_onda_funcion_onda",
            "title": "Onda y Funcion de Onda",
            "level": "beginner",
            "skill": "foundations",
            "estimated_minutes": 30,
            "prerequisites": ["qm_principios_basicos"],
            "modalities": ["micro_lesson", "visualization", "exercise"],
            "milestone_id": "starter_foundations",
            "summary": "Trabaja modulo cuadrado, normalizacion y lectura de densidad de probabilidad.",
            "objectives": [
                "Interpretar |psi|^2 como densidad de probabilidad.",
                "Leer cualitativamente una funcion de onda.",
            ],
            "simulator": "Visualizador de densidad de probabilidad",
        },
        {
            "id": "qm_superposicion_operadores",
            "title": "Superposicion y Operadores",
            "level": "intermediate",
            "skill": "mathematical_formalism",
            "estimated_minutes": 35,
            "prerequisites": ["qm_onda_funcion_onda"],
            "modalities": ["worked_example", "exercise", "notebook"],
            "milestone_id": "schrodinger_ready",
            "summary": "Introduce linealidad, operadores y observables de forma guiada.",
            "objectives": [
                "Aplicar linealidad a combinaciones de estados.",
                "Relacionar operadores con observables fisicos.",
            ],
            "simulator": "Bloques lineales o notebook simbolico",
        },
        {
            "id": "qm_ecuacion_schrodinger",
            "title": "Ecuacion de Schroedinger",
            "level": "intermediate",
            "skill": "mathematical_formalism",
            "estimated_minutes": 40,
            "prerequisites": ["qm_superposicion_operadores"],
            "modalities": ["worked_example", "exercise", "lab"],
            "milestone_id": "schrodinger_ready",
            "summary": "Aborda evolucion temporal, condiciones de frontera y pozos de potencial.",
            "objectives": [
                "Interpretar el papel de la ecuacion de Schroedinger.",
                "Resolver cualitativamente un pozo infinito sencillo.",
            ],
            "simulator": "Pozo de potencial interactivo",
        },
        {
            "id": "qm_medicion_cuantica",
            "title": "Medicion Cuantica",
            "level": "intermediate",
            "skill": "measurement",
            "estimated_minutes": 35,
            "prerequisites": ["qm_ecuacion_schrodinger"],
            "modalities": ["micro_lesson", "simulation", "exercise"],
            "milestone_id": "measurement_practitioner",
            "summary": "Desarrolla colapso, autovalores, incertidumbre y lectura de resultados experimentales.",
            "objectives": [
                "Explicar medicion como proyeccion sobre autoestados.",
                "Interpretar el principio de incertidumbre de manera operacional.",
            ],
            "simulator": "Experimentos de Stern-Gerlach virtuales",
        },
        {
            "id": "qm_efecto_tunel",
            "title": "Efecto Tunel",
            "level": "intermediate",
            "skill": "measurement",
            "estimated_minutes": 35,
            "prerequisites": ["qm_ecuacion_schrodinger"],
            "modalities": ["simulation", "lab", "exercise"],
            "milestone_id": "measurement_practitioner",
            "summary": "Aplica el formalismo a barreras de potencial y analiza transmision y reflexion.",
            "objectives": [
                "Describir por que existe transmision aun con energia menor a la barrera.",
                "Comparar el comportamiento clasico y cuantico.",
            ],
            "simulator": "Tunel cuantico tipo PhET o QuVis",
        },
        {
            "id": "qm_entrelazamiento",
            "title": "Entrelazamiento",
            "level": "advanced",
            "skill": "applications",
            "estimated_minutes": 45,
            "prerequisites": ["qm_medicion_cuantica"],
            "modalities": ["visualization", "lab", "challenge"],
            "milestone_id": "quantum_applications",
            "summary": "Introduce correlaciones no clasicas y lectura de estados bipartitos.",
            "objectives": [
                "Distinguir correlacion clasica de entrelazamiento.",
                "Interpretar escenarios de medicion en sistemas compuestos.",
            ],
            "simulator": "Laboratorio de qubits bipartitos",
        },
        {
            "id": "qm_computacion_cuantica",
            "title": "Computacion Cuantica Inicial",
            "level": "advanced",
            "skill": "applications",
            "estimated_minutes": 45,
            "prerequisites": ["qm_entrelazamiento"],
            "modalities": ["notebook", "lab", "challenge"],
            "milestone_id": "quantum_applications",
            "summary": "Conecta qubits, puertas cuanticas y circuitos elementales.",
            "objectives": [
                "Representar un qubit y una superposicion simple.",
                "Aplicar puertas basicas y leer su efecto conceptual.",
            ],
            "simulator": "Notebook Qiskit o circuito visual",
        },
    ],
}


DEFAULT_DIAGNOSTIC_QUESTION_BANK: list[dict[str, Any]] = [
    {
        "id": "diag_foundations_probability",
        "skill": "foundations",
        "level": "beginner",
        "difficulty": 1,
        "prompt": "En mecanica cuantica, |psi(x)|^2 representa principalmente:",
        "kind": "mcq",
        "options": [
            "La densidad de probabilidad de encontrar la particula en x",
            "La energia total del sistema",
            "La masa efectiva de la particula",
            "La velocidad instantanea exacta",
        ],
        "correct_answer": "La densidad de probabilidad de encontrar la particula en x",
        "hint": "Piensa en la interpretacion probabilistica de Born.",
        "explanation": "El modulo cuadrado de la funcion de onda se interpreta como densidad de probabilidad.",
        "remediation_node_id": "qm_onda_funcion_onda",
    },
    {
        "id": "diag_foundations_duality",
        "skill": "foundations",
        "level": "beginner",
        "difficulty": 1,
        "prompt": "La dualidad onda-particula sugiere que una entidad cuantica:",
        "kind": "mcq",
        "options": [
            "Puede mostrar rasgos ondulatorios o corpusculares segun el experimento",
            "Es siempre una particula clasica disfrazada",
            "Es una onda material sin ningun aspecto discreto",
            "No puede medirse de ningun modo",
        ],
        "correct_answer": "Puede mostrar rasgos ondulatorios o corpusculares segun el experimento",
        "hint": "Recuerda el experimento de doble rendija.",
        "explanation": "El comportamiento observado depende del arreglo experimental y no coincide con una intuicion clasica unica.",
        "remediation_node_id": "qm_principios_basicos",
    },
    {
        "id": "diag_math_superposition",
        "skill": "mathematical_formalism",
        "level": "intermediate",
        "difficulty": 2,
        "prompt": "Si |psi> y |phi> son estados validos, una combinacion lineal normalizable de ambos:",
        "kind": "mcq",
        "options": [
            "Tambien puede representar un estado cuantico",
            "Nunca representa un estado fisico",
            "Solo sirve en mecanica clasica",
            "Viola siempre la conservacion de energia",
        ],
        "correct_answer": "Tambien puede representar un estado cuantico",
        "hint": "La linealidad es una idea central del formalismo.",
        "explanation": "El principio de superposicion permite combinar estados mientras la expresion siga siendo fisicamente admisible y normalizable.",
        "remediation_node_id": "qm_superposicion_operadores",
    },
    {
        "id": "diag_math_schrodinger",
        "skill": "mathematical_formalism",
        "level": "intermediate",
        "difficulty": 2,
        "prompt": "La ecuacion de Schroedinger describe principalmente:",
        "kind": "mcq",
        "options": [
            "La evolucion temporal del estado cuantico",
            "El color real de una particula",
            "La perdida total de energia en una colision",
            "La trayectoria clasica exacta de la particula",
        ],
        "correct_answer": "La evolucion temporal del estado cuantico",
        "hint": "Preguntate que magnitud cambia con el tiempo en el formalismo.",
        "explanation": "La ecuacion de Schroedinger gobierna la dinamica del estado cuantico.",
        "remediation_node_id": "qm_ecuacion_schrodinger",
    },
    {
        "id": "diag_measurement_collapse",
        "skill": "measurement",
        "level": "intermediate",
        "difficulty": 2,
        "prompt": "Tras medir un observable idealmente, el estado queda asociado a:",
        "kind": "mcq",
        "options": [
            "Un autoestado compatible con el valor medido",
            "Cualquier estado aleatorio sin relacion con la medida",
            "La misma funcion de onda inicial siempre",
            "Unicamente la posicion clasica de la particula",
        ],
        "correct_answer": "Un autoestado compatible con el valor medido",
        "hint": "Relaciona medicion con autovalores y autoestados.",
        "explanation": "En el modelo ideal, la medicion proyecta el estado sobre un autoestado del observable medido.",
        "remediation_node_id": "qm_medicion_cuantica",
    },
    {
        "id": "diag_measurement_tunnel",
        "skill": "measurement",
        "level": "intermediate",
        "difficulty": 3,
        "prompt": "El efecto tunel cuantico muestra que una particula puede:",
        "kind": "mcq",
        "options": [
            "Atravesar una barrera con probabilidad no nula aun si su energia es menor",
            "Aumentar su masa al cruzar una barrera",
            "Desaparecer por completo del sistema",
            "Moverse siempre mas rapido que la luz",
        ],
        "correct_answer": "Atravesar una barrera con probabilidad no nula aun si su energia es menor",
        "hint": "Compara la prediccion cuantica con la intuicion clasica.",
        "explanation": "La funcion de onda penetra la barrera y genera una amplitud de transmision no nula.",
        "remediation_node_id": "qm_efecto_tunel",
    },
    {
        "id": "diag_applications_qubit",
        "skill": "applications",
        "level": "advanced",
        "difficulty": 3,
        "prompt": "Un qubit se diferencia de un bit clasico porque:",
        "kind": "mcq",
        "options": [
            "Puede estar en superposicion de |0> y |1>",
            "Solo almacena valores negativos",
            "No puede medirse en absoluto",
            "Es siempre equivalente a dos bits clasicos",
        ],
        "correct_answer": "Puede estar en superposicion de |0> y |1>",
        "hint": "Piensa en el espacio de estados permitido antes de medir.",
        "explanation": "Antes de la medicion, un qubit puede describirse como combinacion lineal de los estados base.",
        "remediation_node_id": "qm_computacion_cuantica",
    },
]

DEFAULT_CURRICULUM["nodes"] = [
    {
        "id": "math_functions",
        "title": "Funciones y Graficas",
        "level": "beginner",
        "skill": "mathematical_foundations",
        "estimated_minutes": 20,
        "prerequisites": [],
        "modalities": ["micro_lesson", "exercise", "guided_quiz"],
        "milestone_id": "starter_foundations",
        "summary": "Refuerza lectura de funciones, ejes, amplitud y comportamiento cualitativo.",
        "objectives": [
            "Interpretar el comportamiento de una funcion en una grafica.",
            "Relacionar forma de una curva con significado fisico basico.",
        ],
        "simulator": "Visualizador de funciones",
    },
    {
        "id": "math_derivatives",
        "title": "Derivadas para Quantum",
        "level": "beginner",
        "skill": "mathematical_foundations",
        "estimated_minutes": 25,
        "prerequisites": ["math_functions"],
        "modalities": ["worked_example", "exercise", "guided_quiz"],
        "milestone_id": "starter_foundations",
        "summary": "Trabaja razon de cambio y derivadas simples necesarias para Schroedinger.",
        "objectives": [
            "Reconocer derivadas como razon de cambio.",
            "Aplicar derivadas basicas a funciones polinomiales y exponenciales.",
        ],
        "simulator": "Explorador de derivadas",
    },
    {
        "id": "math_complex_numbers",
        "title": "Numeros Complejos",
        "level": "beginner",
        "skill": "mathematical_foundations",
        "estimated_minutes": 25,
        "prerequisites": ["math_functions"],
        "modalities": ["micro_lesson", "exercise", "visualization"],
        "milestone_id": "starter_foundations",
        "summary": "Introduce parte real, imaginaria y modulo para interpretar amplitudes cuanticas.",
        "objectives": [
            "Distinguir parte real e imaginaria.",
            "Relacionar modulo complejo con amplitud y probabilidad.",
        ],
        "simulator": "Plano complejo interactivo",
    },
] + DEFAULT_CURRICULUM["nodes"]

for _node in DEFAULT_CURRICULUM["nodes"]:
    if _node["id"] == "qm_principios_basicos":
        _node["prerequisites"] = ["math_functions"]
    elif _node["id"] == "qm_onda_funcion_onda":
        _node["prerequisites"] = ["qm_principios_basicos", "math_functions"]
    elif _node["id"] == "qm_superposicion_operadores":
        _node["prerequisites"] = ["qm_onda_funcion_onda", "math_complex_numbers"]
    elif _node["id"] == "qm_ecuacion_schrodinger":
        _node["prerequisites"] = ["qm_superposicion_operadores", "math_derivatives"]
    elif _node["id"] == "qm_efecto_tunel":
        _node["prerequisites"] = ["qm_ecuacion_schrodinger", "math_complex_numbers"]

DEFAULT_DIAGNOSTIC_QUESTION_BANK.extend([
    {
        "id": "diag_math_foundations_functions",
        "skill": "mathematical_foundations",
        "level": "beginner",
        "difficulty": 1,
        "prompt": "Si una funcion aumenta cuando x aumenta, su pendiente local suele ser:",
        "kind": "mcq",
        "options": [
            "Positiva",
            "Negativa",
            "Siempre cero",
            "Siempre imaginaria",
        ],
        "correct_answer": "Positiva",
        "hint": "Piensa en la relacion entre crecimiento y pendiente.",
        "explanation": "Una funcion creciente suele tener pendiente positiva en ese tramo.",
        "remediation_node_id": "math_functions",
    },
    {
        "id": "diag_math_foundations_complex",
        "skill": "mathematical_foundations",
        "level": "beginner",
        "difficulty": 2,
        "prompt": "En z = 3 + 4i, el modulo de z es:",
        "kind": "mcq",
        "options": [
            "5",
            "7",
            "1",
            "12",
        ],
        "correct_answer": "5",
        "hint": "Usa el teorema de Pitagoras en el plano complejo.",
        "explanation": "El modulo es sqrt(3^2 + 4^2) = 5.",
        "remediation_node_id": "math_complex_numbers",
    },
])


TOPIC_TO_NODE = {
    "Pozo Infinito": "qm_ecuacion_schrodinger",
    "Pozo Finito": "qm_ecuacion_schrodinger",
    "Efecto Túnel": "qm_efecto_tunel",
    "Espín": "qm_medicion_cuantica",
    "Oscilador Armónico": "qm_ecuacion_schrodinger",
    "Conmutadores": "qm_superposicion_operadores",
}


def _normalize_text(value: Any) -> str:
    raw = str(value or "").strip().lower()
    normalized = unicodedata.normalize("NFD", raw)
    without_marks = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    collapsed = re.sub(r"[^a-z0-9]+", " ", without_marks)
    return re.sub(r"\s+", " ", collapsed).strip()


class AdaptiveLearningEngine:
    def __init__(
        self,
        curriculum_path: Path = LEARNING_CURRICULUM_PATH,
        progress_path: Path = LEARNING_PROGRESS_PATH,
        diagnostic_state_path: Path = LEARNING_DIAGNOSTIC_STATE_PATH,
        gamification_path: Path = LEARNING_GAMIFICATION_PATH,
        analytics_path: Path = STUDENT_PROFILE_PATH,
    ):
        try:
            self._lock = __import__("threading").Lock()
        except Exception:
            pass

        self.curriculum_path = resolve_runtime_path(Path(curriculum_path), "learning_curriculum.json")
        self.progress_path = resolve_runtime_path(Path(progress_path), "learning_progress.json")
        self.diagnostic_state_path = resolve_runtime_path(Path(diagnostic_state_path), "learning_diagnostics.json")
        self.gamification_path = resolve_runtime_path(Path(gamification_path), "learning_gamification.json")
        self.analytics_path = resolve_runtime_path(Path(analytics_path), "student_profile.json")

        self.curriculum = self._load_or_bootstrap_curriculum()
        self.progress_state = self._load_json(
            self.progress_path,
            {"students": {}, "learning_cohorts": {}, "experiments": {}},
        )
        self.diagnostic_state = self._load_json(
            self.diagnostic_state_path,
            {"events": [], "question_bank_version": DEFAULT_CURRICULUM["version"]},
        )
        self.gamification_state = self._load_json(self.gamification_path, {"students": {}})
        self.question_bank = {item["id"]: dict(item) for item in DEFAULT_DIAGNOSTIC_QUESTION_BANK}
        self.curriculum_nodes = {item["id"]: dict(item) for item in self.curriculum["nodes"]}
        self.topic_to_node = {
            _normalize_text(topic): node_id
            for topic, node_id in TOPIC_TO_NODE.items()
        }

    def _load_json(self, path: Path, default: dict[str, Any]) -> dict[str, Any]:
        try:
            with path.open("r", encoding="utf-8") as handle:
                data = json.load(handle)
                if isinstance(data, dict):
                    return data
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            pass
        return json.loads(json.dumps(default))

    def _save_progress(self) -> None:
        with self._lock:
            write_json_atomic(self.progress_path, self.progress_state, indent=2, ensure_ascii=False)

    def _save_diagnostics(self) -> None:
        with self._lock:
            write_json_atomic(self.diagnostic_state_path, self.diagnostic_state, indent=2, ensure_ascii=False)

    def _save_gamification(self) -> None:
        with self._lock:
            write_json_atomic(self.gamification_path, self.gamification_state, indent=2, ensure_ascii=False)

    def _load_or_bootstrap_curriculum(self) -> dict[str, Any]:
        curriculum = self._load_json(self.curriculum_path, {})
        if curriculum.get("nodes") and curriculum.get("milestones"):
            return curriculum
        curriculum = json.loads(json.dumps(DEFAULT_CURRICULUM))
        write_json_atomic(self.curriculum_path, curriculum, indent=2, ensure_ascii=False)
        return curriculum

    def _default_student(self, student_id: str, goal: str = "fundamentos") -> dict[str, Any]:
        now = time.time()
        return {
            "student_id": student_id,
            "goal": goal,
            "target_level": "beginner",
            "skills": {
                "mathematical_foundations": 0.30,
                "foundations": 0.35,
                "mathematical_formalism": 0.30,
                "measurement": 0.25,
                "applications": 0.20,
            },
            "completed_nodes": [],
            "node_progress": {},
            "needs_remediation": [],
            "question_attempts": {},
            "diagnostic_answers": {},
            "last_diagnostic_question_ids": [],
            "diagnostic_completed": False,
            "pretest_score": None,
            "posttest_score": None,
            "assessment_history": [],
            "chat_events": [],
            "performance_events": [],
            "misconceptions": {},
            "persona": "beginner",
            "difficulty_profile": {
                "current_difficulty": "medium",
                "recommended_difficulty": "medium",
                "recent_accuracy": 0.0,
            },
            "optimization_profile": {
                "scaffolding": "standard",
                "difficulty_adjustment": "stable",
                "remediation_boost": False,
                "review_intensity": "standard",
                "last_updated_at": 0.0,
                "last_actions": [],
            },
            "learning_preferences": {
                "preferred_modalities": ["micro_lesson", "simulation", "guided_quiz"],
                "self_assessment": None,
            },
            "milestones_unlocked": [],
            "last_recommended_node": "",
            "created_at": now,
            "updated_at": now,
        }

    def _student(self, student_id: str, goal: str = "fundamentos") -> dict[str, Any]:
        students = self.progress_state.setdefault("students", {})
        if student_id not in students:
            students[student_id] = self._default_student(student_id, goal=goal)
        return students[student_id]

    def _gamification_entry(self, student_id: str) -> dict[str, Any]:
        students = self.gamification_state.setdefault("students", {})
        if student_id not in students:
            students[student_id] = {
                "points": 0,
                "badges": [],
                "events": [],
                "experiments": {},
            }
        students[student_id].setdefault("experiments", {})
        return students[student_id]

    def get_experiment_assignment(
        self,
        student_id: str,
        *,
        experiment_name: str = DEFAULT_GAMIFICATION_EXPERIMENT,
        variants: tuple[str, str] = ("control", "challenge"),
    ) -> dict[str, Any]:
        profile = self._gamification_entry(student_id)
        experiments = profile.setdefault("experiments", {})
        assignment = experiments.get(experiment_name)
        if assignment:
            assignment.setdefault("metric", DEFAULT_EXPERIMENT_PRIMARY_METRIC)
            assignment.setdefault("min_sample", DEFAULT_EXPERIMENT_MIN_SAMPLE)
            assignment.setdefault("window_days", DEFAULT_EXPERIMENT_WINDOW_DAYS)
            assignment.setdefault("start_at", assignment.get("assigned_at", time.time()))
            assignment.setdefault(
                "end_at",
                float(assignment["start_at"]) + float(assignment["window_days"]) * 24 * 60 * 60,
            )
            return dict(assignment)

        digest = hashlib.sha256(f"{experiment_name}:{student_id}".encode("utf-8")).hexdigest()
        variant = variants[int(digest[:8], 16) % len(variants)]
        start_at = time.time()
        assignment = {
            "experiment_name": experiment_name,
            "variant": variant,
            "assigned_at": start_at,
            "start_at": start_at,
            "window_days": DEFAULT_EXPERIMENT_WINDOW_DAYS,
            "end_at": start_at + DEFAULT_EXPERIMENT_WINDOW_DAYS * 24 * 60 * 60,
            "metric": DEFAULT_EXPERIMENT_PRIMARY_METRIC,
            "min_sample": DEFAULT_EXPERIMENT_MIN_SAMPLE,
        }
        experiments[experiment_name] = assignment
        self._save_gamification()
        return dict(assignment)

    def _award_points(self, student_id: str, points: int, reason: str) -> None:
        profile = self._gamification_entry(student_id)
        profile["points"] = int(profile.get("points", 0)) + max(int(points), 0)
        profile.setdefault("events", []).append({
            "type": "points",
            "reason": reason,
            "points": int(points),
            "created_at": time.time(),
        })
        profile["events"] = profile["events"][-100:]

    def _award_badge(self, student_id: str, badge_key: str) -> dict[str, Any] | None:
        badge = BADGE_CATALOG.get(badge_key)
        if not badge:
            return None
        profile = self._gamification_entry(student_id)
        existing = {item["id"] for item in profile.get("badges", [])}
        if badge["id"] in existing:
            return None
        badge_payload = dict(badge)
        badge_payload["created_at"] = time.time()
        profile.setdefault("badges", []).append(badge_payload)
        profile.setdefault("events", []).append({
            "type": "badge",
            "badge_id": badge_payload["id"],
            "created_at": badge_payload["created_at"],
        })
        profile["events"] = profile["events"][-100:]
        return badge_payload

    def _analytics_remediation_nodes(self) -> list[str]:
        try:
            with self.analytics_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            return []

        nodes: list[str] = []
        for topic, entry in (payload.get("topics", {}) or {}).items():
            struggle = float((entry or {}).get("struggle_index", 0.0))
            mapped = self.topic_to_node.get(_normalize_text(topic))
            if mapped and struggle >= 0.35:
                nodes.append(mapped)
        return list(dict.fromkeys(nodes))

    def _visible_question(self, question: dict[str, Any]) -> dict[str, Any]:
        return {
            "id": question["id"],
            "skill": question["skill"],
            "level": question["level"],
            "difficulty": question["difficulty"],
            "prompt": question["prompt"],
            "kind": question["kind"],
            "options": list(question.get("options", [])),
        }

    def _milestone_status(self, completed_nodes: set[str]) -> list[dict[str, Any]]:
        rows: list[dict[str, Any]] = []
        for milestone in self.curriculum["milestones"]:
            required = list(milestone.get("required_nodes", []))
            completed_count = sum(1 for node_id in required if node_id in completed_nodes)
            rows.append({
                "id": milestone["id"],
                "label": milestone["label"],
                "required_nodes": required,
                "completed_count": completed_count,
                "required_count": len(required),
                "progress": round((completed_count / len(required)) if required else 0.0, 3),
                "unlocked": completed_count == len(required) and bool(required),
            })
        return rows

    def _node_progress_snapshot(self, student: dict[str, Any], node_id: str) -> dict[str, Any]:
        progress = dict((student.get("node_progress", {}) or {}).get(node_id, {}))
        progress.setdefault("mastery_score", 0.0)
        progress.setdefault("completed", False)
        progress.setdefault("source", "")
        progress.setdefault("updated_at", 0.0)
        progress.setdefault("first_exposure_at", 0.0)
        progress.setdefault("mastery_achieved_at", 0.0)
        progress.setdefault("retention_score", 0.4)
        progress.setdefault("review_count", 0)
        progress.setdefault("next_review_at", 0.0)
        progress.setdefault("review_interval_seconds", SPACED_REVIEW_BASE_SECONDS)
        return progress

    def _synchronize_completed_nodes(self, student: dict[str, Any]) -> list[str]:
        ordered_nodes = [node["id"] for node in self.curriculum["nodes"]]
        mastered_nodes = {
            node_id
            for node_id in ordered_nodes
            if self._node_mastered(student, node_id)
        }
        student["completed_nodes"] = [node_id for node_id in ordered_nodes if node_id in mastered_nodes]
        return list(student["completed_nodes"])

    def _node_mastered(self, student: dict[str, Any], node_id: str) -> bool:
        progress = self._node_progress_snapshot(student, node_id)
        return bool(progress.get("completed")) and float(progress.get("mastery_score", 0.0)) >= MASTERY_THRESHOLD

    def _shift_difficulty(self, difficulty: str, direction: str) -> str:
        normalized = (difficulty or "medium").strip().lower()
        try:
            index = DIFFICULTY_ORDER.index(normalized)
        except ValueError:
            index = 1
        if direction == "easier":
            index = max(index - 1, 0)
        elif direction == "harder":
            index = min(index + 1, len(DIFFICULTY_ORDER) - 1)
        return DIFFICULTY_ORDER[index]

    def _touch_progress_entry(self, progress_entry: dict[str, Any]) -> dict[str, Any]:
        now = time.time()
        if float(progress_entry.get("first_exposure_at", 0.0) or 0.0) <= 0:
            progress_entry["first_exposure_at"] = now
        progress_entry["updated_at"] = now
        return progress_entry

    def _mark_mastery_timestamp(self, progress_entry: dict[str, Any]) -> dict[str, Any]:
        if (
            bool(progress_entry.get("completed"))
            and float(progress_entry.get("mastery_score", 0.0) or 0.0) >= MASTERY_THRESHOLD
            and float(progress_entry.get("mastery_achieved_at", 0.0) or 0.0) <= 0
        ):
            progress_entry["mastery_achieved_at"] = time.time()
        return progress_entry

    def _classify_persona(self, student: dict[str, Any]) -> str:
        pretest = student.get("pretest_score")
        overall_mastery = sum(float(value) for value in student.get("skills", {}).values()) / max(len(student.get("skills", {})), 1)
        score = float(pretest) if pretest is not None else overall_mastery
        if score < 0.3:
            return "beginner"
        if score < 0.7:
            return "intermediate"
        if score < 0.9:
            return "advanced"
        return "expert"

    def _difficulty_from_accuracy(self, accuracy: float) -> str:
        if accuracy > 0.9:
            return "hard"
        if accuracy < 0.6:
            return "easy"
        return "medium"

    def _update_difficulty_profile(self, student: dict[str, Any]) -> dict[str, Any]:
        attempts = list((student.get("question_attempts", {}) or {}).values())
        recent = attempts[-8:]
        accuracy = (
            sum(1 for item in recent if item.get("correct")) / max(len(recent), 1)
            if recent else 0.0
        )
        recommended = self._difficulty_from_accuracy(accuracy if recent else 0.75)
        adjustment = (student.get("optimization_profile", {}) or {}).get("difficulty_adjustment", "stable")
        if adjustment in {"easier", "harder"}:
            recommended = self._shift_difficulty(recommended, adjustment)
        profile = student.setdefault("difficulty_profile", {})
        profile["recent_accuracy"] = round(accuracy, 3)
        profile["recommended_difficulty"] = recommended
        profile["current_difficulty"] = recommended
        return profile

    def _schedule_review(
        self,
        progress_entry: dict[str, Any],
        *,
        successful: bool,
        confidence: float,
    ) -> dict[str, Any]:
        now = time.time()
        review_count = int(progress_entry.get("review_count", 0)) + 1
        previous_interval = float(progress_entry.get("review_interval_seconds", SPACED_REVIEW_BASE_SECONDS))
        if successful:
            interval = max(SPACED_REVIEW_BASE_SECONDS, previous_interval * 2.0)
            retention = min(0.98, max(float(progress_entry.get("retention_score", 0.4)), confidence))
        else:
            interval = SPACED_REVIEW_BASE_SECONDS
            retention = max(0.2, float(progress_entry.get("retention_score", 0.4)) - 0.15)
        progress_entry["review_count"] = review_count
        progress_entry["review_interval_seconds"] = round(interval, 3)
        progress_entry["retention_score"] = round(retention, 3)
        progress_entry["next_review_at"] = round(now + interval, 3)
        return progress_entry

    def _detect_misconceptions(self, text: Any) -> list[str]:
        normalized = _normalize_text(text)
        if not normalized:
            return []
        hits = []
        for key, patterns in MISCONCEPTION_PATTERNS.items():
            if any(_normalize_text(pattern) in normalized for pattern in patterns):
                hits.append(key)
        return hits

    def _record_misconceptions(self, student: dict[str, Any], text: Any) -> list[str]:
        hits = self._detect_misconceptions(text)
        bucket = student.setdefault("misconceptions", {})
        for hit in hits:
            entry = bucket.setdefault(
                hit,
                {
                    "count": 0,
                    "last_seen_at": 0.0,
                    "first_seen_at": 0.0,
                    "resolved_count": 0,
                    "active": False,
                },
            )
            entry["count"] = int(entry.get("count", 0)) + 1
            if float(entry.get("first_seen_at", 0.0) or 0.0) <= 0:
                entry["first_seen_at"] = time.time()
            entry["last_seen_at"] = time.time()
            entry["active"] = True
        return hits

    def _resolve_misconceptions_for_node(
        self,
        student: dict[str, Any],
        node_id: str,
        *,
        successful: bool,
        ignored: list[str] | None = None,
    ) -> list[str]:
        if not successful:
            return []
        bucket = student.setdefault("misconceptions", {})
        ignored_set = set(ignored or [])
        resolved: list[str] = []
        for misconception, mapped_node in MISCONCEPTION_NODE_MAP.items():
            if mapped_node != node_id:
                continue
            if misconception in ignored_set:
                continue
            entry = bucket.get(misconception)
            if not entry or not bool(entry.get("active")):
                continue
            entry["active"] = False
            entry["resolved_count"] = int(entry.get("resolved_count", 0)) + 1
            entry["resolved_at"] = time.time()
            resolved.append(misconception)
        return resolved

    def _record_performance_event(
        self,
        student: dict[str, Any],
        *,
        node_id: str,
        correct: bool,
        event_type: str,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "node_id": node_id,
            "correct": bool(correct),
            "event_type": event_type,
            "created_at": time.time(),
        }
        if metadata:
            payload.update(metadata)
        student.setdefault("performance_events", []).append(payload)
        student["performance_events"] = student["performance_events"][-500:]

    def _dominant_misconception(self, student: dict[str, Any]) -> str:
        bucket = student.get("misconceptions", {}) or {}
        if not bucket:
            return "none"
        ranked = sorted(
            bucket.items(),
            key=lambda item: (
                0 if item[1].get("active") else 1,
                -int(item[1].get("count", 0) or 0),
                item[0],
            ),
        )
        return ranked[0][0] if ranked else "none"

    def _current_module(self, student: dict[str, Any]) -> dict[str, str]:
        node_id = str(student.get("last_recommended_node", "") or "")
        if not node_id:
            lesson_history = list(student.get("lesson_history", []) or [])
            if lesson_history:
                node_id = str((lesson_history[-1] or {}).get("node_id", "") or "")
        if not node_id:
            chat_events = list(student.get("chat_events", []) or [])
            if chat_events:
                node_id = str((chat_events[-1] or {}).get("node_id", "") or "")
        if not node_id:
            node_id = "unassigned"
        title = self.curriculum_nodes.get(node_id, {}).get("title", node_id)
        return {
            "node_id": node_id,
            "title": title,
        }

    def _average_time_to_mastery_seconds(self, student: dict[str, Any]) -> float | None:
        values = []
        for progress in (student.get("node_progress", {}) or {}).values():
            first_exposure = float(progress.get("first_exposure_at", 0.0) or 0.0)
            mastered_at = float(progress.get("mastery_achieved_at", 0.0) or 0.0)
            if first_exposure > 0 and mastered_at > first_exposure:
                values.append(mastered_at - first_exposure)
        if not values:
            return None
        return round(sum(values) / len(values), 3)

    def _average_retention_score(self, student: dict[str, Any]) -> float | None:
        rows = list((student.get("node_progress", {}) or {}).values())
        if not rows:
            return None
        return round(
            sum(float(item.get("retention_score", 0.0) or 0.0) for item in rows) / len(rows),
            3,
        )

    def _error_reduction_rate(self, student: dict[str, Any]) -> float | None:
        events = list(student.get("performance_events", []) or [])
        if len(events) < 2:
            return None
        midpoint = max(len(events) // 2, 1)
        initial_errors = sum(1 for item in events[:midpoint] if not item.get("correct"))
        final_errors = sum(1 for item in events[midpoint:] if not item.get("correct"))
        if initial_errors <= 0:
            return None
        return round((initial_errors - final_errors) / initial_errors, 3)

    def _misconception_resolution_rate(self, student: dict[str, Any]) -> float | None:
        bucket = student.get("misconceptions", {}) or {}
        total_detected = sum(int((entry or {}).get("count", 0) or 0) for entry in bucket.values())
        if total_detected <= 0:
            return None
        resolved = sum(int((entry or {}).get("resolved_count", 0) or 0) for entry in bucket.values())
        return round(resolved / total_detected, 3)

    def _structured_feedback(self, question: dict[str, Any], answer: Any, correct: bool) -> dict[str, Any]:
        misconceptions = self._detect_misconceptions(answer)
        common_error = (
            "Tu respuesta no distingue correctamente la idea central del concepto."
            if not misconceptions else
            f"Aparece el patron de misconception: {misconceptions[0]}."
        )
        if correct:
            steps = [
                "Acierto: identificaste correctamente la idea principal.",
                "Error: no hay un error conceptual dominante en esta respuesta.",
                f"Explicacion conceptual: {question['explanation']}",
                "Correccion guiada: intenta justificar con tus propias palabras por que esa opcion es la mejor.",
                "Nuevo intento: responde una variante del mismo concepto con un ejemplo propio.",
            ]
        else:
            steps = [
                "Acierto: tu respuesta intenta conectar con el concepto correcto, aunque falta precision.",
                f"Error: {common_error}",
                f"Explicacion conceptual: {question['explanation']}",
                f"Correccion guiada: {question['hint']}",
                "Nuevo intento: vuelve a responder reformulando la idea con menos intuicion clasica y mas criterio cuantico.",
            ]
        return {
            "steps": steps,
            "misconceptions": misconceptions,
        }

    def _sync_student_profile(self, student_id: str) -> None:
        student = self._student(student_id)
        try:
            with self.analytics_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
                if not isinstance(payload, dict):
                    payload = {}
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            payload = {}

        adaptive_bucket = payload.setdefault("adaptive_learning", {})
        adaptive_students = adaptive_bucket.setdefault("students", {})
        adaptive_students[student_id] = {
            "persona": student.get("persona", "beginner"),
            "target_level": student.get("target_level", "beginner"),
            "diagnostic_completed": bool(student.get("diagnostic_completed")),
            "pretest_score": student.get("pretest_score"),
            "posttest_score": student.get("posttest_score"),
            "skills": dict(student.get("skills", {})),
            "difficulty_profile": dict(student.get("difficulty_profile", {})),
            "optimization_profile": dict(student.get("optimization_profile", {})),
            "misconceptions": dict(student.get("misconceptions", {})),
            "milestones_unlocked": list(student.get("milestones_unlocked", [])),
            "updated_at": time.time(),
        }
        adaptive_bucket["last_synced_at"] = time.time()
        write_json_atomic(self.analytics_path, payload, indent=2, ensure_ascii=False)

    def _current_level(self, student: dict[str, Any]) -> str:
        skills = student.get("skills", {})
        mastery = sum(float(value) for value in skills.values()) / max(len(skills), 1)
        completed_count = len(student.get("completed_nodes", []))
        if mastery >= 0.72 or completed_count >= 7:
            return "advanced"
        if mastery >= 0.48 or completed_count >= 3:
            return "intermediate"
        return "beginner"

    def _recommended_modalities(self, student: dict[str, Any]) -> list[str]:
        skills = student.get("skills", {})
        weakest_skill = min(skills, key=skills.get)
        persona = student.get("persona", "beginner")
        self_assessment = student.get("learning_preferences", {}).get("self_assessment")
        optimization = student.get("optimization_profile", {}) or {}
        if optimization.get("scaffolding") == "high":
            return ["micro_lesson", "worked_example", "guided_quiz"]
        if optimization.get("remediation_boost"):
            return ["micro_lesson", "simulation", "guided_quiz"]
        if self_assessment is not None and float(self_assessment) <= 2.0:
            return ["micro_lesson", "simulation", "guided_quiz"]
        if persona == "expert":
            return ["challenge", "notebook", "lab"]
        if persona == "advanced":
            return ["worked_example", "challenge", "lab"]
        if weakest_skill == "mathematical_formalism":
            return ["worked_example", "exercise", "notebook"]
        if weakest_skill == "measurement":
            return ["simulation", "lab", "exercise"]
        if weakest_skill == "applications":
            return ["visualization", "challenge", "lab"]
        return ["micro_lesson", "simulation", "guided_quiz"]

    def _recommended_modality_for_node(self, student: dict[str, Any], node: dict[str, Any]) -> str:
        preferred = self._recommended_modalities(student)
        available = list(node.get("modalities", []))
        for modality in preferred:
            if modality in available:
                return modality
        return available[0] if available else preferred[0]

    def _node_prerequisite_status(self, student: dict[str, Any], node: dict[str, Any]) -> list[dict[str, Any]]:
        rows = []
        for prereq_id in node.get("prerequisites", []):
            prereq_node = self.curriculum_nodes.get(prereq_id, {})
            rows.append({
                "node_id": prereq_id,
                "title": prereq_node.get("title", prereq_id),
                "mastered": self._node_mastered(student, prereq_id),
            })
        return rows

    def _route_node_payload(
        self,
        student: dict[str, Any],
        node: dict[str, Any],
        *,
        route_reason: str,
        review_entry: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        progress = self._node_progress_snapshot(student, node["id"])
        payload = dict(node)
        payload["recommended_modality"] = self._recommended_modality_for_node(student, node)
        payload["recommended_difficulty"] = (
            (student.get("difficulty_profile", {}) or {}).get("recommended_difficulty", "medium")
        )
        payload["mastery_required"] = MASTERY_THRESHOLD
        payload["current_mastery"] = round(float(progress.get("mastery_score", 0.0) or 0.0), 3)
        payload["completed"] = bool(progress.get("completed", False))
        payload["retention_score"] = round(float(progress.get("retention_score", 0.0) or 0.0), 3)
        payload["review_count"] = int(progress.get("review_count", 0) or 0)
        payload["next_review_at"] = float(progress.get("next_review_at", 0.0) or 0.0)
        payload["review_due"] = bool(review_entry.get("due")) if review_entry else False
        payload["route_reason"] = route_reason
        payload["prerequisites_status"] = self._node_prerequisite_status(student, node)
        payload["blocked_by"] = [
            item["title"]
            for item in payload["prerequisites_status"]
            if not item["mastered"]
        ]
        return payload

    def curriculum_overview(self) -> dict[str, Any]:
        return {
            "version": self.curriculum["version"],
            "levels": self.curriculum["levels"],
            "milestones": self.curriculum["milestones"],
            "nodes": self.curriculum["nodes"],
            "diagnostic_question_count": len(self.question_bank),
            "mastery_threshold": MASTERY_THRESHOLD,
            "spaced_review_base_seconds": SPACED_REVIEW_BASE_SECONDS,
            "misconception_catalog": sorted(MISCONCEPTION_PATTERNS.keys()),
        }

    def get_initial_diagnostic(
        self,
        student_id: str,
        *,
        goal: str = "fundamentos",
        target_level: str = "beginner",
        max_questions: int = 5,
    ) -> dict[str, Any]:
        student = self._student(student_id, goal=goal)
        student["goal"] = goal or student.get("goal", "fundamentos")
        student["target_level"] = target_level if target_level in LEVEL_ORDER else "beginner"
        student["updated_at"] = time.time()

        ordered_questions = sorted(
            self.question_bank.values(),
            key=lambda item: (LEVEL_ORDER.get(item["level"], 0), item["difficulty"], item["id"]),
        )

        if student["target_level"] == "advanced":
            ordered_questions = sorted(
                ordered_questions,
                key=lambda item: (abs(item["difficulty"] - 3), LEVEL_ORDER.get(item["level"], 0), item["id"]),
            )
        elif student["target_level"] == "intermediate":
            ordered_questions = sorted(
                ordered_questions,
                key=lambda item: (abs(item["difficulty"] - 2), LEVEL_ORDER.get(item["level"], 0), item["id"]),
            )

        selected: list[dict[str, Any]] = []
        seen_skills: set[str] = set()
        for question in ordered_questions:
            if question["skill"] not in seen_skills:
                selected.append(question)
                seen_skills.add(question["skill"])
            if len(selected) >= max_questions:
                break

        if len(selected) < max_questions:
            used_ids = {item["id"] for item in selected}
            for question in ordered_questions:
                if question["id"] in used_ids:
                    continue
                selected.append(question)
                if len(selected) >= max_questions:
                    break

        student["last_diagnostic_question_ids"] = [item["id"] for item in selected]
        self._award_points(student_id, 5, "diagnostic_requested")
        self._save_progress()
        self._save_gamification()

        return {
            "student_id": student_id,
            "goal": student["goal"],
            "target_level": student["target_level"],
            "estimated_minutes": max(5, len(selected) * 2),
            "question_bank_version": self.curriculum["version"],
            "questions": [self._visible_question(item) for item in selected],
            "recommended_modalities": self._recommended_modalities(student),
            "milestones": self.curriculum["milestones"],
        }

    def _update_skill_estimate(self, student: dict[str, Any], skill: str, correct: bool) -> float:
        current = float(student.get("skills", {}).get(skill, 0.30))
        delta = 0.18 if correct else -0.10
        updated = max(0.05, min(0.98, current + delta))
        student.setdefault("skills", {})[skill] = round(updated, 3)
        return round(updated, 3)

    def _update_diagnostic_summary(self, student: dict[str, Any], student_id: str) -> list[dict[str, Any]]:
        answers = student.get("diagnostic_answers", {})
        requested = student.get("last_diagnostic_question_ids", [])
        if requested and len(answers) >= len(requested):
            correct_count = sum(1 for entry in answers.values() if entry.get("correct"))
            student["diagnostic_completed"] = True
            student["pretest_score"] = round(correct_count / max(len(requested), 1), 3)
            self._award_badge(student_id, "diagnostic_complete")
        return self._gamification_entry(student_id).get("badges", [])

    def evaluate_answer(
        self,
        student_id: str,
        question_id: str,
        answer: Any,
        *,
        self_assessment: float | None = None,
    ) -> dict[str, Any]:
        student = self._student(student_id)
        question = self.question_bank.get(question_id)
        if not question:
            raise KeyError(f"Unknown diagnostic question: {question_id}")

        normalized_answer = _normalize_text(answer)
        correct = normalized_answer == _normalize_text(question["correct_answer"])
        skill_estimate = self._update_skill_estimate(student, question["skill"], correct)
        attempt_entry = student.setdefault("question_attempts", {}).setdefault(
            question_id,
            {"attempts": 0},
        )
        attempt_entry["attempts"] = int(attempt_entry.get("attempts", 0)) + 1
        attempt_entry["last_answer"] = str(answer)
        attempt_entry["correct"] = correct
        attempt_entry["updated_at"] = time.time()

        student.setdefault("diagnostic_answers", {})[question_id] = {
            "correct": correct,
            "answer": str(answer),
            "updated_at": time.time(),
        }
        if self_assessment is not None:
            student.setdefault("learning_preferences", {})["self_assessment"] = float(self_assessment)

        remediation_node_id = question.get("remediation_node_id", "")
        if remediation_node_id and remediation_node_id in self.curriculum_nodes:
            node_progress = student.setdefault("node_progress", {})
            progress_entry = self._node_progress_snapshot(student, remediation_node_id)
            self._touch_progress_entry(progress_entry)
            current_mastery = float(progress_entry.get("mastery_score", 0.0) or 0.0)
            if correct:
                progress_entry["mastery_score"] = round(
                    min(max(current_mastery + 0.22, 0.82), 0.98),
                    3,
                )
            else:
                progress_entry["mastery_score"] = round(
                    max(current_mastery - 0.05, 0.0),
                    3,
                )
            progress_entry["source"] = "diagnostic"
            progress_entry["updated_at"] = time.time()
            self._schedule_review(
                progress_entry,
                successful=correct,
                confidence=0.88 if correct else 0.35,
            )
            if correct and progress_entry["mastery_score"] >= MASTERY_THRESHOLD:
                progress_entry["completed"] = True
                self._mark_mastery_timestamp(progress_entry)
                completed_nodes = student.setdefault("completed_nodes", [])
                if remediation_node_id not in completed_nodes:
                    completed_nodes.append(remediation_node_id)
            node_progress[remediation_node_id] = progress_entry

        if correct:
            self._award_points(student_id, 12, f"correct_answer:{question_id}")
        else:
            self._award_points(student_id, 4, f"attempted_answer:{question_id}")
            remediation_queue = student.setdefault("needs_remediation", [])
            remediation_node = remediation_node_id
            if remediation_node and remediation_node not in remediation_queue:
                remediation_queue.append(remediation_node)

        self._record_performance_event(
            student,
            node_id=remediation_node_id or question.get("skill", "diagnostic"),
            correct=correct,
            event_type="diagnostic_answer",
            metadata={"question_id": question_id},
        )

        misconception_hits = self._record_misconceptions(student, answer)
        if remediation_node_id:
            self._resolve_misconceptions_for_node(
                student,
                remediation_node_id,
                successful=correct and float(
                    (student.get("node_progress", {}) or {}).get(remediation_node_id, {}).get("mastery_score", 0.0) or 0.0
                ) >= MASTERY_THRESHOLD,
                ignored=misconception_hits,
            )
        student["persona"] = self._classify_persona(student)
        difficulty_profile = self._update_difficulty_profile(student)
        badges = self._update_diagnostic_summary(student, student_id)
        student["updated_at"] = time.time()
        self._synchronize_completed_nodes(student)
        self._recalculate_milestones(student_id, student)
        route = self.get_personalized_route(student_id, persist=False)

        self.diagnostic_state.setdefault("events", []).append({
            "student_id": student_id,
            "question_id": question_id,
            "correct": correct,
            "skill": question["skill"],
            "answer": str(answer),
            "created_at": time.time(),
        })
        self.diagnostic_state["events"] = self.diagnostic_state["events"][-500:]

        self._save_progress()
        self._save_diagnostics()
        self._save_gamification()
        self._sync_student_profile(student_id)

        remediation_node = self.curriculum_nodes.get(remediation_node_id, {})
        feedback_structured = self._structured_feedback(question, answer, correct)
        feedback = "\n".join(
            f"{idx}. {step}"
            for idx, step in enumerate(feedback_structured["steps"], start=1)
        )

        return {
            "correcto": correct,
            "feedback": feedback,
            "feedback_steps": feedback_structured["steps"],
            "hint": question["hint"],
            "explicacion": question["explanation"],
            "skill": question["skill"],
            "skill_estimate": skill_estimate,
            "persona": student.get("persona", "beginner"),
            "difficulty_profile": difficulty_profile,
            "misconceptions": misconception_hits or feedback_structured["misconceptions"],
            "recommended_remediation": {
                "node_id": remediation_node.get("id", ""),
                "title": remediation_node.get("title", ""),
            },
            "route_preview": route,
            "gamification": {
                "points": self._gamification_entry(student_id).get("points", 0),
                "badges": badges,
            },
        }

    def _recalculate_milestones(self, student_id: str, student: dict[str, Any]) -> None:
        completed = set(student.get("completed_nodes", []))
        unlocked = set(student.get("milestones_unlocked", []))
        for milestone in self._milestone_status(completed):
            if milestone["unlocked"] and milestone["id"] not in unlocked:
                unlocked.add(milestone["id"])
                self._award_badge(student_id, milestone["id"])
                self._award_points(student_id, 25, f"milestone:{milestone['id']}")
        student["milestones_unlocked"] = sorted(unlocked)

    def save_progress(
        self,
        student_id: str,
        node_id: str,
        *,
        question_id: str | None = None,
        correct: bool | None = None,
        mastery_score: float | None = None,
        completed: bool = False,
        time_spent_seconds: float | None = None,
        reflection: str = "",
    ) -> dict[str, Any]:
        student = self._student(student_id)
        node = self.curriculum_nodes.get(node_id)
        if not node:
            raise KeyError(f"Unknown curriculum node: {node_id}")

        if mastery_score is not None:
            current_skill = float(student.get("skills", {}).get(node["skill"], 0.30))
            blended = max(current_skill, min(float(mastery_score), 1.0))
            student.setdefault("skills", {})[node["skill"]] = round(blended, 3)

        effective_mastery = float(mastery_score if mastery_score is not None else 0.0)
        should_complete = effective_mastery >= MASTERY_THRESHOLD
        node_progress = student.setdefault("node_progress", {})
        progress_entry = self._node_progress_snapshot(student, node_id)
        self._touch_progress_entry(progress_entry)
        progress_entry["mastery_score"] = round(
            max(float(progress_entry.get("mastery_score", 0.0)), float(mastery_score or 0.0)),
            3,
        )
        progress_entry["completed"] = bool(progress_entry.get("completed")) or should_complete
        if progress_entry["completed"] and progress_entry["mastery_score"] >= MASTERY_THRESHOLD:
            self._mark_mastery_timestamp(progress_entry)
        progress_entry["source"] = "manual_progress"
        progress_entry["updated_at"] = time.time()
        self._schedule_review(
            progress_entry,
            successful=bool(correct if correct is not None else should_complete),
            confidence=max(progress_entry["mastery_score"], 0.4),
        )
        node_progress[node_id] = progress_entry

        completed_nodes = student.setdefault("completed_nodes", [])
        if should_complete and node_id not in completed_nodes:
            completed_nodes.append(node_id)
            self._award_points(student_id, 20, f"completed_node:{node_id}")
        elif not should_complete and node_id in completed_nodes:
            completed_nodes.remove(node_id)

        if node_id in student.get("needs_remediation", []) and should_complete:
            student["needs_remediation"] = [item for item in student["needs_remediation"] if item != node_id]

        if question_id:
            student.setdefault("question_attempts", {}).setdefault(question_id, {})["linked_node_id"] = node_id
        if correct is not None:
            self._update_skill_estimate(student, node["skill"], bool(correct))
        self._record_performance_event(
            student,
            node_id=node_id,
            correct=bool(correct if correct is not None else should_complete),
            event_type="manual_progress",
            metadata={"question_id": question_id or ""},
        )

        misconception_hits = self._record_misconceptions(student, reflection)
        self._resolve_misconceptions_for_node(
            student,
            node_id,
            successful=should_complete or bool(correct),
            ignored=misconception_hits,
        )
        student["persona"] = self._classify_persona(student)
        difficulty_profile = self._update_difficulty_profile(student)
        student["last_recommended_node"] = node_id
        student["updated_at"] = time.time()
        student.setdefault("lesson_history", []).append({
            "node_id": node_id,
            "question_id": question_id,
            "correct": correct,
            "mastery_score": mastery_score,
            "completed": should_complete,
            "time_spent_seconds": time_spent_seconds,
            "reflection": reflection[:500],
            "created_at": time.time(),
        })
        student["lesson_history"] = student["lesson_history"][-200:]

        self._synchronize_completed_nodes(student)
        self._recalculate_milestones(student_id, student)
        route = self.get_personalized_route(student_id, persist=False)

        self._save_progress()
        self._save_gamification()
        self._sync_student_profile(student_id)
        return {
            "student_id": student_id,
            "saved": True,
            "completed_nodes": student["completed_nodes"],
            "milestones_unlocked": student["milestones_unlocked"],
            "gamification": self._gamification_entry(student_id),
            "persona": student.get("persona", "beginner"),
            "difficulty_profile": difficulty_profile,
            "misconceptions": misconception_hits,
            "mastery_threshold": MASTERY_THRESHOLD,
            "route": route,
        }

    def record_chat_learning_signal(
        self,
        student_id: str,
        topic: str,
        *,
        passed_socratic: bool,
        response_quality: str = "",
        engine_status: str = "",
        wolfram_used: bool = False,
        context_retrieved: bool = False,
        user_text: str = "",
    ) -> dict[str, Any]:
        student = self._student(student_id)
        node_id = self.topic_to_node.get(_normalize_text(topic), "")
        if not node_id or node_id not in self.curriculum_nodes:
            return {
                "recorded": False,
                "reason": "topic_not_mapped",
            }

        node = self.curriculum_nodes[node_id]
        node_progress = student.setdefault("node_progress", {})
        current_progress = self._node_progress_snapshot(student, node_id)
        self._touch_progress_entry(current_progress)
        quality_normalized = (response_quality or "").strip().lower()
        is_solid = quality_normalized in {"solida", "solid", "strong"}
        is_degraded = (engine_status or "").endswith("_LOCAL") or engine_status in {
            "LOCAL_FALLBACK",
            "RATE_LIMITED_LOCAL",
            "BACKPRESSURE_LOCAL",
            "CIRCUIT_BREAKER_LOCAL",
        }

        progress_delta = 0.12 if passed_socratic and is_solid else 0.05 if passed_socratic else -0.03
        if is_degraded:
            progress_delta *= 0.6
        if wolfram_used:
            progress_delta += 0.01
        if context_retrieved:
            progress_delta += 0.01

        updated_progress = max(0.0, min(float(current_progress.get("mastery_score", 0.0)) + progress_delta, 0.99))
        current_progress["mastery_score"] = round(updated_progress, 3)
        current_progress["source"] = "chat_signal"
        current_progress["updated_at"] = time.time()
        self._schedule_review(
            current_progress,
            successful=passed_socratic,
            confidence=max(current_progress["mastery_score"], 0.35),
        )
        current_progress["completed"] = bool(current_progress.get("completed", False)) or (
            passed_socratic and not is_degraded and current_progress["mastery_score"] >= MASTERY_THRESHOLD
        )
        if current_progress["completed"] and current_progress["mastery_score"] >= MASTERY_THRESHOLD:
            self._mark_mastery_timestamp(current_progress)

        node_progress[node_id] = current_progress
        current_skill = float(student.get("skills", {}).get(node["skill"], 0.30))
        skill_delta = 0.04 if passed_socratic and is_solid else 0.02 if passed_socratic else -0.03
        student.setdefault("skills", {})[node["skill"]] = round(
            max(0.05, min(current_skill + skill_delta, 0.98)),
            3,
        )
        if passed_socratic:
            self._award_points(student_id, 3 if is_solid else 2, f"chat_signal:{node_id}")
        else:
            remediation_queue = student.setdefault("needs_remediation", [])
            if node_id not in remediation_queue:
                remediation_queue.append(node_id)
        if current_progress["completed"]:
            completed_nodes = student.setdefault("completed_nodes", [])
            if node_id not in completed_nodes:
                completed_nodes.append(node_id)
        self._record_performance_event(
            student,
            node_id=node_id,
            correct=passed_socratic,
            event_type="chat_signal",
            metadata={"response_quality": response_quality[:40]},
        )
        misconception_hits = self._record_misconceptions(student, user_text or topic)
        self._resolve_misconceptions_for_node(
            student,
            node_id,
            successful=passed_socratic and current_progress["mastery_score"] >= MASTERY_THRESHOLD,
            ignored=misconception_hits,
        )
        student["persona"] = self._classify_persona(student)
        difficulty_profile = self._update_difficulty_profile(student)

        student.setdefault("chat_events", []).append({
            "topic": topic,
            "node_id": node_id,
            "passed_socratic": passed_socratic,
            "response_quality": response_quality,
            "engine_status": engine_status,
            "wolfram_used": wolfram_used,
            "context_retrieved": context_retrieved,
            "mastery_score": current_progress["mastery_score"],
            "misconceptions": misconception_hits,
            "created_at": time.time(),
        })
        student["chat_events"] = student["chat_events"][-200:]
        student["updated_at"] = time.time()

        self._synchronize_completed_nodes(student)
        self._recalculate_milestones(student_id, student)
        route = self.get_personalized_route(student_id, persist=False)
        kpis = self.get_learning_kpis(student_id)
        self._save_progress()
        self._save_gamification()
        self._sync_student_profile(student_id)

        return {
            "recorded": True,
            "node_id": node_id,
            "mastery_score": current_progress["mastery_score"],
            "persona": student.get("persona", "beginner"),
            "difficulty_profile": difficulty_profile,
            "misconceptions": misconception_hits,
            "route": route,
            "kpis": kpis,
        }

    def record_assessment_score(
        self,
        student_id: str,
        *,
        assessment_type: str,
        score: float,
        label: str = "",
        notes: str = "",
    ) -> dict[str, Any]:
        student = self._student(student_id)
        normalized_type = (assessment_type or "").strip().lower()
        normalized_score = max(0.0, min(float(score), 1.0))
        if normalized_type == "pretest":
            student["pretest_score"] = round(normalized_score, 3)
        elif normalized_type == "posttest":
            student["posttest_score"] = round(normalized_score, 3)
        else:
            raise KeyError(f"Unknown assessment type: {assessment_type}")

        student.setdefault("assessment_history", []).append({
            "assessment_type": normalized_type,
            "score": round(normalized_score, 3),
            "label": label[:120],
            "notes": notes[:500],
            "created_at": time.time(),
        })
        student["assessment_history"] = student["assessment_history"][-50:]
        student["persona"] = self._classify_persona(student)
        difficulty_profile = self._update_difficulty_profile(student)
        if normalized_type == "posttest":
            self._award_points(student_id, 15, "posttest_recorded")
        student["updated_at"] = time.time()

        self._save_progress()
        self._save_gamification()
        self._sync_student_profile(student_id)
        return {
            "student_id": student_id,
            "assessment_type": normalized_type,
            "score": round(normalized_score, 3),
            "persona": student.get("persona", "beginner"),
            "difficulty_profile": difficulty_profile,
            "kpis": self.get_learning_kpis(student_id),
        }

    def get_review_queue(self, student_id: str) -> list[dict[str, Any]]:
        student = self._student(student_id)
        now = time.time()
        rows = []
        for node_id, entry in (student.get("node_progress", {}) or {}).items():
            next_review_at = float(entry.get("next_review_at", 0.0) or 0.0)
            if next_review_at <= 0:
                continue
            due = next_review_at <= now
            rows.append({
                "node_id": node_id,
                "title": self.curriculum_nodes.get(node_id, {}).get("title", node_id),
                "due": due,
                "next_review_at": next_review_at,
                "retention_score": round(float(entry.get("retention_score", 0.0) or 0.0), 3),
                "review_count": int(entry.get("review_count", 0) or 0),
                "mastery_score": round(float(entry.get("mastery_score", 0.0) or 0.0), 3),
            })
        rows.sort(key=lambda item: (not item["due"], item["next_review_at"], item["title"]))
        return rows

    def _student_learning_metrics(
        self,
        student_id: str,
        *,
        experiment_name: str = DEFAULT_GAMIFICATION_EXPERIMENT,
    ) -> dict[str, Any]:
        student = self._student(student_id)
        kpis = self.get_learning_kpis(student_id)
        assignment = self.get_experiment_assignment(student_id, experiment_name=experiment_name)
        module = self._current_module(student)
        dominant_misconception = self._dominant_misconception(student)
        learning_gain = kpis.get("improvement")
        time_to_mastery_seconds = self._average_time_to_mastery_seconds(student)
        retention_score = self._average_retention_score(student)
        error_reduction_rate = self._error_reduction_rate(student)
        misconception_resolution_rate = self._misconception_resolution_rate(student)
        cohort_key = "|".join([
            str(kpis.get("persona", "beginner")),
            dominant_misconception,
            module["node_id"],
            assignment["variant"],
        ])
        return {
            "student_id": student_id,
            "cohort_key": cohort_key,
            "persona": kpis.get("persona", "beginner"),
            "dominant_misconception": dominant_misconception,
            "module_id": module["node_id"],
            "module_title": module["title"],
            "variant": assignment["variant"],
            "learning_gain": learning_gain,
            "time_to_mastery_seconds": time_to_mastery_seconds,
            "retention_score": retention_score,
            "error_reduction_rate": error_reduction_rate,
            "misconception_resolution_rate": misconception_resolution_rate,
            "recommended_difficulty": (kpis.get("difficulty_profile") or {}).get("recommended_difficulty", "medium"),
            "due_review_count": kpis.get("due_review_count", 0),
        }

    def _rebuild_learning_cohorts(
        self,
        student_rows: list[dict[str, Any]],
        *,
        experiment_name: str = DEFAULT_GAMIFICATION_EXPERIMENT,
    ) -> dict[str, list[str]]:
        cohorts: dict[str, list[str]] = {}
        for row in student_rows:
            cohorts.setdefault(row["cohort_key"], []).append(row["student_id"])
        ordered = {
            cohort_key: sorted(student_ids)
            for cohort_key, student_ids in sorted(cohorts.items())
        }
        self.progress_state.setdefault("learning_cohorts", {})[experiment_name] = ordered
        return ordered

    def _experiment_status(self, experiment_name: str = DEFAULT_GAMIFICATION_EXPERIMENT) -> dict[str, Any]:
        assignments = []
        for student_id in sorted((self.progress_state.get("students", {}) or {}).keys()):
            assignment = self.get_experiment_assignment(student_id, experiment_name=experiment_name)
            if assignment:
                assignments.append(assignment)

        if not assignments:
            return {
                "experiment_name": experiment_name,
                "start_at": None,
                "end_at": None,
                "metric": DEFAULT_EXPERIMENT_PRIMARY_METRIC,
                "min_sample": DEFAULT_EXPERIMENT_MIN_SAMPLE,
                "sample_size": 0,
                "window_days": DEFAULT_EXPERIMENT_WINDOW_DAYS,
                "sample_ready": False,
                "window_complete": False,
                "evaluation_ready": False,
                "seconds_until_ready": None,
            }

        start_at = min(float(item.get("start_at", item.get("assigned_at", 0.0)) or 0.0) for item in assignments)
        end_at = max(float(item.get("end_at", start_at)) or start_at for item in assignments)
        min_sample = max(int(assignments[0].get("min_sample", DEFAULT_EXPERIMENT_MIN_SAMPLE) or DEFAULT_EXPERIMENT_MIN_SAMPLE), 1)
        window_days = max(int(assignments[0].get("window_days", DEFAULT_EXPERIMENT_WINDOW_DAYS) or DEFAULT_EXPERIMENT_WINDOW_DAYS), 1)
        metric = str(assignments[0].get("metric", DEFAULT_EXPERIMENT_PRIMARY_METRIC))
        now = time.time()
        sample_size = len(assignments)
        sample_ready = sample_size >= min_sample
        window_complete = now >= end_at
        seconds_until_ready = max(end_at - now, 0.0) if not window_complete else 0.0
        return {
            "experiment_name": experiment_name,
            "start_at": start_at,
            "end_at": end_at,
            "metric": metric,
            "min_sample": min_sample,
            "sample_size": sample_size,
            "window_days": window_days,
            "sample_ready": sample_ready,
            "window_complete": window_complete,
            "evaluation_ready": sample_ready and window_complete,
            "seconds_until_ready": round(seconds_until_ready, 3),
        }

    def _recommend_optimization_actions(
        self,
        *,
        learning_gain: float | None,
        time_to_mastery_seconds: float | None,
        retention_score: float | None,
        error_reduction_rate: float | None,
        misconception_resolution_rate: float | None,
    ) -> list[str]:
        actions: list[str] = []
        if learning_gain is None or learning_gain < 0.18:
            actions.append("increase_scaffolding")
        if time_to_mastery_seconds is not None and time_to_mastery_seconds > 3.5 * 24 * 60 * 60:
            actions.append("reduce_difficulty")
        if retention_score is not None and retention_score < 0.65:
            actions.append("increase_review_frequency")
        if error_reduction_rate is None or error_reduction_rate < 0.25:
            actions.append("inject_remediation_content")
        if misconception_resolution_rate is None or misconception_resolution_rate < 0.55:
            actions.append("inject_remediation_content")
        if not actions:
            actions.append("keep_current_strategy")
        return list(dict.fromkeys(actions))

    def _recommendation_text(self, actions: list[str]) -> str:
        if "keep_current_strategy" in actions and len(actions) == 1:
            return "Mantener la estrategia actual: la cohorte muestra senales saludables de aprendizaje."
        recommendations = []
        if "increase_scaffolding" in actions:
            recommendations.append("aumentar andamiaje")
        if "reduce_difficulty" in actions:
            recommendations.append("bajar dificultad temporalmente")
        if "increase_review_frequency" in actions:
            recommendations.append("acortar intervalos de repaso")
        if "inject_remediation_content" in actions:
            recommendations.append("inyectar remediacion guiada")
        return "Recomendacion: " + ", ".join(recommendations) + "."

    def _apply_optimization_to_student(self, student: dict[str, Any], actions: list[str]) -> bool:
        profile = student.setdefault("optimization_profile", {})
        before = dict(profile)
        profile["scaffolding"] = "high" if "increase_scaffolding" in actions else "standard"
        profile["difficulty_adjustment"] = "easier" if "reduce_difficulty" in actions else "stable"
        profile["remediation_boost"] = "inject_remediation_content" in actions
        profile["review_intensity"] = "high" if "increase_review_frequency" in actions else "standard"
        profile["last_actions"] = list(actions)
        profile["last_updated_at"] = time.time()
        return profile != before

    def get_learning_kpis(self, student_id: str) -> dict[str, Any]:
        student = self._student(student_id)
        completed_nodes = set(self._synchronize_completed_nodes(student))
        total_nodes = len(self.curriculum["nodes"])
        node_progress = student.get("node_progress", {}) or {}
        average_node_progress = (
            sum(float(item.get("mastery_score", 0.0)) for item in node_progress.values()) / max(len(node_progress), 1)
            if node_progress else 0.0
        )
        milestones = self._milestone_status(completed_nodes)
        unlocked_milestones = [item for item in milestones if item.get("unlocked")]
        overall_mastery = round(
            sum(float(value) for value in student.get("skills", {}).values()) / max(len(student.get("skills", {})), 1),
            3,
        )
        pretest = student.get("pretest_score")
        posttest = student.get("posttest_score")
        improvement = None
        if pretest is not None and posttest is not None:
            improvement = round(float(posttest) - float(pretest), 3)
        experiment = self.get_experiment_assignment(student_id)
        review_queue = self.get_review_queue(student_id)
        current_module = self._current_module(student)
        dominant_misconception = self._dominant_misconception(student)

        return {
            "student_id": student_id,
            "diagnostic_completed": bool(student.get("diagnostic_completed")),
            "pretest_score": pretest,
            "posttest_score": posttest,
            "improvement": improvement,
            "learning_gain": improvement,
            "overall_mastery": overall_mastery,
            "average_node_progress": round(average_node_progress, 3),
            "completed_nodes": len(completed_nodes),
            "total_nodes": total_nodes,
            "completion_rate": round(len(completed_nodes) / max(total_nodes, 1), 3),
            "milestones_unlocked": len(unlocked_milestones),
            "milestones_total": len(milestones),
            "points": int(self._gamification_entry(student_id).get("points", 0)),
            "badges": len(self._gamification_entry(student_id).get("badges", [])),
            "chat_learning_events": len(student.get("chat_events", [])),
            "experiment": experiment,
            "persona": student.get("persona", "beginner"),
            "difficulty_profile": dict(student.get("difficulty_profile", {})),
            "optimization_profile": dict(student.get("optimization_profile", {})),
            "misconceptions": dict(student.get("misconceptions", {})),
            "dominant_misconception": dominant_misconception,
            "current_module": current_module,
            "mastery_threshold": MASTERY_THRESHOLD,
            "average_retention_score": self._average_retention_score(student),
            "average_time_to_mastery_seconds": self._average_time_to_mastery_seconds(student),
            "error_reduction_rate": self._error_reduction_rate(student),
            "misconception_resolution_rate": self._misconception_resolution_rate(student),
            "due_review_count": sum(1 for item in review_queue if item["due"]),
            "review_queue": review_queue[:10],
            "assessment_history": list(student.get("assessment_history", []))[-5:],
            "node_progress": [
                {
                    "node_id": node_id,
                    "title": self.curriculum_nodes.get(node_id, {}).get("title", node_id),
                    "mastery_score": round(float(entry.get("mastery_score", 0.0)), 3),
                    "completed": bool(entry.get("completed", False)),
                    "source": entry.get("source", ""),
                }
                for node_id, entry in sorted(
                    node_progress.items(),
                    key=lambda item: (-float(item[1].get("mastery_score", 0.0)), item[0]),
                )
            ][:8],
        }

    def get_cohort_report(
        self,
        *,
        experiment_name: str = DEFAULT_GAMIFICATION_EXPERIMENT,
    ) -> dict[str, Any]:
        students = self.progress_state.get("students", {}) or {}
        student_rows: list[dict[str, Any]] = []
        module_aggregate: dict[str, dict[str, Any]] = {
            node["id"]: {
                "node_id": node["id"],
                "title": node["title"],
                "level": node["level"],
                "skill": node["skill"],
                "started_count": 0,
                "completed_count": 0,
                "total_mastery": 0.0,
                "variant_counts": {},
            }
            for node in self.curriculum["nodes"]
        }

        for student_id in sorted(students.keys()):
            student = self._student(student_id)
            kpis = self.get_learning_kpis(student_id)
            route = self.get_personalized_route(student_id, persist=False)
            metrics = self._student_learning_metrics(student_id, experiment_name=experiment_name)
            assignment = self.get_experiment_assignment(student_id, experiment_name=experiment_name)

            row = {
                "student_id": student_id,
                "cohort_key": metrics["cohort_key"],
                "target_level": student.get("target_level", "beginner"),
                "current_level": route.get("current_level", "beginner"),
                "persona": metrics["persona"],
                "dominant_misconception": metrics["dominant_misconception"],
                "module_id": metrics["module_id"],
                "module_title": metrics["module_title"],
                "diagnostic_completed": bool(student.get("diagnostic_completed")),
                "pretest_score": student.get("pretest_score"),
                "posttest_score": student.get("posttest_score"),
                "improvement": metrics["learning_gain"],
                "completion_rate": kpis.get("completion_rate"),
                "overall_mastery": kpis.get("overall_mastery"),
                "due_review_count": metrics["due_review_count"],
                "recommended_difficulty": metrics["recommended_difficulty"],
                "average_retention_score": metrics["retention_score"],
                "average_time_to_mastery_seconds": metrics["time_to_mastery_seconds"],
                "error_reduction_rate": metrics["error_reduction_rate"],
                "misconception_resolution_rate": metrics["misconception_resolution_rate"],
                "points": kpis.get("points"),
                "badges": kpis.get("badges"),
                "milestones_unlocked": kpis.get("milestones_unlocked"),
                "experiment_variant": assignment["variant"],
                "chat_learning_events": kpis.get("chat_learning_events"),
            }
            student_rows.append(row)

            variant = assignment["variant"]
            for node_id, progress in (student.get("node_progress", {}) or {}).items():
                aggregate = module_aggregate.get(node_id)
                if not aggregate:
                    continue
                aggregate["started_count"] += 1
                aggregate["total_mastery"] += float(progress.get("mastery_score", 0.0))
                if progress.get("completed"):
                    aggregate["completed_count"] += 1
                aggregate["variant_counts"][variant] = aggregate["variant_counts"].get(variant, 0) + 1

        student_count = len(student_rows)
        variant_breakdown: dict[str, dict[str, Any]] = {}
        target_level_breakdown: dict[str, dict[str, Any]] = {}
        for row in student_rows:
            variant_bucket = variant_breakdown.setdefault(
                row["experiment_variant"],
                {"student_count": 0, "diagnostic_completed": 0, "completion_total": 0.0, "improvement_total": 0.0, "improvement_count": 0},
            )
            variant_bucket["student_count"] += 1
            variant_bucket["diagnostic_completed"] += 1 if row["diagnostic_completed"] else 0
            variant_bucket["completion_total"] += float(row["completion_rate"] or 0.0)
            if row["improvement"] is not None:
                variant_bucket["improvement_total"] += float(row["improvement"])
                variant_bucket["improvement_count"] += 1

            target_bucket = target_level_breakdown.setdefault(
                row["target_level"],
                {"student_count": 0, "completion_total": 0.0, "mastery_total": 0.0},
            )
            target_bucket["student_count"] += 1
            target_bucket["completion_total"] += float(row["completion_rate"] or 0.0)
            target_bucket["mastery_total"] += float(row["overall_mastery"] or 0.0)

        variant_rows = []
        for variant, bucket in sorted(variant_breakdown.items()):
            count = max(bucket["student_count"], 1)
            improvement_count = max(bucket["improvement_count"], 1)
            variant_rows.append({
                "variant": variant,
                "student_count": bucket["student_count"],
                "diagnostic_completed_rate": round(bucket["diagnostic_completed"] / count, 3),
                "average_completion_rate": round(bucket["completion_total"] / count, 3),
                "average_improvement": round(bucket["improvement_total"] / improvement_count, 3)
                if bucket["improvement_count"] else None,
            })

        target_level_rows = []
        for target_level, bucket in sorted(target_level_breakdown.items()):
            count = max(bucket["student_count"], 1)
            target_level_rows.append({
                "target_level": target_level,
                "student_count": bucket["student_count"],
                "average_completion_rate": round(bucket["completion_total"] / count, 3),
                "average_overall_mastery": round(bucket["mastery_total"] / count, 3),
            })

        module_rows = []
        for aggregate in module_aggregate.values():
            started_count = aggregate["started_count"]
            module_rows.append({
                "node_id": aggregate["node_id"],
                "title": aggregate["title"],
                "level": aggregate["level"],
                "skill": aggregate["skill"],
                "started_count": started_count,
                "completed_count": aggregate["completed_count"],
                "completion_rate": round(aggregate["completed_count"] / max(started_count, 1), 3),
                "average_mastery": round(aggregate["total_mastery"] / max(started_count, 1), 3) if started_count else 0.0,
                "variant_counts": aggregate["variant_counts"],
            })
        module_rows.sort(key=lambda item: (-item["started_count"], item["level"], item["title"]))

        overall_improvement_rows = [row["improvement"] for row in student_rows if row["improvement"] is not None]
        overall_completion = [float(row["completion_rate"] or 0.0) for row in student_rows]
        overall_mastery = [float(row["overall_mastery"] or 0.0) for row in student_rows]
        overall_due_reviews = [int(row["due_review_count"] or 0) for row in student_rows]
        overall_retention = [float(row["average_retention_score"] or 0.0) for row in student_rows if row["average_retention_score"] is not None]
        diagnostic_completed_count = sum(1 for row in student_rows if row["diagnostic_completed"])
        learning_cohorts = self._rebuild_learning_cohorts(student_rows, experiment_name=experiment_name)

        payload = {
            "generated_at": time.time(),
            "experiment_name": experiment_name,
            "experiment_status": self._experiment_status(experiment_name),
            "summary": {
                "student_count": student_count,
                "diagnostic_completed_rate": round(diagnostic_completed_count / max(student_count, 1), 3),
                "average_completion_rate": round(sum(overall_completion) / max(student_count, 1), 3) if student_rows else 0.0,
                "average_overall_mastery": round(sum(overall_mastery) / max(student_count, 1), 3) if student_rows else 0.0,
                "average_improvement": round(sum(overall_improvement_rows) / len(overall_improvement_rows), 3) if overall_improvement_rows else None,
                "average_due_reviews": round(sum(overall_due_reviews) / max(student_count, 1), 3) if student_rows else 0.0,
                "average_retention_score": round(sum(overall_retention) / len(overall_retention), 3) if overall_retention else None,
            },
            "variants": variant_rows,
            "target_levels": target_level_rows,
            "module_comparison": module_rows,
            "learning_cohorts": learning_cohorts,
            "students": student_rows,
        }
        self._save_progress()
        return payload

    def export_cohort_report(
        self,
        *,
        experiment_name: str = DEFAULT_GAMIFICATION_EXPERIMENT,
        json_path: Path = LEARNING_COHORT_REPORT_PATH,
        csv_path: Path = LEARNING_COHORT_STUDENTS_CSV_PATH,
    ) -> dict[str, Any]:
        report = self.get_cohort_report(experiment_name=experiment_name)
        write_json_atomic(Path(json_path), report, indent=2, ensure_ascii=False)

        csv_buffer = StringIO()
        fieldnames = [
            "student_id",
            "cohort_key",
            "target_level",
            "current_level",
            "persona",
            "dominant_misconception",
            "module_id",
            "module_title",
            "diagnostic_completed",
            "pretest_score",
            "posttest_score",
            "improvement",
            "completion_rate",
            "overall_mastery",
            "due_review_count",
            "recommended_difficulty",
            "average_retention_score",
            "average_time_to_mastery_seconds",
            "error_reduction_rate",
            "misconception_resolution_rate",
            "points",
            "badges",
            "milestones_unlocked",
            "experiment_variant",
            "chat_learning_events",
        ]
        writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
        writer.writeheader()
        for row in report["students"]:
            writer.writerow(row)
        write_text_atomic(Path(csv_path), csv_buffer.getvalue(), encoding="utf-8")

        return {
            "report": report,
            "json_path": str(Path(json_path)),
            "csv_path": str(Path(csv_path)),
        }

    def get_learning_insights(
        self,
        *,
        experiment_name: str = DEFAULT_GAMIFICATION_EXPERIMENT,
        apply_optimization: bool = True,
    ) -> dict[str, Any]:
        students = self.progress_state.get("students", {}) or {}
        student_rows = [
            self._student_learning_metrics(student_id, experiment_name=experiment_name)
            for student_id in sorted(students.keys())
        ]
        learning_cohorts = self._rebuild_learning_cohorts(student_rows, experiment_name=experiment_name)
        experiment_status = self._experiment_status(experiment_name)

        grouped: dict[str, dict[str, Any]] = {}
        for row in student_rows:
            bucket = grouped.setdefault(
                row["cohort_key"],
                {
                    "cohort_key": row["cohort_key"],
                    "persona": row["persona"],
                    "dominant_misconception": row["dominant_misconception"],
                    "module_id": row["module_id"],
                    "module_title": row["module_title"],
                    "variant": row["variant"],
                    "student_ids": [],
                    "learning_gain_rows": [],
                    "time_to_mastery_rows": [],
                    "retention_rows": [],
                    "error_reduction_rows": [],
                    "misconception_resolution_rows": [],
                },
            )
            bucket["student_ids"].append(row["student_id"])
            if row["learning_gain"] is not None:
                bucket["learning_gain_rows"].append(float(row["learning_gain"]))
            if row["time_to_mastery_seconds"] is not None:
                bucket["time_to_mastery_rows"].append(float(row["time_to_mastery_seconds"]))
            if row["retention_score"] is not None:
                bucket["retention_rows"].append(float(row["retention_score"]))
            if row["error_reduction_rate"] is not None:
                bucket["error_reduction_rows"].append(float(row["error_reduction_rate"]))
            if row["misconception_resolution_rate"] is not None:
                bucket["misconception_resolution_rows"].append(float(row["misconception_resolution_rate"]))

        changed_students: set[str] = set()
        cohort_rows: list[dict[str, Any]] = []
        for bucket in grouped.values():
            learning_gain_avg = round(sum(bucket["learning_gain_rows"]) / len(bucket["learning_gain_rows"]), 3) if bucket["learning_gain_rows"] else None
            time_to_mastery_avg = round(sum(bucket["time_to_mastery_rows"]) / len(bucket["time_to_mastery_rows"]), 3) if bucket["time_to_mastery_rows"] else None
            retention_avg = round(sum(bucket["retention_rows"]) / len(bucket["retention_rows"]), 3) if bucket["retention_rows"] else None
            error_reduction_avg = round(sum(bucket["error_reduction_rows"]) / len(bucket["error_reduction_rows"]), 3) if bucket["error_reduction_rows"] else None
            misconception_resolution_avg = round(sum(bucket["misconception_resolution_rows"]) / len(bucket["misconception_resolution_rows"]), 3) if bucket["misconception_resolution_rows"] else None
            actions = self._recommend_optimization_actions(
                learning_gain=learning_gain_avg,
                time_to_mastery_seconds=time_to_mastery_avg,
                retention_score=retention_avg,
                error_reduction_rate=error_reduction_avg,
                misconception_resolution_rate=misconception_resolution_avg,
            )
            recommendation = self._recommendation_text(actions)
            insight = (
                f"{bucket['module_title']} | persona {bucket['persona']} | variante {bucket['variant']} | "
                f"misconception dominante {bucket['dominant_misconception']}."
            )
            if apply_optimization:
                for student_id in bucket["student_ids"]:
                    if self._apply_optimization_to_student(self._student(student_id), actions):
                        changed_students.add(student_id)
            cohort_rows.append({
                "cohort_key": bucket["cohort_key"],
                "student_count": len(bucket["student_ids"]),
                "persona": bucket["persona"],
                "dominant_misconception": bucket["dominant_misconception"],
                "module_id": bucket["module_id"],
                "module_title": bucket["module_title"],
                "variant": bucket["variant"],
                "learning_gain_avg": learning_gain_avg,
                "time_to_mastery_avg_seconds": time_to_mastery_avg,
                "time_to_mastery_avg_days": round(time_to_mastery_avg / (24 * 60 * 60), 3) if time_to_mastery_avg is not None else None,
                "retention_score_avg": retention_avg,
                "error_reduction_rate_avg": error_reduction_avg,
                "misconception_resolution_rate_avg": misconception_resolution_avg,
                "insight": insight,
                "optimization_actions": actions,
                "recommendation": recommendation,
                "evaluation_ready": experiment_status["evaluation_ready"],
            })

        cohort_rows.sort(
            key=lambda item: (
                -(item["student_count"]),
                item.get("learning_gain_avg") is None,
                item.get("learning_gain_avg") or 0.0,
                item["cohort_key"],
            )
        )

        learning_gain_rows = [float(item["learning_gain"]) for item in student_rows if item["learning_gain"] is not None]
        time_to_mastery_rows = [float(item["time_to_mastery_seconds"]) for item in student_rows if item["time_to_mastery_seconds"] is not None]
        retention_rows = [float(item["retention_score"]) for item in student_rows if item["retention_score"] is not None]
        error_reduction_rows = [float(item["error_reduction_rate"]) for item in student_rows if item["error_reduction_rate"] is not None]
        misconception_resolution_rows = [float(item["misconception_resolution_rate"]) for item in student_rows if item["misconception_resolution_rate"] is not None]
        top_recommendation = cohort_rows[0]["recommendation"] if cohort_rows else "Sin datos suficientes."

        payload = {
            "generated_at": time.time(),
            "experiment": experiment_status,
            "summary": {
                "student_count": len(student_rows),
                "cohort_count": len(cohort_rows),
                "learning_gain_avg": round(sum(learning_gain_rows) / len(learning_gain_rows), 3) if learning_gain_rows else None,
                "time_to_mastery_avg_seconds": round(sum(time_to_mastery_rows) / len(time_to_mastery_rows), 3) if time_to_mastery_rows else None,
                "time_to_mastery_avg_days": round((sum(time_to_mastery_rows) / len(time_to_mastery_rows)) / (24 * 60 * 60), 3) if time_to_mastery_rows else None,
                "retention_score_avg": round(sum(retention_rows) / len(retention_rows), 3) if retention_rows else None,
                "error_reduction_rate_avg": round(sum(error_reduction_rows) / len(error_reduction_rows), 3) if error_reduction_rows else None,
                "misconception_resolution_rate_avg": round(sum(misconception_resolution_rows) / len(misconception_resolution_rows), 3) if misconception_resolution_rows else None,
                "top_recommendation": top_recommendation,
            },
            "learning_cohorts": learning_cohorts,
            "cohorts": cohort_rows,
            "students": student_rows,
        }

        self.progress_state.setdefault("experiments", {})[experiment_name] = experiment_status
        if apply_optimization and changed_students:
            for student_id in changed_students:
                self._sync_student_profile(student_id)
        self._save_progress()
        return payload

    def get_personalized_route(self, student_id: str, *, persist: bool = True) -> dict[str, Any]:
        student = self._student(student_id)
        student["persona"] = self._classify_persona(student)
        difficulty_profile = self._update_difficulty_profile(student)
        completed = set(self._synchronize_completed_nodes(student))
        remediation_nodes = list(dict.fromkeys(student.get("needs_remediation", []) + self._analytics_remediation_nodes()))
        review_queue = self.get_review_queue(student_id)
        due_reviews = [item for item in review_queue if item["due"]]
        due_review_ids = [item["node_id"] for item in due_reviews]
        due_review_lookup = {item["node_id"]: item for item in due_reviews}

        unlocked_nodes = [
            node for node in self.curriculum["nodes"]
            if all(self._node_mastered(student, prereq) for prereq in node.get("prerequisites", []))
        ]
        blocked_nodes = [
            node for node in self.curriculum["nodes"]
            if node["id"] not in {item["id"] for item in unlocked_nodes}
        ]
        available_new_nodes = [node for node in unlocked_nodes if node["id"] not in completed]
        available_new_nodes.sort(
            key=lambda node: (
                0 if node["id"] in remediation_nodes else 1,
                0 if float(self._node_progress_snapshot(student, node["id"]).get("mastery_score", 0.0)) > 0 else 1,
                -float(self._node_progress_snapshot(student, node["id"]).get("mastery_score", 0.0)),
                LEVEL_ORDER.get(node["level"], 99),
                -float(1.0 - student.get("skills", {}).get(node["skill"], 0.30)),
                node["title"],
            )
        )

        candidate_nodes: list[dict[str, Any]] = []
        seen_ids: set[str] = set()

        for review_entry in due_reviews:
            node = self.curriculum_nodes.get(review_entry["node_id"])
            if not node or node["id"] in seen_ids:
                continue
            candidate_nodes.append(
                self._route_node_payload(
                    student,
                    node,
                    route_reason="spaced_review_due",
                    review_entry=review_entry,
                )
            )
            seen_ids.add(node["id"])

        for node in available_new_nodes:
            if node["id"] in seen_ids:
                continue
            route_reason = "remediation_priority" if node["id"] in remediation_nodes else "next_mastery_gap"
            candidate_nodes.append(
                self._route_node_payload(
                    student,
                    node,
                    route_reason=route_reason,
                )
            )
            seen_ids.add(node["id"])

        next_node = dict(candidate_nodes[0]) if candidate_nodes else None
        alternative_nodes = [dict(item) for item in candidate_nodes[1:4]]
        milestone_status = self._milestone_status(completed)
        current_level = self._current_level(student)
        profile = self._gamification_entry(student_id)
        overall_mastery = round(
            sum(float(value) for value in student.get("skills", {}).values()) / max(len(student.get("skills", {})), 1),
            3,
        )

        if next_node:
            student["last_recommended_node"] = next_node["id"]

        route = {
            "student_id": student_id,
            "current_level": current_level,
            "overall_mastery": overall_mastery,
            "diagnostic_completed": bool(student.get("diagnostic_completed")),
            "experiment": self.get_experiment_assignment(student_id),
            "persona": student.get("persona", "beginner"),
            "difficulty_profile": difficulty_profile,
            "optimization_profile": dict(student.get("optimization_profile", {})),
            "mastery_threshold": MASTERY_THRESHOLD,
            "recommended_modalities": self._recommended_modalities(student),
            "next_node": next_node,
            "alternative_nodes": alternative_nodes,
            "remediation_queue": remediation_nodes,
            "review_queue": review_queue[:8],
            "due_review_count": len(due_reviews),
            "review_due_now": bool(due_reviews),
            "milestones": milestone_status,
            "knowledge_graph": {
                "unlocked_count": len(unlocked_nodes),
                "blocked_count": len(blocked_nodes),
                "blocked_nodes": [
                    {
                        "node_id": node["id"],
                        "title": node["title"],
                        "blocked_by": [
                            item["title"]
                            for item in self._node_prerequisite_status(student, node)
                            if not item["mastered"]
                        ],
                    }
                    for node in blocked_nodes[:6]
                ],
            },
            "gamification": {
                "points": profile.get("points", 0),
                "badges": profile.get("badges", []),
            },
        }

        if persist:
            student["updated_at"] = time.time()
            self._save_progress()
        return route
