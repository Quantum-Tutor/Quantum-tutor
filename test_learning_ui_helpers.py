import time

from learning_ui_helpers import (
    build_dashboard_view,
    next_node_theme,
    summarize_cohort_report,
    summarize_feedback_rollup,
    summarize_learning_insights,
    summarize_kpis,
    summarize_route,
)


def test_summarize_route_extracts_learning_summary():
    route = {
        "current_level": "intermediate",
        "persona": "advanced",
        "overall_mastery": 0.61,
        "diagnostic_completed": True,
        "mastery_threshold": 0.85,
        "due_review_count": 2,
        "review_due_now": True,
        "difficulty_profile": {"recommended_difficulty": "hard"},
        "knowledge_graph": {"blocked_count": 3},
        "review_queue": [{"title": "Funciones y Graficas", "due": True}],
        "next_node": {
            "id": "qm_efecto_tunel",
            "title": "Efecto Tunel",
            "summary": "Aplica el formalismo a barreras.",
            "recommended_modality": "simulation",
        },
        "milestones": [
            {"label": "Starter Foundations", "progress": 1.0, "unlocked": True},
            {"label": "Measurement Practitioner", "progress": 0.5, "unlocked": False},
        ],
        "gamification": {
            "points": 47,
            "badges": [{"id": "mapa-inicial"}],
        },
    }

    summary = summarize_route(route)

    assert summary["current_level_label"] == "Intermedio"
    assert summary["persona_label"] == "Avanzado"
    assert summary["points"] == 47
    assert summary["badge_count"] == 1
    assert summary["next_node_title"] == "Efecto Tunel"
    assert summary["next_milestone_label"] == "Measurement Practitioner"
    assert summary["next_milestone_progress_percent"] == 50.0
    assert summary["mastery_threshold_percent"] == 85.0
    assert summary["due_review_count"] == 2
    assert summary["recommended_difficulty"] == "hard"


def test_summarize_feedback_rollup_groups_remediation_titles():
    payload = [
        {
            "correcto": False,
            "recommended_remediation": {"title": "Onda y Funcion de Onda"},
            "misconceptions": ["onda_particula_literal"],
        },
        {
            "correcto": True,
            "recommended_remediation": {"title": ""},
            "misconceptions": [],
        },
        {
            "correcto": False,
            "recommended_remediation": {"title": "Onda y Funcion de Onda"},
            "misconceptions": ["tunel_superluminal"],
        },
    ]

    summary = summarize_feedback_rollup(payload)

    assert summary["correct_count"] == 1
    assert summary["incorrect_count"] == 2
    assert summary["remediation_titles"] == ["Onda y Funcion de Onda"]
    assert summary["misconception_count"] == 2


def test_next_node_theme_maps_known_route_ids():
    assert next_node_theme({"next_node": {"id": "qm_efecto_tunel"}}) == "efecto_tunel"
    assert next_node_theme({"next_node": {"id": "qm_superposicion_operadores"}}) == "conmutadores"


def test_summarize_kpis_formats_learning_metrics():
    summary = summarize_kpis({
        "pretest_score": 0.4,
        "posttest_score": 0.7,
        "improvement": 0.3,
        "completion_rate": 0.5,
        "average_node_progress": 0.62,
        "overall_mastery": 0.68,
        "milestones_unlocked": 1,
        "milestones_total": 4,
        "chat_learning_events": 3,
        "points": 52,
        "badges": 2,
        "persona": "intermediate",
        "difficulty_profile": {
            "recommended_difficulty": "hard",
            "recent_accuracy": 0.92,
        },
        "due_review_count": 3,
        "misconceptions": {
            "onda_particula_literal": {"count": 2},
        },
        "mastery_threshold": 0.85,
    })

    assert summary["pretest_percent"] == 40.0
    assert summary["posttest_percent"] == 70.0
    assert summary["improvement_points"] == 30.0
    assert summary["completion_percent"] == 50.0
    assert summary["milestones_text"] == "1/4"
    assert summary["persona_label"] == "Intermedio"
    assert summary["recommended_difficulty"] == "hard"
    assert summary["due_review_count"] == 3
    assert summary["misconception_count"] == 2
    assert summary["mastery_threshold_percent"] == 85.0


def test_summarize_cohort_report_formats_aggregate_metrics():
    summary = summarize_cohort_report({
        "summary": {
            "student_count": 12,
            "diagnostic_completed_rate": 0.75,
            "average_completion_rate": 0.5,
            "average_overall_mastery": 0.62,
            "average_improvement": 0.18,
            "average_due_reviews": 1.25,
        },
        "variants": [{"variant": "control"}, {"variant": "challenge"}],
        "module_comparison": [{"title": "Efecto Tunel", "started_count": 9}],
    })

    assert summary["student_count"] == 12
    assert summary["diagnostic_completed_percent"] == 75.0
    assert summary["average_completion_percent"] == 50.0
    assert summary["average_mastery_percent"] == 62.0
    assert summary["average_improvement_points"] == 18.0
    assert summary["average_due_reviews"] == 1.25
    assert summary["variant_count"] == 2
    assert summary["top_module_title"] == "Efecto Tunel"


def test_summarize_learning_insights_formats_experimental_metrics():
    summary = summarize_learning_insights({
        "experiment": {
            "evaluation_ready": True,
            "sample_size": 120,
            "min_sample": 100,
        },
        "summary": {
            "student_count": 120,
            "cohort_count": 4,
            "learning_gain_avg": 0.22,
            "time_to_mastery_avg_days": 2.75,
            "retention_score_avg": 0.71,
            "error_reduction_rate_avg": 0.38,
            "misconception_resolution_rate_avg": 0.64,
            "top_recommendation": "Mantener la estrategia actual.",
        },
        "cohorts": [
            {
                "cohort_key": "beginner|onda_particula_literal|qm_onda_funcion_onda|challenge",
                "recommendation": "Aumentar andamiaje.",
            }
        ],
    })

    assert summary["student_count"] == 120
    assert summary["cohort_count"] == 4
    assert summary["learning_gain_points"] == 22.0
    assert summary["time_to_mastery_days"] == 2.75
    assert summary["retention_percent"] == 71.0
    assert summary["error_reduction_percent"] == 38.0
    assert summary["misconception_resolution_percent"] == 64.0
    assert summary["evaluation_ready"] is True
    assert summary["top_cohort_key"].startswith("beginner|")


def test_build_dashboard_view_groups_statuses_ab_and_recommendations():
    now = time.time()
    dashboard = build_dashboard_view({
        "experiment": {
            "experiment_name": "gamification_v1",
            "metric": "learning_gain",
            "sample_size": 120,
            "min_sample": 100,
            "window_days": 14,
            "end_at": now - 60,
            "window_complete": True,
            "evaluation_ready": True,
        },
        "summary": {
            "student_count": 120,
            "cohort_count": 3,
            "learning_gain_avg": 0.22,
            "time_to_mastery_avg_days": 2.9,
            "retention_score_avg": 0.71,
            "misconception_resolution_rate_avg": 0.64,
        },
        "cohorts": [
            {
                "cohort_key": "beginner|onda_particula_literal|qm_onda_funcion_onda|challenge",
                "student_count": 25,
                "persona": "beginner",
                "dominant_misconception": "onda_particula_literal",
                "module_id": "qm_onda_funcion_onda",
                "module_title": "Funcion de Onda",
                "variant": "challenge",
                "learning_gain_avg": 0.15,
                "time_to_mastery_avg_days": 4.8,
                "retention_score_avg": 0.58,
                "misconception_resolution_rate_avg": 0.42,
                "optimization_actions": ["increase_scaffolding", "reduce_difficulty", "inject_remediation_content"],
                "recommendation": "Recomendacion: aumentar andamiaje.",
            },
            {
                "cohort_key": "intermediate|none|qm_efecto_tunel|control",
                "student_count": 30,
                "persona": "intermediate",
                "dominant_misconception": "none",
                "module_id": "qm_efecto_tunel",
                "module_title": "Efecto Tunel",
                "variant": "control",
                "learning_gain_avg": 0.29,
                "time_to_mastery_avg_days": 2.1,
                "retention_score_avg": 0.78,
                "misconception_resolution_rate_avg": 0.74,
                "optimization_actions": ["keep_current_strategy"],
                "recommendation": "Mantener la estrategia actual.",
            },
            {
                "cohort_key": "beginner|onda_particula_literal|qm_onda_funcion_onda|control",
                "student_count": 20,
                "persona": "beginner",
                "dominant_misconception": "onda_particula_literal",
                "module_id": "qm_onda_funcion_onda",
                "module_title": "Funcion de Onda",
                "variant": "control",
                "learning_gain_avg": 0.18,
                "time_to_mastery_avg_days": 3.5,
                "retention_score_avg": 0.62,
                "misconception_resolution_rate_avg": 0.55,
                "optimization_actions": ["increase_scaffolding"],
                "recommendation": "Recomendacion: aumentar andamiaje.",
            },
        ],
    })

    assert dashboard["system_status"]["readiness"] == "HIGH"
    assert dashboard["metrics_by_id"]["learning_gain"]["status_label"] == "MEJORABLE"
    assert dashboard["top_issues"][0]["module_title"] == "Funcion de Onda"
    assert dashboard["top_issues"][0]["misconception_label"] == "Confusion onda vs particula"
    assert dashboard["ab_test"]["winner_variant"] in {"control", "challenge"}
    assert "mejora relativa" in dashboard["ab_test"]["insight"]
    assert dashboard["critical_cohorts"]["worst"]["cohort_key"].startswith("beginner|onda_particula_literal")
    assert dashboard["recommendations"][0]["severity"] == "CRITICO"
