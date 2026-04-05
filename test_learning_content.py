from pathlib import Path

from adaptive_learning_engine import AdaptiveLearningEngine
from learning_content import generate_exercises, generate_micro_lesson


def build_engine(tmp_path: Path) -> AdaptiveLearningEngine:
    analytics_path = tmp_path / "student_profile.json"
    analytics_path.write_text('{"topics": {}}', encoding="utf-8")
    return AdaptiveLearningEngine(
        curriculum_path=tmp_path / "learning_curriculum.json",
        progress_path=tmp_path / "learning_progress.json",
        diagnostic_state_path=tmp_path / "learning_diagnostics.json",
        gamification_path=tmp_path / "learning_gamification.json",
        analytics_path=analytics_path,
    )


def test_generate_exercises_returns_expected_shape():
    exercises = generate_exercises(
        "efecto_tunel",
        "hard",
        3,
        persona="advanced",
        misconceptions=["tunel_superluminal"],
    )

    assert len(exercises) == 3
    assert all("prompt" in item and "solution" in item and "hint" in item for item in exercises)
    assert exercises[0]["theme"] == "efecto_tunel"
    assert exercises[0]["remediation_focus"] == "tunel_superluminal"


def test_generate_micro_lesson_renders_curriculum_template(tmp_path):
    engine = build_engine(tmp_path)

    lesson = generate_micro_lesson(
        "qm_ecuacion_schrodinger",
        engine=engine,
        persona="intermediate",
        mastery_threshold=0.85,
    )

    assert "# Micro-leccion: Ecuacion de Schroedinger" in lesson
    assert "Pozo de potencial interactivo" in lesson
    assert "worked_example" in lesson
    assert "Dominio requerido para avanzar: 85.0%" in lesson
