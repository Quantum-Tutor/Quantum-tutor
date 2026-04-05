import json
import time
from pathlib import Path

from adaptive_learning_engine import AdaptiveLearningEngine


def build_engine(tmp_path: Path) -> AdaptiveLearningEngine:
    analytics_path = tmp_path / "student_profile.json"
    analytics_path.write_text(
        '{"topics": {"Efecto T\\u00fanel": {"struggle_index": 0.72}}}',
        encoding="utf-8",
    )
    return AdaptiveLearningEngine(
        curriculum_path=tmp_path / "learning_curriculum.json",
        progress_path=tmp_path / "learning_progress.json",
        diagnostic_state_path=tmp_path / "learning_diagnostics.json",
        gamification_path=tmp_path / "learning_gamification.json",
        analytics_path=analytics_path,
    )


def test_initial_diagnostic_spans_skills_and_persists_student(tmp_path):
    engine = build_engine(tmp_path)

    payload = engine.get_initial_diagnostic(
        "student-a",
        target_level="intermediate",
        max_questions=4,
    )

    assert payload["student_id"] == "student-a"
    assert len(payload["questions"]) == 4
    assert len({item["skill"] for item in payload["questions"]}) == 4
    assert "correct_answer" not in payload["questions"][0]
    saved = engine.progress_state["students"]["student-a"]
    assert len(saved["last_diagnostic_question_ids"]) == 4


def test_mastery_threshold_blocks_advance_until_node_is_dominated(tmp_path):
    engine = build_engine(tmp_path)

    first_save = engine.save_progress(
        "student-threshold",
        "math_functions",
        mastery_score=0.84,
        completed=True,
    )
    assert "math_functions" not in first_save["completed_nodes"]

    route_before = engine.get_personalized_route("student-threshold")
    assert route_before["next_node"]["id"] == "math_functions"
    assert route_before["mastery_threshold"] == 0.85

    second_save = engine.save_progress(
        "student-threshold",
        "math_functions",
        mastery_score=0.9,
        completed=True,
    )
    assert "math_functions" in second_save["completed_nodes"]

    route_after = engine.get_personalized_route("student-threshold")
    assert route_after["next_node"]["id"] != "math_functions"


def test_evaluate_answer_updates_remediation_and_badges(tmp_path):
    engine = build_engine(tmp_path)
    diagnostic = engine.get_initial_diagnostic("student-b", max_questions=4)
    question_ids = [item["id"] for item in diagnostic["questions"]]

    first = engine.evaluate_answer("student-b", question_ids[0], "respuesta equivocada", self_assessment=1.5)
    assert first["correcto"] is False
    assert first["recommended_remediation"]["node_id"]
    assert first["route_preview"]["recommended_modalities"][0] == "micro_lesson"
    assert len(first["feedback_steps"]) == 5
    assert first["persona"] in {"beginner", "intermediate", "advanced", "expert"}

    for question_id in question_ids[1:]:
        correct_answer = engine.question_bank[question_id]["correct_answer"]
        engine.evaluate_answer("student-b", question_id, correct_answer)

    student = engine.progress_state["students"]["student-b"]
    badges = engine.gamification_state["students"]["student-b"]["badges"]
    assert student["diagnostic_completed"] is True
    assert any(item["id"] == "mapa-inicial" for item in badges)


def test_save_progress_unlocks_milestone_and_uses_analytics_queue(tmp_path):
    engine = build_engine(tmp_path)
    engine.get_initial_diagnostic("student-c", max_questions=4)

    route = engine.get_personalized_route("student-c")
    assert "qm_efecto_tunel" in route["remediation_queue"]

    engine.save_progress("student-c", "qm_principios_basicos", mastery_score=0.9, completed=True)
    saved = engine.save_progress("student-c", "qm_onda_funcion_onda", mastery_score=0.92, completed=True)

    assert "starter_foundations" in saved["milestones_unlocked"]
    badges = saved["gamification"]["badges"]
    assert any(item["id"] == "fundamentos-cuanticos" for item in badges)


def test_spaced_review_due_has_priority_in_route(tmp_path):
    engine = build_engine(tmp_path)
    engine.save_progress("student-review", "math_functions", mastery_score=0.91, completed=True)
    engine.save_progress("student-review", "math_derivatives", mastery_score=0.9, completed=True)

    progress_entry = engine.progress_state["students"]["student-review"]["node_progress"]["math_functions"]
    progress_entry["next_review_at"] = time.time() - 60

    route = engine.get_personalized_route("student-review")

    assert route["review_due_now"] is True
    assert route["due_review_count"] >= 1
    assert route["next_node"]["id"] == "math_functions"
    assert route["next_node"]["route_reason"] == "spaced_review_due"
    assert route["next_node"]["review_due"] is True


def test_chat_learning_signal_updates_node_progress_and_kpis(tmp_path):
    engine = build_engine(tmp_path)

    recorded = engine.record_chat_learning_signal(
        "student-d",
        "Efecto Túnel",
        passed_socratic=True,
        response_quality="Sólida",
        engine_status="HYBRID_RELATIONAL",
        wolfram_used=True,
        context_retrieved=True,
    )

    assert recorded["recorded"] is True
    assert recorded["node_id"] == "qm_efecto_tunel"
    student = engine.progress_state["students"]["student-d"]
    assert student["node_progress"]["qm_efecto_tunel"]["mastery_score"] > 0
    kpis = engine.get_learning_kpis("student-d")
    assert kpis["chat_learning_events"] == 1
    assert kpis["average_node_progress"] > 0
    assert kpis["difficulty_profile"]["recommended_difficulty"] in {"easy", "medium", "hard"}


def test_misconceptions_are_detected_and_synced_to_student_profile(tmp_path):
    engine = build_engine(tmp_path)

    payload = engine.evaluate_answer(
        "student-misconception",
        "diag_foundations_duality",
        "La funcion de onda es una particula",
    )

    assert "onda_particula_literal" in payload["misconceptions"]

    profile = json.loads((tmp_path / "student_profile.json").read_text(encoding="utf-8"))
    adaptive_bucket = profile["adaptive_learning"]["students"]["student-misconception"]
    assert adaptive_bucket["persona"] in {"beginner", "intermediate", "advanced", "expert"}
    assert "onda_particula_literal" in adaptive_bucket["misconceptions"]


def test_record_assessment_score_computes_improvement(tmp_path):
    engine = build_engine(tmp_path)

    engine.record_assessment_score("student-e", assessment_type="pretest", score=0.45, label="inicio")
    payload = engine.record_assessment_score("student-e", assessment_type="posttest", score=0.70, label="cierre")

    assert payload["assessment_type"] == "posttest"
    assert payload["kpis"]["pretest_score"] == 0.45
    assert payload["kpis"]["posttest_score"] == 0.7
    assert payload["kpis"]["improvement"] == 0.25


def test_cohort_report_and_export_include_variants_and_modules(tmp_path):
    engine = build_engine(tmp_path)
    engine.record_assessment_score("student-f", assessment_type="pretest", score=0.3)
    engine.record_assessment_score("student-f", assessment_type="posttest", score=0.6)
    engine.save_progress("student-f", "qm_principios_basicos", mastery_score=0.8, completed=True)
    engine.record_chat_learning_signal(
        "student-g",
        "Efecto Túnel",
        passed_socratic=True,
        response_quality="Sólida",
        engine_status="HYBRID_RELATIONAL",
    )

    report = engine.get_cohort_report()
    exported = engine.export_cohort_report(
        json_path=tmp_path / "cohort_report.json",
        csv_path=tmp_path / "cohort_report.csv",
    )

    assert report["summary"]["student_count"] >= 2
    assert report["variants"]
    assert report["module_comparison"]
    assert "persona" in report["students"][0]
    assert "due_review_count" in report["students"][0]
    assert exported["json_path"].endswith("cohort_report.json")
    assert exported["csv_path"].endswith("cohort_report.csv")
    assert (tmp_path / "cohort_report.json").exists()
    assert (tmp_path / "cohort_report.csv").exists()


def test_learning_insights_builds_multidimensional_cohorts_and_applies_optimization(tmp_path):
    engine = build_engine(tmp_path)
    student_id = "student-insights"

    engine.record_assessment_score(student_id, assessment_type="pretest", score=0.4, label="inicio")
    engine.record_assessment_score(student_id, assessment_type="posttest", score=0.45, label="cierre")
    engine.evaluate_answer(student_id, "diag_foundations_duality", "La funcion de onda es una particula")
    engine.save_progress(student_id, "math_functions", mastery_score=0.92, completed=True, reflection="Todavia pienso que la funcion de onda es una particula")

    progress_entry = engine.progress_state["students"][student_id]["node_progress"]["math_functions"]
    progress_entry["first_exposure_at"] = time.time() - (6 * 24 * 60 * 60)
    progress_entry["mastery_achieved_at"] = time.time() - (1 * 24 * 60 * 60)
    progress_entry["retention_score"] = 0.42

    assignment = engine.get_experiment_assignment(student_id)
    assignment["start_at"] = time.time() - (15 * 24 * 60 * 60)
    assignment["end_at"] = time.time() - (1 * 24 * 60 * 60)
    assignment["min_sample"] = 1
    engine.gamification_state["students"][student_id]["experiments"][assignment["experiment_name"]] = assignment

    insights = engine.get_learning_insights(apply_optimization=True)

    assert insights["experiment"]["evaluation_ready"] is True
    assert insights["summary"]["cohort_count"] >= 1
    assert insights["cohorts"]
    cohort = insights["cohorts"][0]
    assert cohort["cohort_key"]
    assert cohort["learning_gain_avg"] == 0.05
    assert cohort["time_to_mastery_avg_days"] is not None
    assert cohort["recommendation"]
    assert student_id in insights["learning_cohorts"][cohort["cohort_key"]]

    optimization_profile = engine.progress_state["students"][student_id]["optimization_profile"]
    assert optimization_profile["scaffolding"] == "high"
    assert optimization_profile["difficulty_adjustment"] == "easier"
    assert optimization_profile["remediation_boost"] is True
