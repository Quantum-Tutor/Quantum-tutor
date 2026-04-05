from __future__ import annotations

import time
from typing import Any


LEVEL_LABELS = {
    "beginner": "Principiante",
    "intermediate": "Intermedio",
    "advanced": "Avanzado",
}

PERSONA_LABELS = {
    "beginner": "Principiante",
    "intermediate": "Intermedio",
    "advanced": "Avanzado",
    "expert": "Experto",
}

METRIC_STATUS_LABELS = {
    "green": "OPTIMO",
    "yellow": "MEJORABLE",
    "red": "CRITICO",
    "neutral": "SIN_DATOS",
}

ACTION_RECOMMENDATIONS = {
    "increase_scaffolding": "Agrega ejemplos guiados y divide el concepto en pasos mas cortos.",
    "reduce_difficulty": "Reduce la dificultad temporalmente y vuelve a escalar cuando mejore el dominio.",
    "increase_review_frequency": "Acorta el intervalo de repaso y reactiva preguntas de retencion.",
    "inject_remediation_content": "Activa remediacion explicita contra el error conceptual dominante.",
    "keep_current_strategy": "Mantener la estrategia actual y seguir observando la cohorte.",
}

MISCONCEPTION_LABELS = {
    "none": "Sin misconception dominante",
    "onda_particula_literal": "Confusion onda vs particula",
    "medicion_destruye_realidad": "Colapso literal en medicion",
    "tunel_superluminal": "Tunel superluminal",
}


def level_label(level: str) -> str:
    return LEVEL_LABELS.get((level or "").strip().lower(), "Exploracion")


def persona_label(persona: str) -> str:
    return PERSONA_LABELS.get((persona or "").strip().lower(), "Exploracion")


def misconception_label(code: str) -> str:
    normalized = (code or "none").strip().lower()
    if normalized in MISCONCEPTION_LABELS:
        return MISCONCEPTION_LABELS[normalized]
    if not normalized or normalized == "none":
        return MISCONCEPTION_LABELS["none"]
    return normalized.replace("_", " ").strip().capitalize()


def _status_for_threshold(
    value: float | None,
    *,
    green_threshold: float,
    yellow_threshold: float,
    higher_is_better: bool = True,
) -> dict[str, Any]:
    if value is None:
        return {"tone": "neutral", "status_label": METRIC_STATUS_LABELS["neutral"]}
    if higher_is_better:
        if value >= green_threshold:
            return {"tone": "green", "status_label": METRIC_STATUS_LABELS["green"]}
        if value >= yellow_threshold:
            return {"tone": "yellow", "status_label": METRIC_STATUS_LABELS["yellow"]}
        return {"tone": "red", "status_label": METRIC_STATUS_LABELS["red"]}
    if value <= green_threshold:
        return {"tone": "green", "status_label": METRIC_STATUS_LABELS["green"]}
    if value <= yellow_threshold:
        return {"tone": "yellow", "status_label": METRIC_STATUS_LABELS["yellow"]}
    return {"tone": "red", "status_label": METRIC_STATUS_LABELS["red"]}


def _readiness_level(experiment: dict[str, Any]) -> dict[str, Any]:
    experiment = experiment or {}
    sample_size = int(experiment.get("sample_size", 0) or 0)
    min_sample = max(int(experiment.get("min_sample", 0) or 0), 1)
    end_at = float(experiment.get("end_at", 0.0) or 0.0)
    now = time.time()
    readiness = "LOW"
    if sample_size > min_sample * 0.5:
        readiness = "MEDIUM"
    if sample_size >= min_sample and end_at and now > end_at:
        readiness = "HIGH"
    progress = min(sample_size / min_sample, 1.0) if min_sample else 0.0
    seconds_remaining = max(end_at - now, 0.0) if end_at else 0.0
    if readiness == "HIGH":
        explanation = "La muestra minima y la ventana experimental ya estan completas."
    elif readiness == "MEDIUM":
        explanation = "La cohorte ya tiene una muestra util, pero aun conviene esperar mas datos o cerrar la ventana."
    else:
        explanation = "Todavia faltan datos antes de usar estos resultados para decisiones fuertes."
    return {
        "level": readiness,
        "sample_size": sample_size,
        "min_sample": min_sample,
        "sample_progress_percent": round(progress * 100, 1),
        "window_complete": bool(experiment.get("window_complete")),
        "evaluation_ready": bool(experiment.get("evaluation_ready")),
        "seconds_until_ready": round(seconds_remaining, 1),
        "days_until_ready": round(seconds_remaining / (24 * 60 * 60), 2) if seconds_remaining else 0.0,
        "explanation": explanation,
    }


def _human_recommendation(actions: list[str]) -> str:
    steps = [
        ACTION_RECOMMENDATIONS[action]
        for action in actions
        if action in ACTION_RECOMMENDATIONS and action != "keep_current_strategy"
    ]
    if not steps and "keep_current_strategy" in actions:
        return ACTION_RECOMMENDATIONS["keep_current_strategy"]
    if not steps:
        return "Mantener observacion activa y revisar nuevas interacciones antes de intervenir."
    return " ".join(steps)


def _cohort_health_score(cohort: dict[str, Any]) -> float:
    statuses = [
        _status_for_threshold(cohort.get("learning_gain_avg"), green_threshold=0.25, yellow_threshold=0.12),
        _status_for_threshold(cohort.get("time_to_mastery_avg_days"), green_threshold=2.5, yellow_threshold=4.5, higher_is_better=False),
        _status_for_threshold(cohort.get("retention_score_avg"), green_threshold=0.75, yellow_threshold=0.60),
        _status_for_threshold(cohort.get("misconception_resolution_rate_avg"), green_threshold=0.70, yellow_threshold=0.50),
    ]
    mapping = {"green": 1.0, "yellow": 0.6, "red": 0.2, "neutral": 0.0}
    score = sum(mapping[item["tone"]] for item in statuses) / max(len(statuses), 1)
    return round(score, 3)


def next_node_theme(route: dict[str, Any]) -> str:
    node = (route or {}).get("next_node") or {}
    node_id = str(node.get("id", ""))
    if "tunel" in node_id:
        return "efecto_tunel"
    if "schrodinger" in node_id or "pozo" in node_id:
        return "pozo_infinito"
    if "operadores" in node_id or "conmut" in node_id:
        return "conmutadores"
    return "superposicion"


def summarize_route(route: dict[str, Any]) -> dict[str, Any]:
    route = route or {}
    next_node = route.get("next_node") or {}
    milestones = route.get("milestones") or []
    next_milestone = next(
        (item for item in milestones if not item.get("unlocked")),
        milestones[0] if milestones else {},
    )
    review_queue = route.get("review_queue") or []
    due_reviews = [item for item in review_queue if item.get("due")]
    next_review = due_reviews[0] if due_reviews else (review_queue[0] if review_queue else {})
    difficulty_profile = route.get("difficulty_profile") or {}
    return {
        "current_level_label": level_label(route.get("current_level", "")),
        "persona_label": persona_label(route.get("persona", "")),
        "points": int(((route.get("gamification") or {}).get("points", 0)) or 0),
        "badge_count": len((route.get("gamification") or {}).get("badges", [])),
        "overall_mastery_percent": round(float(route.get("overall_mastery", 0.0) or 0.0) * 100, 1),
        "next_node_title": next_node.get("title", "Sin recomendacion"),
        "next_node_summary": next_node.get("summary", ""),
        "next_node_modality": next_node.get("recommended_modality", ""),
        "next_node_reason": next_node.get("route_reason", ""),
        "next_node_mastery_percent": round(float(next_node.get("current_mastery", 0.0) or 0.0) * 100, 1),
        "next_milestone_label": next_milestone.get("label", "Sin milestones"),
        "next_milestone_progress_percent": round(float(next_milestone.get("progress", 0.0) or 0.0) * 100, 1),
        "diagnostic_completed": bool(route.get("diagnostic_completed")),
        "mastery_threshold_percent": round(float(route.get("mastery_threshold", 0.0) or 0.0) * 100, 1),
        "due_review_count": int(route.get("due_review_count", 0) or 0),
        "review_due_now": bool(route.get("review_due_now")),
        "next_review_title": next_review.get("title", ""),
        "recommended_difficulty": difficulty_profile.get("recommended_difficulty", "medium"),
        "blocked_node_count": int(((route.get("knowledge_graph") or {}).get("blocked_count", 0)) or 0),
    }


def summarize_feedback_rollup(results: list[dict[str, Any]]) -> dict[str, Any]:
    correct_count = sum(1 for item in results if item.get("correcto"))
    incorrect_count = sum(1 for item in results if not item.get("correcto"))
    remediation_titles = []
    misconception_count = 0
    for item in results:
        remediation = item.get("recommended_remediation") or {}
        title = remediation.get("title")
        if title and title not in remediation_titles:
            remediation_titles.append(title)
        misconception_count += len(item.get("misconceptions") or [])
    return {
        "correct_count": correct_count,
        "incorrect_count": incorrect_count,
        "remediation_titles": remediation_titles,
        "misconception_count": misconception_count,
    }


def summarize_kpis(kpis: dict[str, Any]) -> dict[str, Any]:
    kpis = kpis or {}
    pretest = kpis.get("pretest_score")
    posttest = kpis.get("posttest_score")
    improvement = kpis.get("improvement")
    experiment = kpis.get("experiment") or {}
    misconceptions = kpis.get("misconceptions") or {}
    difficulty_profile = kpis.get("difficulty_profile") or {}
    return {
        "pretest_percent": round(float(pretest or 0.0) * 100, 1) if pretest is not None else None,
        "posttest_percent": round(float(posttest or 0.0) * 100, 1) if posttest is not None else None,
        "improvement_points": round(float(improvement or 0.0) * 100, 1) if improvement is not None else None,
        "completion_percent": round(float(kpis.get("completion_rate", 0.0) or 0.0) * 100, 1),
        "average_node_progress_percent": round(float(kpis.get("average_node_progress", 0.0) or 0.0) * 100, 1),
        "overall_mastery_percent": round(float(kpis.get("overall_mastery", 0.0) or 0.0) * 100, 1),
        "milestones_text": f"{int(kpis.get('milestones_unlocked', 0) or 0)}/{int(kpis.get('milestones_total', 0) or 0)}",
        "chat_learning_events": int(kpis.get("chat_learning_events", 0) or 0),
        "points": int(kpis.get("points", 0) or 0),
        "badges": int(kpis.get("badges", 0) or 0),
        "experiment_name": experiment.get("experiment_name", ""),
        "experiment_variant": experiment.get("variant", ""),
        "persona_label": persona_label(kpis.get("persona", "")),
        "recommended_difficulty": difficulty_profile.get("recommended_difficulty", "medium"),
        "recent_accuracy_percent": round(float(difficulty_profile.get("recent_accuracy", 0.0) or 0.0) * 100, 1),
        "due_review_count": int(kpis.get("due_review_count", 0) or 0),
        "misconception_count": sum(int((value or {}).get("count", 0) or 0) for value in misconceptions.values()),
        "mastery_threshold_percent": round(float(kpis.get("mastery_threshold", 0.0) or 0.0) * 100, 1),
    }


def summarize_cohort_report(report: dict[str, Any]) -> dict[str, Any]:
    report = report or {}
    summary = report.get("summary") or {}
    variants = report.get("variants") or []
    module_rows = report.get("module_comparison") or []
    top_module = module_rows[0] if module_rows else {}
    return {
        "student_count": int(summary.get("student_count", 0) or 0),
        "diagnostic_completed_percent": round(float(summary.get("diagnostic_completed_rate", 0.0) or 0.0) * 100, 1),
        "average_completion_percent": round(float(summary.get("average_completion_rate", 0.0) or 0.0) * 100, 1),
        "average_mastery_percent": round(float(summary.get("average_overall_mastery", 0.0) or 0.0) * 100, 1),
        "average_improvement_points": round(float(summary.get("average_improvement", 0.0) or 0.0) * 100, 1)
        if summary.get("average_improvement") is not None else None,
        "average_due_reviews": round(float(summary.get("average_due_reviews", 0.0) or 0.0), 2),
        "variant_count": len(variants),
        "top_module_title": top_module.get("title", "Sin datos"),
        "top_module_started": int(top_module.get("started_count", 0) or 0),
    }


def summarize_learning_insights(insights: dict[str, Any]) -> dict[str, Any]:
    insights = insights or {}
    summary = insights.get("summary") or {}
    experiment = insights.get("experiment") or {}
    cohorts = insights.get("cohorts") or []
    top_cohort = cohorts[0] if cohorts else {}
    return {
        "student_count": int(summary.get("student_count", 0) or 0),
        "cohort_count": int(summary.get("cohort_count", 0) or 0),
        "learning_gain_points": round(float(summary.get("learning_gain_avg", 0.0) or 0.0) * 100, 1)
        if summary.get("learning_gain_avg") is not None else None,
        "time_to_mastery_days": round(float(summary.get("time_to_mastery_avg_days", 0.0) or 0.0), 2)
        if summary.get("time_to_mastery_avg_days") is not None else None,
        "retention_percent": round(float(summary.get("retention_score_avg", 0.0) or 0.0) * 100, 1)
        if summary.get("retention_score_avg") is not None else None,
        "error_reduction_percent": round(float(summary.get("error_reduction_rate_avg", 0.0) or 0.0) * 100, 1)
        if summary.get("error_reduction_rate_avg") is not None else None,
        "misconception_resolution_percent": round(float(summary.get("misconception_resolution_rate_avg", 0.0) or 0.0) * 100, 1)
        if summary.get("misconception_resolution_rate_avg") is not None else None,
        "evaluation_ready": bool(experiment.get("evaluation_ready")),
        "sample_size": int(experiment.get("sample_size", 0) or 0),
        "min_sample": int(experiment.get("min_sample", 0) or 0),
        "top_recommendation": summary.get("top_recommendation", ""),
        "top_cohort_key": top_cohort.get("cohort_key", ""),
        "top_cohort_recommendation": top_cohort.get("recommendation", ""),
    }


def build_dashboard_view(insights: dict[str, Any]) -> dict[str, Any]:
    insights = insights or {}
    experiment = insights.get("experiment") or {}
    summary = insights.get("summary") or {}
    cohorts = insights.get("cohorts") or []
    readiness = _readiness_level(experiment)

    metrics = [
        {
            "id": "learning_gain",
            "label": "Learning Gain",
            "value": summary.get("learning_gain_avg"),
            "display": f"{float(summary.get('learning_gain_avg', 0.0) or 0.0) * 100:.1f} pts"
            if summary.get("learning_gain_avg") is not None else "Sin datos",
            "help": "Diferencia promedio entre postest y pretest.",
            **_status_for_threshold(summary.get("learning_gain_avg"), green_threshold=0.25, yellow_threshold=0.12),
        },
        {
            "id": "time_to_mastery",
            "label": "Time to Mastery",
            "value": summary.get("time_to_mastery_avg_days"),
            "display": f"{float(summary.get('time_to_mastery_avg_days', 0.0) or 0.0):.2f} d"
            if summary.get("time_to_mastery_avg_days") is not None else "Sin datos",
            "help": "Tiempo promedio hasta alcanzar mastery.",
            **_status_for_threshold(summary.get("time_to_mastery_avg_days"), green_threshold=2.5, yellow_threshold=4.5, higher_is_better=False),
        },
        {
            "id": "retention_score",
            "label": "Retention Score",
            "value": summary.get("retention_score_avg"),
            "display": f"{float(summary.get('retention_score_avg', 0.0) or 0.0) * 100:.1f}%"
            if summary.get("retention_score_avg") is not None else "Sin datos",
            "help": "Retencion posterior a repasos programados.",
            **_status_for_threshold(summary.get("retention_score_avg"), green_threshold=0.75, yellow_threshold=0.60),
        },
        {
            "id": "misconception_resolution_rate",
            "label": "Misconception Resolution",
            "value": summary.get("misconception_resolution_rate_avg"),
            "display": f"{float(summary.get('misconception_resolution_rate_avg', 0.0) or 0.0) * 100:.1f}%"
            if summary.get("misconception_resolution_rate_avg") is not None else "Sin datos",
            "help": "Porcentaje de misconceptions detectadas que luego se corrigen.",
            **_status_for_threshold(summary.get("misconception_resolution_rate_avg"), green_threshold=0.70, yellow_threshold=0.50),
        },
    ]
    metrics_by_id = {metric["id"]: metric for metric in metrics}

    module_totals: dict[str, int] = {}
    issue_counts: dict[tuple[str, str], int] = {}
    for cohort in cohorts:
        module_title = cohort.get("module_title") or cohort.get("module_id") or "Sin modulo"
        student_count = int(cohort.get("student_count", 0) or 0)
        misconception = (cohort.get("dominant_misconception") or "none").strip().lower()
        module_totals[module_title] = module_totals.get(module_title, 0) + student_count
        if misconception in {"", "none"}:
            continue
        key = (module_title, misconception)
        issue_counts[key] = issue_counts.get(key, 0) + student_count

    top_issues = []
    for (module_title, misconception), student_count in issue_counts.items():
        total_for_module = max(module_totals.get(module_title, 0), 1)
        share = student_count / total_for_module
        top_issues.append({
            "module_title": module_title,
            "misconception": misconception,
            "misconception_label": misconception_label(misconception),
            "student_count": student_count,
            "share_percent": round(share * 100, 1),
            "display_label": f"{module_title}: {misconception_label(misconception)}",
        })
    top_issues.sort(key=lambda item: (-item["share_percent"], -item["student_count"], item["module_title"]))

    variant_buckets: dict[str, dict[str, Any]] = {}
    for cohort in cohorts:
        variant = (cohort.get("variant") or "unknown").strip().lower()
        student_count = int(cohort.get("student_count", 0) or 0)
        bucket = variant_buckets.setdefault(
            variant,
            {
                "variant": variant,
                "student_count": 0,
                "learning_gain_total": 0.0,
                "learning_gain_count": 0,
                "time_to_mastery_total": 0.0,
                "time_to_mastery_count": 0,
                "retention_total": 0.0,
                "retention_count": 0,
                "misconception_resolution_total": 0.0,
                "misconception_resolution_count": 0,
            },
        )
        bucket["student_count"] += student_count
        if cohort.get("learning_gain_avg") is not None:
            bucket["learning_gain_total"] += float(cohort["learning_gain_avg"]) * student_count
            bucket["learning_gain_count"] += student_count
        if cohort.get("time_to_mastery_avg_days") is not None:
            bucket["time_to_mastery_total"] += float(cohort["time_to_mastery_avg_days"]) * student_count
            bucket["time_to_mastery_count"] += student_count
        if cohort.get("retention_score_avg") is not None:
            bucket["retention_total"] += float(cohort["retention_score_avg"]) * student_count
            bucket["retention_count"] += student_count
        if cohort.get("misconception_resolution_rate_avg") is not None:
            bucket["misconception_resolution_total"] += float(cohort["misconception_resolution_rate_avg"]) * student_count
            bucket["misconception_resolution_count"] += student_count

    ab_rows = []
    for variant, bucket in sorted(variant_buckets.items()):
        ab_rows.append({
            "variant": variant,
            "student_count": bucket["student_count"],
            "learning_gain_avg": round(bucket["learning_gain_total"] / bucket["learning_gain_count"], 3)
            if bucket["learning_gain_count"] else None,
            "time_to_mastery_avg_days": round(bucket["time_to_mastery_total"] / bucket["time_to_mastery_count"], 3)
            if bucket["time_to_mastery_count"] else None,
            "retention_score_avg": round(bucket["retention_total"] / bucket["retention_count"], 3)
            if bucket["retention_count"] else None,
            "misconception_resolution_rate_avg": round(
                bucket["misconception_resolution_total"] / bucket["misconception_resolution_count"], 3
            ) if bucket["misconception_resolution_count"] else None,
        })

    primary_metric = str(experiment.get("metric", "learning_gain") or "learning_gain")
    metric_field = {
        "learning_gain": "learning_gain_avg",
        "time_to_mastery": "time_to_mastery_avg_days",
        "retention_score": "retention_score_avg",
        "misconception_resolution_rate": "misconception_resolution_rate_avg",
    }.get(primary_metric, "learning_gain_avg")
    lower_is_better = metric_field == "time_to_mastery_avg_days"
    comparable_rows = [row for row in ab_rows if row.get(metric_field) is not None]
    winner_variant = None
    winner_insight = "Sin datos suficientes para comparar variantes."
    if comparable_rows:
        winner = sorted(
            comparable_rows,
            key=lambda item: (
                item[metric_field] if lower_is_better else -(item[metric_field]),
                -int(item.get("student_count", 0) or 0),
                item["variant"],
            ),
        )[0]
        winner_variant = winner["variant"]
        if len(comparable_rows) >= 2:
            ordered = sorted(
                comparable_rows,
                key=lambda item: (
                    item[metric_field] if lower_is_better else -(item[metric_field]),
                    -int(item.get("student_count", 0) or 0),
                ),
            )
            best = ordered[0]
            second = ordered[1]
            if lower_is_better:
                delta = float(second[metric_field]) - float(best[metric_field])
                relative = (delta / max(float(second[metric_field]) or 1.0, 1e-6)) * 100
                winner_insight = (
                    f"La variante {best['variant']} domina en {primary_metric} con {delta:.2f} dias menos "
                    f"({relative:.1f}% de mejora relativa)."
                )
            else:
                delta = float(best[metric_field]) - float(second[metric_field])
                baseline = abs(float(second[metric_field]) or 0.0)
                relative = (delta / baseline * 100) if baseline > 1e-6 else 0.0
                winner_insight = (
                    f"La variante {best['variant']} supera a {second['variant']} en {primary_metric} "
                    f"por {delta:.3f} ({relative:.1f}% de mejora relativa)."
                )
        else:
            winner_insight = f"Solo hay una variante comparable activa: {winner['variant']}."

    scored_cohorts = []
    for cohort in cohorts:
        enriched = dict(cohort)
        enriched["health_score"] = _cohort_health_score(cohort)
        enriched["persona_label"] = persona_label(cohort.get("persona", ""))
        enriched["misconception_label"] = misconception_label(cohort.get("dominant_misconception", "none"))
        actions = list(cohort.get("optimization_actions") or [])
        enriched["human_recommendation"] = _human_recommendation(actions)
        scored_cohorts.append(enriched)

    scored_cohorts.sort(
        key=lambda item: (
            item["health_score"],
            item.get("learning_gain_avg") is None,
            item.get("learning_gain_avg") or 0.0,
            -int(item.get("student_count", 0) or 0),
            item.get("cohort_key", ""),
        )
    )
    worst_cohort = scored_cohorts[0] if scored_cohorts else {}
    best_cohort = scored_cohorts[-1] if scored_cohorts else {}

    recommendations = []
    for cohort in scored_cohorts[:3]:
        actions = list(cohort.get("optimization_actions") or [])
        problem_fragments = []
        if cohort.get("learning_gain_avg") is None or float(cohort.get("learning_gain_avg", 0.0) or 0.0) < 0.18:
            problem_fragments.append("ganancia de aprendizaje baja")
        if cohort.get("time_to_mastery_avg_days") is not None and float(cohort.get("time_to_mastery_avg_days", 0.0) or 0.0) > 3.5:
            problem_fragments.append("mastery lento")
        if cohort.get("retention_score_avg") is not None and float(cohort.get("retention_score_avg", 0.0) or 0.0) < 0.65:
            problem_fragments.append("retencion fragil")
        if cohort.get("misconception_resolution_rate_avg") is None or float(cohort.get("misconception_resolution_rate_avg", 0.0) or 0.0) < 0.55:
            problem_fragments.append("misconception persistente")
        if not problem_fragments:
            problem_fragments.append("observacion preventiva")
        recommendations.append({
            "module_title": cohort.get("module_title", "Sin modulo"),
            "persona": cohort.get("persona", ""),
            "persona_label": cohort.get("persona_label", persona_label(cohort.get("persona", ""))),
            "variant": cohort.get("variant", ""),
            "dominant_misconception": cohort.get("dominant_misconception", "none"),
            "misconception_label": cohort.get("misconception_label", misconception_label(cohort.get("dominant_misconception", "none"))),
            "issue": ", ".join(problem_fragments),
            "recommendation": cohort.get("human_recommendation", _human_recommendation(actions)),
            "severity": "CRITICO" if float(cohort.get("health_score", 0.0) or 0.0) < 0.45 else "MEJORABLE",
        })

    return {
        "system_status": {
            "experiment_name": experiment.get("experiment_name", "gamification_v1"),
            "primary_metric": primary_metric,
            "sample_size": readiness["sample_size"],
            "min_sample": readiness["min_sample"],
            "sample_progress_percent": readiness["sample_progress_percent"],
            "readiness": readiness["level"],
            "window_days": int(experiment.get("window_days", 0) or 0),
            "window_complete": readiness["window_complete"],
            "evaluation_ready": readiness["evaluation_ready"],
            "days_until_ready": readiness["days_until_ready"],
            "explanation": readiness["explanation"],
        },
        "metrics": metrics,
        "metrics_by_id": metrics_by_id,
        "top_issues": top_issues[:8],
        "ab_test": {
            "rows": ab_rows,
            "metric_field": metric_field,
            "primary_metric": primary_metric,
            "winner_variant": winner_variant,
            "insight": winner_insight,
        },
        "recommendations": recommendations,
        "critical_cohorts": {
            "worst": worst_cohort,
            "best": best_cohort,
        },
    }
