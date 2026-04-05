import sys
import os
from pathlib import Path

# --- DISABLE TQDM (Prevents OSError 22 in Streamlit/Windows) ---
os.environ["TQDM_DISABLE"] = "1"
os.environ["TQDM_MININTERVAL"] = "100"

# --- MONKEYPATCH: Windows/Streamlit sys.stderr.flush [Errno 22] FIX ---
if hasattr(sys.stderr, "flush"):
    def _safe_flush(*args, **kwargs):
        pass 
    sys.stderr.flush = _safe_flush

if hasattr(sys.stdout, "flush"):
    def _safe_flush_out(*args, **kwargs):
        pass 
    sys.stdout.flush = _safe_flush_out
# ----------------------------------------------------------------------
import streamlit as st
import mimetypes

# Fix MIME types for Streamlit static serving (Windows registry workaround)
mimetypes.add_type('application/javascript', '.js')
mimetypes.add_type('image/svg+xml', '.svg')
import time
import json
import asyncio
import pandas as pd
try:
    import nest_asyncio
    nest_asyncio.apply()
except ImportError:
    pass  # nest_asyncio no disponible, se manejará con thread pool
from concurrent.futures import ThreadPoolExecutor
from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from tool_scheduler import ToolScheduler, ToolRegistry
from learning_analytics import LearningAnalytics
from adaptive_learning_engine import AdaptiveLearningEngine
from learning_content import generate_exercises, generate_micro_lesson
from learning_ui_helpers import (
    build_dashboard_view,
    next_node_theme,
    summarize_cohort_report,
    summarize_feedback_rollup,
    summarize_kpis,
    summarize_route,
)
from multimodal_vision_parser import MultimodalVisionParser
from auth_module import require_auth
from quantum_tutor_runtime import APP_NAME, RUNTIME_VERSION
from reference_visualizer import ReferenceVisualizer
from galindo_page_map import galindo_display_page_from_asset
from security_audit import SecurityEventLogger
from security_controls import FileAbusePrevention, FileCircuitBreaker
import importlib

import uuid
from quantum_request_context import QuantumRequestContext
from session_manager import SessionStore, create_session_state

# BUG FIX #5: Eliminado importlib.reload (anti-patron, no thread-safe con Streamlit cache)

# Ruta base del proyecto
BASE_DIR = Path(__file__).parent.absolute()
PDF_PATH = BASE_DIR / "wuolah-premium-Galindo-Pascual-Quantum-Mechanics-Vol-I.pdf"

# Configuración de la página
st.set_page_config(
    page_title="Quantum Tutor | v6.1-stateless",
    page_icon="⚛️",
    layout="wide"
)

# Inyección de metadatos PWA y branding de Quantum Tutor (Celestial-Harmonic)
st.logo("static/logo_192.png", icon_image="static/logo_192.png")

# CSS para Estética Celestial-Harmonic — SCOPED para evitar leakage al sidebar
# NOTA: Los selectores genéricos (h1, code, etc.) son reemplazados por
#       .eic-app-main h1, .eic-app-main code, etc. para no afectar widgets nativos.
st.markdown(
    """
    <style>
    /* ── Sources and Global Reset ────────── */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600&display=swap');

    /* ── Forzar Modo Claro (Blanco y Negro) ────────── */
    .stApp {
        background-color: #ffffff !important;
        color: #000000 !important;
        font-family: 'Inter', sans-serif !important;
    }
    
    [data-testid="stHeader"] {
        background: transparent !important;
    }

    [data-testid="stSidebar"] {
        background-color: #f7f7f8 !important;
        border-right: 1px solid #e5e5e5 !important;
    }

    /* Sobrescribir todos los colores de texto principales a negro */
    h1, h2, h3, h4, h5, h6, p, li, span {
        color: #000000 !important;
    }

    /* ── Corrección de Matemáticas en Rojo (Inline Code) ────────── */
    /* Streamlit rendered `code` tags in red text natively. We force them to be dark grey on light grey */
    code {
        color: #000000 !important;
        background-color: #f0f0f0 !important;
        border: 1px solid #dcdcdc !important;
        border-radius: 4px !important;
        padding: 2px 4px !important;
        font-size: 1.05em !important;
    }
    
    pre code {
        background-color: transparent !important;
        border: none !important;
    }

    /* ── Bloques de Chat Simplificados ────────── */
    .stChatMessage {
        background-color: #ffffff !important;
        border: 1px solid #e0e0e0 !important;
        border-radius: 8px !important;
        margin-bottom: 1rem !important;
        padding: 1.5rem !important;
        box-shadow: 0 1px 3px rgba(0,0,0,0.05) !important;
    }
    
    [data-testid="chatAvatarIcon-user"] {
        background-color: #000000 !important;
    }
    
    [data-testid="chatAvatarIcon-assistant"] {
        background-color: #666666 !important;
    }

    /* ── Input de Chat Simplificado ────────── */
    [data-testid="stChatInput"] {
        background-color: #ffffff !important;
        border: 2px solid #000000 !important;
        border-radius: 8px !important;
    }
    [data-testid="stChatInput"] textarea {
        color: #000000 !important;
    }

    /* ── Título Principal ────────── */
    .celestial-title {
        color: #000000 !important;
        font-size: 2.2rem !important;
        font-weight: bold !important;
        text-align: left;
        border-bottom: 2px solid #000000;
        padding-bottom: 0.5rem;
        margin-bottom: 1rem;
    }

    /* ── Ocultar elementos innecesarios ────────── */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    </style>
    """,
    unsafe_allow_html=True
)

st.components.v1.html(
    """
    <script>
        const head = window.parent.document.head;
        if (!head.querySelector('link[rel="manifest"]')) {
            const manifest = window.parent.document.createElement('link');
            manifest.rel = 'manifest';
            manifest.href = './app/static/manifest.json';
            head.appendChild(manifest);
            
            const theme = window.parent.document.createElement('meta');
            theme.name = 'theme-color';
            theme.content = '#0E1117';
            head.appendChild(theme);
            
            const appleIcon = window.parent.document.createElement('link');
            appleIcon.rel = 'apple-touch-icon';
            appleIcon.href = './app/static/icon.svg';
            head.appendChild(appleIcon);
            
            if ('serviceWorker' in navigator) {
                navigator.serviceWorker.register('./app/static/sw.js').then(reg => {
                    console.log('Quantum Tutor SW registered', reg);
                }).catch(err => {
                    console.error('SW registration failed:', err);
                });
            }
        }
    </script>
    """,
    height=0,
    width=0
)

st.markdown(
    """
    <link rel="manifest" href="static/manifest.json">
    <meta name="theme-color" content="#0e1117">
    """,
    unsafe_allow_html=True
)

# =========================================================
# SINGLETONS v6 (Stateless Orchestrator & Session Store)
# =========================================================
if "orchestrator" not in st.session_state:
    _registry = ToolRegistry()
    _scheduler = ToolScheduler(_registry)
    st.session_state.orchestrator = QuantumTutorOrchestrator(config_path="quantum_tutor_config.json", base_dir=BASE_DIR, scheduler=_scheduler)

if "session_store" not in st.session_state:
    st.session_state.session_store = SessionStore(ttl_seconds=3600)

if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "cancel_flag" not in st.session_state:
    st.session_state.cancel_flag = False

@st.cache_resource
def init_vision():
    return MultimodalVisionParser()

@st.cache_resource
def init_reference_viz():
    return ReferenceVisualizer(str(PDF_PATH), base_dir=str(BASE_DIR))


@st.cache_resource
def init_adaptive_learning():
    return AdaptiveLearningEngine()

# GATEWAY: Autenticación Obligatoria
auth = require_auth()
vision_parser = init_vision()
reference_viz = init_reference_viz()
adaptive_learning = init_adaptive_learning()

tutor = st.session_state.orchestrator


def _format_reference_page_label(page_id) -> str:
    raw_id = str(page_id)
    if "cohen_page_" in raw_id:
        return raw_id.replace("cohen_page_", "Cohen Tannoudji p. ")
    if "sakurai_page_" in raw_id:
        return raw_id.replace("sakurai_page_", "Sakurai p. ")
    if "page_" in raw_id:
        asset_token = raw_id.replace("page_", "").replace(".png", "")
        display_page = galindo_display_page_from_asset(asset_token)
        return f"Galindo & Pascual p. {display_page}" if display_page else raw_id
    if raw_id.isdigit():
        return f"Galindo & Pascual p. {raw_id}"
    return raw_id


def _delete_session_data(session_id: str) -> None:
    if not session_id:
        return
    try:
        asyncio.run(st.session_state.session_store.delete(session_id))
    except RuntimeError:
        with ThreadPoolExecutor(max_workers=1) as _ex:
            _ex.submit(
                lambda: asyncio.run(st.session_state.session_store.delete(session_id))
            ).result(timeout=10)


def _rotate_user_session() -> None:
    old_session_id = st.session_state.get("session_id", "")
    _delete_session_data(old_session_id)
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.messages = []
    st.session_state.stats = {"wolfram_hits": 0, "rag_queries": 0}
    st.session_state.cancel_flag = False
    st.session_state.ignore_chat_input_once = True
    st.session_state.pop("relational_data", None)
    st.session_state.pop("scaffolding", None)
    st.session_state.pop("engine_status", None)
    st.session_state.pop("vision_active_prompt", None)
    st.session_state.pop("last_response_quality", None)
    st.session_state.pop("last_response_notes", None)
    st.session_state.pop("last_rate_limit_meta", None)
    st.session_state.pop("last_backpressure_meta", None)
    st.session_state.pop("last_provider_retry_meta", None)
    st.session_state.pop("sidebar_action", None)
    st.session_state.pop("group_chat_notice", None)
    st.session_state.pop("main_chat_input", None)
    st.session_state.pop("learning_diagnostic_payload", None)
    st.session_state.pop("learning_last_feedback", None)
    st.session_state.pop("learning_last_progress", None)
    st.session_state.pop("learning_last_assessment", None)
    st.session_state.pop("learning_last_export", None)


def _clear_current_chat() -> None:
    st.session_state.messages = []
    st.session_state.cancel_flag = False
    st.session_state.ignore_chat_input_once = True
    st.session_state.pop("vision_active_prompt", None)
    st.session_state.pop("last_response_quality", None)
    st.session_state.pop("last_response_notes", None)
    st.session_state.pop("last_rate_limit_meta", None)
    st.session_state.pop("last_backpressure_meta", None)
    st.session_state.pop("last_provider_retry_meta", None)
    st.session_state.pop("group_chat_notice", None)
    st.session_state.pop("main_chat_input", None)
    st.session_state.pop("learning_last_feedback", None)


def _evaluate_response_outcome(ctx: QuantumRequestContext, response_text: str) -> dict:
    meta = getattr(ctx, "metadata", {}) or {}
    normalized = (response_text or "").lower()
    notes = []

    if ctx.cancelled:
        notes.append("respuesta cancelada")
    if "[error" in normalized or "error en proveedor" in normalized:
        notes.append("error de runtime")
    if "no recuper" in normalized and "fragmento bibliogr" in normalized:
        notes.append("sin soporte bibliográfico fuerte")
    if "conviene reformular la consulta" in normalized:
        notes.append("respuesta reformulativa")
    if meta.get("engine_status") == "LOCAL_FALLBACK" and not meta.get("context_retrieved") and not ctx.wolfram_result:
        notes.append("modo degradado sin evidencia suficiente")
    if ctx.needs_wolfram and not ctx.wolfram_result:
        notes.append("sin resultado simbólico")
    if ctx.intent == "VISUAL" and not meta.get("image_pages"):
        notes.append("sin referencias visuales")

    passed = not notes
    return {
        "passed_socratic": passed,
        "notes": notes,
        "label": "Sólida" if passed else "Parcial",
    }


def _render_session_metric(slot, value: int, label: str) -> None:
    slot.markdown(
        (
            "<div style='text-align: center;'>"
            f"<div style='font-size: 1.5rem; font-weight: bold;'>{value}</div>"
            f"<div style='font-size: 0.6rem; opacity: 0.6;'>{label}</div>"
            "</div>"
        ),
        unsafe_allow_html=True,
    )


def _format_wait_hint(seconds: float) -> str:
    if seconds <= 0:
        return "0.0s"
    if seconds < 60:
        return f"{seconds:.1f}s"
    minutes = int(seconds // 60)
    remainder = seconds % 60
    return f"{minutes}m {remainder:.0f}s"


def _runtime_retry_hint() -> dict:
    provider_retry_seconds = max(float(getattr(tutor, "_provider_retry_seconds", lambda: 0.0)() or 0.0), 0.0)
    return {
        "provider_retry_seconds": provider_retry_seconds,
        "active_cooldown_nodes": int(getattr(tutor, "_active_cooldown_nodes", lambda: 0)() or 0),
    }


def _format_admin_timestamp(epoch_seconds: float) -> str:
    if not epoch_seconds:
        return "-"
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(float(epoch_seconds)))
    except Exception:
        return str(epoch_seconds)


def _streamlit_request_headers() -> dict[str, str]:
    try:
        context = getattr(st, "context", None)
        headers = getattr(context, "headers", None)
        if headers is None:
            return {}
        if hasattr(headers, "items"):
            return {str(key).lower(): str(value) for key, value in headers.items()}
        return {str(key).lower(): str(value) for key, value in dict(headers).items()}
    except Exception:
        return {}


def _admin_hostnames() -> set[str]:
    raw_hosts = os.getenv("QT_ADMIN_HOSTNAMES", "admin.quantumtutor.cl")
    return {
        item.strip().lower()
        for item in raw_hosts.split(",")
        if item.strip()
    }


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _request_hostname() -> str:
    headers = _streamlit_request_headers()
    raw_host = headers.get("x-forwarded-host") or headers.get("host") or ""
    if not raw_host:
        return ""
    return raw_host.split(",")[0].strip().split(":")[0].lower()


def _is_admin_review_host() -> bool:
    headers = _streamlit_request_headers()
    if not headers:
        proxy_mode = _env_flag("QT_TRUST_PROXY_HEADERS", False)
        return _env_flag("QT_ALLOW_ADMIN_REVIEW_ANY_HOST", not proxy_mode)
    host_tier = (headers.get("x-quantum-host-tier", "") or "").strip().lower()
    if host_tier:
        return host_tier == "admin"
    hostname = _request_hostname()
    return bool(hostname and hostname in _admin_hostnames())


def _learning_student_id() -> str:
    return auth.get_user_email() or f"streamlit:{st.session_state.get('session_id', 'anon')}"


def _refresh_learning_route(student_id: str) -> dict:
    route = adaptive_learning.get_personalized_route(student_id)
    st.session_state["learning_route"] = route
    return route


def _refresh_learning_kpis(student_id: str) -> dict:
    kpis = adaptive_learning.get_learning_kpis(student_id)
    st.session_state["learning_kpis"] = kpis
    return kpis


def _refresh_learning_cohort_report() -> dict:
    report = adaptive_learning.get_cohort_report()
    st.session_state["learning_cohort_report"] = report
    return report


def _refresh_learning_insights(*, apply_optimization: bool = False) -> dict:
    insights = adaptive_learning.get_learning_insights(apply_optimization=apply_optimization)
    st.session_state["learning_insights"] = insights
    return insights


def _status_badge_html(label: str, tone: str) -> str:
    palette = {
        "green": ("#0f5132", "#d1e7dd"),
        "yellow": ("#664d03", "#fff3cd"),
        "red": ("#842029", "#f8d7da"),
        "neutral": ("#495057", "#e9ecef"),
    }
    fg, bg = palette.get(tone, palette["neutral"])
    return (
        "<div style='margin-top: 0.35rem;'>"
        f"<span style='display: inline-block; padding: 0.2rem 0.55rem; border-radius: 999px; "
        f"font-size: 0.72rem; font-weight: 700; letter-spacing: 0.03em; color: {fg}; background: {bg};'>"
        f"{label}</span></div>"
    )


def _variant_label(raw_variant: str) -> str:
    normalized = (raw_variant or "unknown").strip().lower()
    if normalized == "challenge":
        return "Challenge"
    if normalized == "control":
        return "Control"
    return normalized.capitalize() or "Unknown"


def _render_admin_security_console(actor_email: str) -> None:
    audit_logger = SecurityEventLogger()
    abuse_store = FileAbusePrevention()
    breaker_store = FileCircuitBreaker()

    tab_events, tab_abuse, tab_breaker, tab_gateway = st.tabs(
        ["Eventos", "Bloqueos", "Circuit Breaker", "Gateway"]
    )

    with tab_events:
        events = audit_logger.read_recent_events(limit=100)
        if not events:
            st.info("Aun no hay eventos de seguridad registrados.")
        else:
            event_rows = []
            for event in events:
                event_rows.append({
                    "timestamp": _format_admin_timestamp(event.get("timestamp", 0.0)),
                    "type": event.get("event_type", ""),
                    "action": event.get("action", ""),
                    "severity": event.get("severity", ""),
                    "actor": event.get("actor", ""),
                    "fields": json.dumps(event.get("fields", {}), ensure_ascii=False),
                })
            st.dataframe(pd.DataFrame(event_rows), width="stretch", hide_index=True)
            st.caption("Log persistente: outputs/logs/security_events.jsonl")

    with tab_abuse:
        abuse_entries = abuse_store.list_entries(limit=200)
        if not abuse_entries:
            st.info("No hay identidades vigiladas por abuso en este momento.")
        else:
            blocked_count = sum(1 for entry in abuse_entries if entry["blocked"])
            col_abuse_1, col_abuse_2 = st.columns(2)
            col_abuse_1.metric("Identidades bloqueadas", blocked_count)
            col_abuse_2.metric("Identidades observadas", len(abuse_entries))
            abuse_rows = []
            for entry in abuse_entries:
                abuse_rows.append({
                    "identifier": entry["identifier"],
                    "blocked": entry["blocked"],
                    "retry_after_seconds": entry["retry_after_seconds"],
                    "score": entry["score"],
                    "block_count": entry["block_count"],
                    "last_reason": entry["last_reason"],
                    "updated_at": _format_admin_timestamp(entry["updated_at"]),
                })
            st.dataframe(pd.DataFrame(abuse_rows), width="stretch", hide_index=True)

            selectable_identities = [entry["identifier"] for entry in abuse_entries]
            selected_identity = st.selectbox(
                "Identidad para desbloqueo manual",
                options=selectable_identities,
                key="admin_unblock_identity",
            )
            if st.button("Desbloquear identidad", key="admin_unblock_identity_btn"):
                if abuse_store.clear_identifier(selected_identity):
                    audit_logger.log_event(
                        event_type="admin_action",
                        action="manual_abuse_unblock",
                        actor=actor_email,
                        fields={"identity": selected_identity},
                    )
                    st.success(f"Identidad desbloqueada: {selected_identity}")
                    st.rerun()
                else:
                    st.warning("La identidad seleccionada ya no estaba bloqueada.")

    with tab_breaker:
        breaker_entries = breaker_store.list_entries()
        if not breaker_entries:
            st.info("No hay providers registrados en el circuit breaker todavia.")
        else:
            active_breakers = sum(1 for entry in breaker_entries if entry["active"])
            col_breaker_1, col_breaker_2 = st.columns(2)
            col_breaker_1.metric("Breakers activos", active_breakers)
            col_breaker_2.metric("Providers vigilados", len(breaker_entries))
            breaker_rows = []
            for entry in breaker_entries:
                breaker_rows.append({
                    "provider": entry["provider"],
                    "state": entry["state"],
                    "blocked": entry["blocked"],
                    "retry_after_seconds": entry["retry_after_seconds"],
                    "failure_count": entry["failure_count"],
                    "failure_threshold": entry["failure_threshold"],
                    "last_failure_category": entry["last_failure_category"],
                })
            st.dataframe(pd.DataFrame(breaker_rows), width="stretch", hide_index=True)

            selected_provider = st.selectbox(
                "Provider para reset manual",
                options=[entry["provider"] for entry in breaker_entries],
                key="admin_reset_breaker_provider",
            )
            if st.button("Reset circuit breaker", key="admin_reset_breaker_btn"):
                breaker_store.reset(selected_provider)
                audit_logger.log_event(
                    event_type="admin_action",
                    action="manual_circuit_breaker_reset",
                    actor=actor_email,
                    fields={"provider": selected_provider},
                )
                st.success(f"Circuit breaker reseteado: {selected_provider}")
                st.rerun()

    with tab_gateway:
        st.caption("Gateway operativo recomendado: Cloudflare Access delante de Nginx.")
        st.code(
            "\n".join([
                "QT_TRUST_PROXY_HEADERS=true",
                "QT_TRUSTED_PROXY_RANGES=127.0.0.1,::1",
                "QT_ADMIN_HOSTNAMES=admin.quantumtutor.cl",
                "QT_ALLOW_ADMIN_REVIEW_ANY_HOST=false",
                "QT_PROVIDER_BREAKER_NAME=gemini_text",
            ]),
            language="bash",
        )
        st.caption("Configs listas en deployment/nginx/quantum_tutor.conf y deployment/cloudflare/.")
        st.caption("Los desbloqueos manuales quedan auditados en security_events.jsonl.")


def _render_learning_intelligence_dashboard() -> None:
    st.markdown("### Learning Intelligence Dashboard")
    st.caption(
        "Vista de decision pedagogica para profesores y admins: estado experimental, "
        "metricas ITS, misconceptions, A/B y recomendaciones accionables."
    )

    if auth.get_role() not in {"admin", "professor"}:
        st.info("Este dashboard solo esta disponible para roles professor/admin.")
        return

    controls_col_1, controls_col_2 = st.columns([2, 1])
    with controls_col_1:
        apply_optimization = st.checkbox(
            "Aplicar loop de optimizacion durante esta actualizacion",
            key="learning_dashboard_apply_optimization",
            value=False,
        )
    with controls_col_2:
        st.write("")
        st.write("")
        if st.button("Actualizar dashboard", key="learning_dashboard_refresh_btn", width="stretch"):
            _refresh_learning_insights(apply_optimization=apply_optimization)

    insights_snapshot = st.session_state.get("learning_insights", {}) or {}
    if not insights_snapshot:
        insights_snapshot = _refresh_learning_insights(apply_optimization=apply_optimization)

    dashboard_view = build_dashboard_view(insights_snapshot)
    system_status = dashboard_view["system_status"]

    st.divider()
    st.subheader("Estado del sistema")
    status_col_1, status_col_2, status_col_3, status_col_4 = st.columns(4)
    status_col_1.metric("Experimento activo", system_status["experiment_name"])
    status_col_2.metric("Muestra actual", system_status["sample_size"], delta=f"min {system_status['min_sample']}")
    status_col_3.metric("Completado", f"{system_status['sample_progress_percent']:.1f}%")
    status_col_4.metric("Readiness", system_status["readiness"])

    readiness_message = system_status["explanation"]
    if system_status["readiness"] == "HIGH":
        st.success(readiness_message)
    elif system_status["readiness"] == "MEDIUM":
        st.warning(readiness_message)
    else:
        st.error(readiness_message)

    st.caption(
        f"Metrica primaria: {system_status['primary_metric']} | "
        f"Ventana: {system_status['window_days']} dias | "
        f"Evaluacion lista: {'si' if system_status['evaluation_ready'] else 'no'}"
    )
    if not system_status["window_complete"]:
        st.caption(f"Tiempo estimado para cerrar la ventana: {system_status['days_until_ready']:.2f} dias")

    st.divider()
    st.subheader("Metricas clave")
    metric_columns = st.columns(4)
    for slot, metric in zip(metric_columns, dashboard_view["metrics"]):
        with slot:
            st.metric(metric["label"], metric["display"])
            st.markdown(_status_badge_html(metric["status_label"], metric["tone"]), unsafe_allow_html=True)
            st.caption(metric["help"])

    st.divider()
    st.subheader("Top problemas pedagogicos")
    issue_rows = dashboard_view["top_issues"]
    if issue_rows:
        issue_df = pd.DataFrame(issue_rows)
        st.bar_chart(
            issue_df.set_index("display_label")[["share_percent"]],
            height=280,
        )
        st.dataframe(
            issue_df[["module_title", "misconception_label", "share_percent", "student_count"]],
            width="stretch",
            hide_index=True,
        )
    else:
        st.success("No aparecen misconceptions dominantes con masa critica en las cohortes actuales.")

    st.divider()
    st.subheader("Comparacion A/B")
    ab_test = dashboard_view["ab_test"]
    ab_rows = ab_test["rows"]
    if ab_rows:
        ab_table = []
        for row in ab_rows:
            ab_table.append({
                "Variante": _variant_label(row["variant"]),
                "Estudiantes": row["student_count"],
                "Learning Gain": f"{float(row.get('learning_gain_avg', 0.0) or 0.0) * 100:.1f} pts"
                if row.get("learning_gain_avg") is not None else "Sin datos",
                "Time to Mastery": f"{float(row.get('time_to_mastery_avg_days', 0.0) or 0.0):.2f} d"
                if row.get("time_to_mastery_avg_days") is not None else "Sin datos",
                "Retention": f"{float(row.get('retention_score_avg', 0.0) or 0.0) * 100:.1f}%"
                if row.get("retention_score_avg") is not None else "Sin datos",
                "Misconception Resolution": f"{float(row.get('misconception_resolution_rate_avg', 0.0) or 0.0) * 100:.1f}%"
                if row.get("misconception_resolution_rate_avg") is not None else "Sin datos",
            })
        st.table(pd.DataFrame(ab_table))
        if ab_test.get("winner_variant"):
            st.success(f"Mejor variante observada: {_variant_label(ab_test['winner_variant'])}")
        st.caption(ab_test["insight"])
    else:
        st.info("Aun no hay suficiente data para comparar variantes.")

    st.divider()
    st.subheader("Recomendaciones automaticas")
    recommendations = dashboard_view["recommendations"]
    if recommendations:
        for recommendation in recommendations:
            message = (
                f"{recommendation['module_title']} | {recommendation['persona_label']} | "
                f"{_variant_label(recommendation['variant'])}\n\n"
                f"Problema: {recommendation['issue']}. "
                f"Misconception dominante: {recommendation['misconception_label']}. "
                f"Accion sugerida: {recommendation['recommendation']}"
            )
            if recommendation["severity"] == "CRITICO":
                st.warning(message)
            else:
                st.info(message)
    else:
        st.info("No hay recomendaciones automaticas nuevas para mostrar.")

    st.divider()
    st.subheader("Cohortes criticas")
    cohort_col_1, cohort_col_2 = st.columns(2)
    worst = dashboard_view["critical_cohorts"]["worst"] or {}
    best = dashboard_view["critical_cohorts"]["best"] or {}

    with cohort_col_1:
        with st.container(border=True):
            st.markdown("#### Peor performance")
            if worst:
                st.caption(
                    f"{worst.get('module_title', 'Sin modulo')} | {worst.get('persona_label', 'Exploracion')} | "
                    f"{_variant_label(worst.get('variant', 'unknown'))}"
                )
                st.caption(f"Misconception: {worst.get('misconception_label', 'Sin dato')}")
                st.caption(f"Health score: {float(worst.get('health_score', 0.0) or 0.0):.2f}")
                st.write(worst.get("human_recommendation", worst.get("recommendation", "")))
            else:
                st.caption("Sin datos suficientes.")

    with cohort_col_2:
        with st.container(border=True):
            st.markdown("#### Mejor performance")
            if best:
                st.caption(
                    f"{best.get('module_title', 'Sin modulo')} | {best.get('persona_label', 'Exploracion')} | "
                    f"{_variant_label(best.get('variant', 'unknown'))}"
                )
                st.caption(f"Misconception: {best.get('misconception_label', 'Sin dato')}")
                st.caption(f"Health score: {float(best.get('health_score', 0.0) or 0.0):.2f}")
                st.write(best.get("human_recommendation", best.get("recommendation", "")))
            else:
                st.caption("Sin datos suficientes.")


current_auth_user = auth.get_user_email() or "streamlit_user"
if st.session_state.get("_auth_bound_user") != current_auth_user:
    _rotate_user_session()
    st.session_state["_auth_bound_user"] = current_auth_user

if "sidebar_action" not in st.session_state:
    st.session_state.sidebar_action = ""
if "sidebar_chat_search" not in st.session_state:
    st.session_state.sidebar_chat_search = ""
if "last_response_quality" not in st.session_state:
    st.session_state.last_response_quality = "unknown"
if "last_response_notes" not in st.session_state:
    st.session_state.last_response_notes = []
if "group_chat_notice" not in st.session_state:
    st.session_state.group_chat_notice = ""
if "last_rate_limit_meta" not in st.session_state:
    st.session_state.last_rate_limit_meta = {}
if "last_backpressure_meta" not in st.session_state:
    st.session_state.last_backpressure_meta = {}
if "last_provider_retry_meta" not in st.session_state:
    st.session_state.last_provider_retry_meta = {}
if "learning_diagnostic_payload" not in st.session_state:
    st.session_state.learning_diagnostic_payload = None
if "learning_last_feedback" not in st.session_state:
    st.session_state.learning_last_feedback = []
if "learning_last_progress" not in st.session_state:
    st.session_state.learning_last_progress = {}
if "learning_kpis" not in st.session_state:
    st.session_state.learning_kpis = {}
if "learning_last_assessment" not in st.session_state:
    st.session_state.learning_last_assessment = {}
if "learning_cohort_report" not in st.session_state:
    st.session_state.learning_cohort_report = {}
if "learning_insights" not in st.session_state:
    st.session_state.learning_insights = {}
if "learning_last_export" not in st.session_state:
    st.session_state.learning_last_export = {}

# Fetch de Session State Seguro via asyncio run
try:
    session_data = asyncio.run(st.session_state.session_store.get_or_create(
        st.session_state.session_id,
        lambda: create_session_state(str(BASE_DIR))
    ))
except RuntimeError:
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as _ex:
        session_data = _ex.submit(lambda: asyncio.run(st.session_state.session_store.get_or_create(
            st.session_state.session_id,
            lambda: create_session_state(str(BASE_DIR))
        ))).result()

analytics = session_data["analytics"]
learning_student_id = _learning_student_id()
learning_route = _refresh_learning_route(learning_student_id)
learning_route_summary = summarize_route(learning_route)
learning_kpis = _refresh_learning_kpis(learning_student_id)
learning_kpi_summary = summarize_kpis(learning_kpis)
learning_cohort_report = _refresh_learning_cohort_report()
learning_cohort_summary = summarize_cohort_report(learning_cohort_report)
learning_insights = {}
if auth.get_role() in {"admin", "professor"}:
    learning_insights = _refresh_learning_insights(apply_optimization=False)

# BUG-05 FIX: inicializar stats ANTES de cualquier bloque que lo lea
if "stats" not in st.session_state:
    st.session_state.stats = {"wolfram_hits": 0, "rag_queries": 0}
if "ignore_chat_input_once" not in st.session_state:
    st.session_state.ignore_chat_input_once = False

# FEATURE: Verificación de API keys (una vez por sesión de servidor)
if not tutor._key_check_done:
    try:
        asyncio.run(tutor._startup_key_check())
    except RuntimeError:
        import concurrent.futures as _cf
        with _cf.ThreadPoolExecutor(max_workers=1) as _ex:
            _ex.submit(lambda: asyncio.run(tutor._startup_key_check())).result(timeout=60)

if "_rag_encoder_status" not in st.session_state:
    with st.spinner("Preparando índice semántico..."):
        try:
            encoder = tutor.rag.encoder
            st.session_state["_rag_encoder_status"] = "READY" if encoder else "KEYWORD_FALLBACK"
        except Exception:
            st.session_state["_rag_encoder_status"] = "KEYWORD_FALLBACK"

if "engine_status" not in st.session_state:
    st.session_state.engine_status = "HYBRID_RELATIONAL" if tutor.llm_enabled and tutor.client else "LOCAL_FALLBACK"

# Sidebar: Estado del Sistema y Analítica
wolfram_metric_slot = None
rag_metric_slot = None

with st.sidebar:
    st.markdown(
        """
        <div style='text-align: center; padding-bottom: 20px;'>
            <h2 style='color: #d4af37; margin: 0;'>Quantum Tutor System</h2>
            <p style='font-size: 0.8rem; opacity: 0.7;'>Entorno Profesional</p>
        </div>
        """,
        unsafe_allow_html=True
    )

    # Botones principales
    if st.button("📝 Nuevo chat", width="stretch"):
        _clear_current_chat()
        st.session_state.sidebar_action = "new_chat"
        st.toast("Chat actual limpiado. La sesión activa se conserva.")
    if st.button("🔍 Buscar chats", width="stretch"):
        st.session_state.sidebar_action = "search"

    runtime_retry = _runtime_retry_hint()
    if False and runtime_retry["provider_retry_seconds"] > 0:
        st.caption(
            "â±ï¸ Proximo reintento proveedor: "
            f"{_format_wait_hint(runtime_retry['provider_retry_seconds'])}"
            f" | nodos en cooldown: {runtime_retry['active_cooldown_nodes']}"
        )

    last_rate_limit_meta = st.session_state.get("last_rate_limit_meta", {}) or {}
    if False and last_rate_limit_meta.get("limited"):
        st.caption(
            "ðŸª£ Bucket usuario: reintento estimado en "
            f"{_format_wait_hint(float(last_rate_limit_meta.get('retry_after_seconds', 0.0) or 0.0))}"
        )

    last_backpressure_meta = st.session_state.get("last_backpressure_meta", {}) or {}
    if False and last_backpressure_meta.get("limited"):
        st.caption(
            "ðŸš¦ Cola del proveedor: reintento estimado en "
            f"{_format_wait_hint(float(last_backpressure_meta.get('retry_after_seconds', 0.0) or 0.0))}"
        )

    if runtime_retry["provider_retry_seconds"] > 0:
        st.caption(
            "Proximo reintento del proveedor en "
            f"{_format_wait_hint(runtime_retry['provider_retry_seconds'])}"
            f" | nodos en cooldown: {runtime_retry['active_cooldown_nodes']}"
        )
    if last_rate_limit_meta.get("limited"):
        st.caption(
            "Bucket por usuario en recuperacion: "
            f"{_format_wait_hint(float(last_rate_limit_meta.get('retry_after_seconds', 0.0) or 0.0))}"
        )
    if last_backpressure_meta.get("limited"):
        st.caption(
            "Cola del proveedor en recuperacion: "
            f"{_format_wait_hint(float(last_backpressure_meta.get('retry_after_seconds', 0.0) or 0.0))}"
        )

    st.divider()

    # Model Selector Clásico
    st.selectbox("🔬 Modelo Cognitivo", ["General (Rápido)", "Científico (Profundo)", "Matemático (Experimental)"])
    
    st.divider()

    # Menú estilo ChatGPT
    st.markdown("### Herramientas")
    if st.button("🖼️ Imágenes", width="stretch"):
        st.session_state.sidebar_action = "images"
    if st.button("⊞ Aplicaciones", width="stretch"):
        st.session_state.sidebar_action = "apps"
    if st.button("🔭 Investigación avanzada", width="stretch"):
        st.session_state.sidebar_action = "research"
    if st.button("⌨️ Codex", width="stretch"):
        st.session_state.sidebar_action = "codex"

    st.divider()

    # Historial Mock
    st.markdown("### Tus chats")
    mock_history = [
        "Mecánica Cuántica PDF", 
        "Base bibliográfica conmutadores", 
        "Prueba manual de app",
        "Personalización maestra GEM",
        "Consulta en LaTeX Cuántica",
        "Personalización IA CV"
    ]
    filtered_history = mock_history
    current_sidebar_action = st.session_state.get("sidebar_action", "")

    if current_sidebar_action == "search":
        st.caption("Busca dentro del historial local disponible.")
        search_query = st.text_input(
            "Filtrar chats",
            key="sidebar_chat_search",
            placeholder="Ej: conmutadores"
        )
        filtered_history = [m for m in mock_history if search_query.lower() in m.lower()]
        if not filtered_history:
            st.caption("Sin coincidencias en el historial visible.")
    elif current_sidebar_action == "images":
        st.info("Explorador visual activo.")
        st.caption(
            "Referencias indexadas: "
            f"Galindo {len(tutor.rag.available_images['galindo'])} · "
            f"Cohen {len(tutor.rag.available_images['cohen'])} · "
            f"Sakurai {len(tutor.rag.available_images['sakurai'])}"
        )
        st.caption("Sugerencia: pide una figura y, si quieres, nombra el autor.")
    elif current_sidebar_action == "apps":
        st.info("Aplicaciones del runtime disponibles.")
        st.caption("RAG bibliográfico, parser visual, Wolfram emulado y scheduler adaptativo.")
    elif current_sidebar_action == "research":
        st.info("Diagnóstico avanzado del runtime.")
        st.caption(f"Motor de respuesta: {st.session_state.get('engine_status', 'HYBRID_RELATIONAL')}")
        st.caption(f"Encoder semántico: {st.session_state.get('_rag_encoder_status', 'UNKNOWN')}")
        st.caption(f"Última respuesta: {st.session_state.get('last_response_quality', 'unknown')}")
    elif current_sidebar_action == "learning":
        st.info("Ruta pedagógica activa.")
        st.caption(f"Nivel actual: {learning_route_summary['current_level_label']}")
        st.caption(f"Próximo nodo: {learning_route_summary['next_node_title']}")
        st.caption(f"Milestone activo: {learning_route_summary['next_milestone_label']}")
        st.caption(f"Finalización: {learning_kpi_summary['completion_percent']:.1f}%")
    elif current_sidebar_action == "codex":
        st.info("Modo Codex informativo.")
        st.caption("Este panel resume el estado local del runtime y las pruebas del workspace.")
    elif current_sidebar_action == "group_chat":
        st.warning("Chat de grupo en vista previa. Aún no hay orquestación multiusuario activa.")
    elif current_sidebar_action == "new_chat":
        st.caption("El chat quedó limpio. Puedes iniciar una conversación nueva sin rotar la sesión.")

    for m in filtered_history:
        st.markdown(f"<div style='padding: 4px 0; color: #aaa; font-size: 0.9em; cursor: pointer;'>• {m}</div>", unsafe_allow_html=True)

    st.divider()
    
    # Iniciar chat de grupo flotante/bottom
    if st.button("👥 Iniciar un chat de grupo", width="stretch"):
        st.session_state.sidebar_action = "group_chat"
        st.session_state.group_chat_notice = "Chat de grupo en vista previa. La coordinación multiusuario aún no está habilitada."
    st.divider()

    # User Card
    _role = auth.get_role()
    _role_icons = {"student": "🎓", "professor": "👨\u200d🏫", "admin": "🛡️"}
    _role_labels = {"student": "Estudiante", "professor": "Profesor", "admin": "Admin"}
    display_name = auth.get_display_name() or auth.get_user_email()
    st.markdown(
        f"""
        <div style='background: rgba(255,255,255,0.05); border: 1px solid rgba(212,175,55,0.2); 
                    border-radius: 15px; padding: 15px; margin-bottom: 20px;'>
            <div style='font-size: 0.75rem; color: #d4af37; text-transform: uppercase;'>Usuario Activo</div>
            <div style='font-weight: 600; font-size: 1.1rem;'>{display_name}</div>
            <div style='margin-top: 5px;'>
                <span style='background: rgba(212,175,55,0.1); border-radius: 10px; padding: 2px 8px; font-size: 0.7rem;'>
                    {_role_icons.get(_role,'🎓')} {_role_labels.get(_role,'Estudiante')}
                </span>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    
    # Session Metrics Card (BUG-05: stats already initialized at top)
    col_m1, col_m2 = st.columns(2)
    with col_m1:
        wolfram_metric_slot = st.empty()
        _render_session_metric(wolfram_metric_slot, st.session_state.stats["wolfram_hits"], "W-CALLS")
    with col_m2:
        rag_metric_slot = st.empty()
        _render_session_metric(rag_metric_slot, st.session_state.stats["rag_queries"], "RAG-ANCHORS")

    # FEATURE: API Key Health Monitor
    st.divider()
    st.markdown("<h4 style='color: #d4af37;'>🔑 API Key Health</h4>", unsafe_allow_html=True)
    _health_icons = {"OK": "✅", "RATE_LIMIT": "⚠️", "INVALID": "❌", "TIMEOUT": "⏱️", "ERROR": "⚠️", "UNKNOWN": "❓"}
    if tutor.key_health:
        for idx, (key, status) in enumerate(tutor.key_health.items()):
            icon = _health_icons.get(status, "❓")
            short = f"{key[:6]}...{key[-3:]}"
            st.caption(f"{icon} Nodo {idx}: `{short}` — {status}")
    else:
        st.caption("Sin claves configuradas.")

    st.divider()

    # Cognitive Profiler Section
    st.markdown("<h4 style='color: #d4af37;'>🧠 Learning Analytics</h4>", unsafe_allow_html=True)
    clusters = analytics.get_misconception_clusters()

    if st.session_state.get("engine_status") == "LOCAL_FALLBACK" or st.session_state.get("last_response_quality") == "Parcial":
        st.warning("Analítica en observación: la última respuesta fue parcial o degradada.")
    
    if any(clusters.values()):
        # Dominados
        if clusters["Dominado"]:
            st.success(f"**Dominado:** {', '.join(clusters['Dominado'])}")
        # Alertas
        if clusters["Error_Conceptual"] or clusters["Falla_Base"]:
            with st.container(border=True):
                st.markdown("<div style='color: #ff4b4b; font-size: 0.8rem; font-weight: bold;'>PUNTOS DE DOLOR</div>", unsafe_allow_html=True)
                for item in (clusters["Error_Conceptual"] + clusters["Falla_Base"]):
                    st.markdown(f"• {item}")
    else:
        st.info("Explora conceptos para generar tu perfil cognitivo.")

    st.divider()
    st.markdown("<h4 style='color: #d4af37;'>🧭 Learning Journey</h4>", unsafe_allow_html=True)
    col_l1, col_l2 = st.columns(2)
    col_l1.metric("Nivel", learning_route_summary["current_level_label"])
    col_l2.metric("Puntos", learning_route_summary["points"])
    st.caption(
        "Siguiente foco: "
        f"{learning_route_summary['next_node_title']} | "
        f"Milestone activo: {learning_route_summary['next_milestone_label']}"
    )
    st.caption(
        f"Avance global: {learning_kpi_summary['completion_percent']:.1f}% | "
        f"Eventos auto desde chat: {learning_kpi_summary['chat_learning_events']}"
    )
    if not learning_route_summary["diagnostic_completed"]:
        st.info("Aun no completas el diagnostico inicial. Ve a la pestaña Learning Journey para personalizar la ruta.")
    elif learning_route.get("next_node"):
        st.caption(learning_route.get("next_node", {}).get("summary", ""))
    if st.button("🧪 Abrir Learning Journey", width="stretch"):
        st.session_state.sidebar_action = "learning"

    # Relational Convergence (Modernized)
    if st.session_state.get("relational_data"):
        rd = st.session_state.relational_data
        st.divider()
        st.markdown("<h4 style='color: #d4af37;'>🌀 Convergence</h4>", unsafe_allow_html=True)
        st.progress(rd["convergence"], text=f"{rd['omega_class']}")
        st.caption(f"Topic: {rd['attractor']}")

    # Footer Actions
    st.divider()
    
    if st.button("🔄 Nueva Sesión", width="stretch"):
        _rotate_user_session()
        st.rerun()

    if st.button("🚪 Cerrar Sesión", type="secondary", width="stretch"):
        _rotate_user_session()
        st.session_state.pop("_auth_bound_user", None)
        auth.logout()

    if False and auth.get_role() == "admin":
        with st.expander("🛡️ Admin Console"):
            if st.button("Reset Global Cache"):
                st.toast("Caché reseteada.")

# Área Principal — envuelta en .eic-app-main para CSS scoping
if auth.get_role() == "admin":
    if _is_admin_review_host():
        with st.expander("Admin Security Review"):
            _render_admin_security_console(auth.get_user_email() or "admin")
    else:
        st.caption("Admin Security Review solo se habilita en admin.quantumtutor.cl.")

st.markdown("<div class='eic-app-main'>", unsafe_allow_html=True)
st.caption(f"{APP_NAME} | Runtime actual: {RUNTIME_VERSION}")
st.markdown("<h1 class='celestial-title'>⚛️ Quantum Tutor Avanzado</h1>", unsafe_allow_html=True)
st.caption("Advanced Quantum Intelligence System | Galindo & Pascual • Cohen-Tannoudji • J.J. Sakurai | Entorno Profesional")

if st.session_state.get("engine_status") == "LOCAL_FALLBACK":
    st.warning("Modo local de contingencia activo. Las respuestas pueden llegar sin cálculo simbólico o sin referencias visuales sólidas.")
elif st.session_state.get("_rag_encoder_status") == "KEYWORD_FALLBACK":
    st.info("El encoder semántico no quedó disponible; el RAG está operando con coincidencias más básicas.")

if st.session_state.get("last_response_quality") == "Parcial" and st.session_state.get("last_response_notes"):
    st.caption("Última respuesta parcial: " + ", ".join(st.session_state["last_response_notes"]))

if st.session_state.get("engine_status") == "RATE_LIMITED_LOCAL":
    retry_after = float((st.session_state.get("last_rate_limit_meta", {}) or {}).get("retry_after_seconds", 0.0) or 0.0)
    st.warning(f"Guard de consumo activo. El bucket por usuario se recupera en {_format_wait_hint(retry_after)}.")

if st.session_state.get("engine_status") == "BACKPRESSURE_LOCAL":
    retry_after = float((st.session_state.get("last_backpressure_meta", {}) or {}).get("retry_after_seconds", 0.0) or 0.0)
    st.warning(f"Backpressure activo. La cola del proveedor deberia aliviarse en {_format_wait_hint(retry_after)}.")

if st.session_state.get("engine_status") == "CIRCUIT_BREAKER_LOCAL":
    retry_after = float((st.session_state.get("last_provider_retry_meta", {}) or {}).get("retry_after_seconds", 0.0) or 0.0)
    st.warning(f"Circuit breaker activo. El proveedor se reintentara en {_format_wait_hint(retry_after)}.")

if st.session_state.get("engine_status") == "PRECOMPUTED_LOCAL":
    st.info("Respuesta servida desde contenido precomputado para ahorrar cuota y latencia.")

if st.session_state.get("engine_status") == "DETERMINISTIC_LOCAL":
    st.info("Respuesta resuelta por motor local deterministico, sin consumo de API externa.")

provider_retry_meta = st.session_state.get("last_provider_retry_meta", {}) or {}
if provider_retry_meta.get("scheduled"):
    st.caption(
        "Proveedor con reintento programado en "
        f"{_format_wait_hint(float(provider_retry_meta.get('retry_after_seconds', 0.0) or 0.0))}."
    )

if st.session_state.get("group_chat_notice"):
    st.info(st.session_state["group_chat_notice"])

# Botones de Scroll — iframe-aware (Streamlit runs inside an iframe)
st.components.v1.html(
    """
    <script>
    (function() {
        const pdoc = window.parent.document;

        if (!pdoc.getElementById('eic-scroll-style')) {
            const style = pdoc.createElement('style');
            style.id = 'eic-scroll-style';
            style.textContent = `
                .eic-scroll-btn {
                    position: fixed;
                    right: 20px;
                    background: #2a2a35;
                    color: white;
                    border: 1px solid #444;
                    border-radius: 50%;
                    width: 40px;
                    height: 40px;
                    font-size: 18px;
                    cursor: pointer;
                    z-index: 99999;
                    opacity: 0.82;
                    transition: opacity 0.2s, background 0.2s;
                    display: flex;
                    align-items: center;
                    justify-content: center;
                    line-height: 1;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.18);
                }
                .eic-scroll-btn:hover { opacity: 1; background: #3a3a45; }
                #eic-scroll-top { bottom: 88px; }
                #eic-scroll-bottom { bottom: 36px; }
            `;
            pdoc.head.appendChild(style);
        }

        function ensureButton(id, label, title) {
            let btn = pdoc.getElementById(id);
            if (!btn) {
                btn = pdoc.createElement('button');
                btn.id = id;
                btn.className = 'eic-scroll-btn';
                btn.type = 'button';
                btn.textContent = label;
                btn.setAttribute('aria-label', title);
                btn.title = title;
                pdoc.body.appendChild(btn);
            }
            return btn;
        }

        function getScrollTop(target) {
            if (!target || target === window) {
                return pdoc.defaultView.pageYOffset || pdoc.documentElement.scrollTop || pdoc.body.scrollTop || 0;
            }
            if (target === pdoc.documentElement || target === pdoc.body || target === pdoc.scrollingElement) {
                return pdoc.defaultView.pageYOffset || target.scrollTop || 0;
            }
            return target.scrollTop || 0;
        }

        function getScrollHeight(target) {
            if (!target || target === window || target === pdoc.documentElement || target === pdoc.body || target === pdoc.scrollingElement) {
                return Math.max(
                    pdoc.documentElement.scrollHeight || 0,
                    pdoc.body ? pdoc.body.scrollHeight || 0 : 0
                );
            }
            return target.scrollHeight || 0;
        }

        function getClientHeight(target) {
            if (!target || target === window || target === pdoc.documentElement || target === pdoc.body || target === pdoc.scrollingElement) {
                return pdoc.documentElement.clientHeight || pdoc.defaultView.innerHeight || 0;
            }
            return target.clientHeight || 0;
        }

        function isScrollable(target) {
            return getScrollHeight(target) - getClientHeight(target) > 40;
        }

        function getScrollContainer() {
            const candidates = [
                pdoc.querySelector('section.main'),
                pdoc.querySelector('.main'),
                pdoc.querySelector('[data-testid="stAppViewContainer"]'),
                pdoc.scrollingElement,
                pdoc.documentElement,
                pdoc.body,
                window,
            ].filter(Boolean);

            for (const candidate of candidates) {
                if (isScrollable(candidate)) {
                    return candidate;
                }
            }

            return candidates[0] || pdoc.documentElement;
        }

        function scrollToPosition(target, top) {
            if (!target || target === window || target === pdoc.documentElement || target === pdoc.body || target === pdoc.scrollingElement) {
                pdoc.defaultView.scrollTo({ top: top, behavior: 'smooth' });
                return;
            }
            target.scrollTo({ top: top, behavior: 'smooth' });
        }

        const topBtn = ensureButton('eic-scroll-top', '↑', 'Ir al inicio');
        const bottomBtn = ensureButton('eic-scroll-bottom', '↓', 'Ir al final');

        topBtn.onclick = function() {
            var el = getScrollContainer();
            scrollToPosition(el, 0);
        };

        bottomBtn.onclick = function() {
            var el = getScrollContainer();
            scrollToPosition(el, getScrollHeight(el));
        };
    })();
    </script>
    """,
    height=0,
    scrolling=False
)

# --- Estructura de Navegación por Pestañas ---
tab_chat, tab_learning, tab_analytics, tab_evaluacion, tab_admin_dashboard = st.tabs(
    ["✨ Interfaz de Sesión Cuántica", "🧭 Learning Journey", "📊 Dashboard Analítico", "📝 Evaluación Externa", "Admin Dashboard"]
)

with tab_chat:
    # Historial de Chat e Inicialización
    if "messages" not in st.session_state:
        st.session_state.messages = []
    # BUG-05 FIX: stats already initialized above, no duplicate needed

    def render_message_with_references(role, content, image_pages=None):
        with st.chat_message(role):
            st.markdown(content)
            
            # Si es el asistente, mostrar referencias visuales
            if role == "assistant":
                import re
                pages_to_show = []
                
                if image_pages:
                    # BUG-FIX: No usar sorted() para mantener el orden de relevancia del RAG
                    pages_to_show = list(dict.fromkeys(image_pages))
                else:
                    # Extraer el identificador completo: page_123, cohen_page_123, o sakurai_page_123
                    matches = re.findall(r'references/(cohen_page_\d+|sakurai_page_\d+|page_\d+)\.png', content)
                    if matches:
                        pages_to_show = list(dict.fromkeys(matches))
                
                if pages_to_show:
                    st.divider()
                    st.subheader("📖 Referencias Bibliográficas")
                    cols = st.columns(min(3, len(pages_to_show)))
                    
                    for i, page_num in enumerate(pages_to_show):
                        img_path = reference_viz.get_page_image(page_num)
                        
                        # Formatear el label de la página
                        page_label = str(page_num).replace("cohen_page_", "Cohen ").replace("sakurai_page_", "Sakurai ").replace("page_", "Galindo ")
                        if isinstance(page_num, int) or page_num.isdigit():
                            page_label = f"Galindo {page_num}"
                        page_label = _format_reference_page_label(page_num)
                            
                        if img_path:
                            with cols[i % len(cols)]:
                                with st.container(border=True):
                                    st.image(img_path, caption=f"Extracto: {page_label}", width="stretch")
                                    with st.expander("Maximizar Documento"):
                                        st.image(img_path, width="stretch")

    # Renderizar Historial
    for message in st.session_state.messages:
        render_message_with_references(
            message["role"],
            message["content"],
            image_pages=message.get("image_pages")
        )

with tab_learning:
    route_snapshot = st.session_state.get("learning_route", learning_route)
    route_summary_snapshot = summarize_route(route_snapshot)
    kpis_snapshot = st.session_state.get("learning_kpis", learning_kpis)
    kpi_summary_snapshot = summarize_kpis(kpis_snapshot)
    last_feedback = st.session_state.get("learning_last_feedback", []) or []
    last_progress = st.session_state.get("learning_last_progress", {}) or {}
    last_assessment = st.session_state.get("learning_last_assessment", {}) or {}

    st.markdown("### 🧭 Learning Journey")
    st.caption("Diagnostico adaptativo, milestones y remediacion guiada sobre tu progreso actual.")

    col_lm1, col_lm2, col_lm3, col_lm4, col_lm5 = st.columns(5)
    col_lm1.metric("Nivel", route_summary_snapshot["current_level_label"])
    col_lm2.metric("Persona", route_summary_snapshot["persona_label"])
    col_lm3.metric("Dominio global", f"{route_summary_snapshot['overall_mastery_percent']:.1f}%")
    col_lm4.metric("Puntos", route_summary_snapshot["points"])
    col_lm5.metric("Badges", route_summary_snapshot["badge_count"])

    col_k1, col_k2, col_k3, col_k4 = st.columns(4)
    col_k1.metric("Finalizacion", f"{kpi_summary_snapshot['completion_percent']:.1f}%")
    col_k2.metric("Progreso por nodo", f"{kpi_summary_snapshot['average_node_progress_percent']:.1f}%")
    col_k3.metric("Milestones", kpi_summary_snapshot["milestones_text"])
    col_k4.metric("Eventos desde chat", kpi_summary_snapshot["chat_learning_events"])
    col_k5, col_k6, col_k7, col_k8 = st.columns(4)
    col_k5.metric("Repasos vencidos", route_summary_snapshot["due_review_count"])
    col_k6.metric("Dificultad", kpi_summary_snapshot["recommended_difficulty"])
    col_k7.metric("Precision reciente", f"{kpi_summary_snapshot['recent_accuracy_percent']:.1f}%")
    col_k8.metric("Misconceptions", kpi_summary_snapshot["misconception_count"])
    if kpi_summary_snapshot["experiment_variant"]:
        st.caption(
            f"Experimento activo: {kpi_summary_snapshot['experiment_name']} / "
            f"variante {kpi_summary_snapshot['experiment_variant']}"
        )
        if kpi_summary_snapshot["experiment_variant"] == "challenge":
            st.info("Modo challenge activo: priorizamos señales de progreso, hitos y motivación visible.")
        else:
            st.caption("Modo control activo: experiencia base con gamificación mínima.")

    st.caption(
        f"Mastery para avanzar: {route_summary_snapshot['mastery_threshold_percent']:.1f}% | "
        f"Nodos bloqueados por prerequisitos: {route_summary_snapshot['blocked_node_count']}"
    )
    if route_summary_snapshot["review_due_now"]:
        st.warning("Hay repasos vencidos en la cola. El siguiente paso prioriza retencion antes de abrir contenido nuevo.")
    elif route_summary_snapshot["next_review_title"]:
        st.caption(f"Proximo repaso sugerido: {route_summary_snapshot['next_review_title']}")

    st.divider()
    st.subheader("KPIs y evaluacion")
    col_assess_1, col_assess_2, col_assess_3 = st.columns(3)
    with col_assess_1:
        assessment_type = st.selectbox(
            "Tipo de evaluacion",
            ["posttest", "pretest"],
            key="learning_assessment_type",
        )
    with col_assess_2:
        assessment_score = st.slider(
            "Puntaje",
            min_value=0.0,
            max_value=1.0,
            value=0.75,
            step=0.01,
            key="learning_assessment_score",
        )
    with col_assess_3:
        assessment_label = st.text_input(
            "Etiqueta",
            value="Modulo actual",
            key="learning_assessment_label",
        )

    assessment_notes = st.text_area(
        "Notas de evaluacion",
        placeholder="Observaciones del modulo, pilotaje o postest.",
        key="learning_assessment_notes",
    )
    if st.button("Guardar evaluacion", key="learning_save_assessment_btn", width="stretch"):
        st.session_state.learning_last_assessment = adaptive_learning.record_assessment_score(
            learning_student_id,
            assessment_type=assessment_type,
            score=assessment_score,
            label=assessment_label,
            notes=assessment_notes,
        )
        st.session_state.learning_kpis = adaptive_learning.get_learning_kpis(learning_student_id)
        st.session_state.learning_cohort_report = adaptive_learning.get_cohort_report()
        st.rerun()

    if last_assessment.get("assessment_type"):
        st.success(
            "Evaluacion guardada: "
            f"{last_assessment['assessment_type']} = {float(last_assessment['score']) * 100:.1f}%"
        )

    pretest_text = (
        f"{kpi_summary_snapshot['pretest_percent']:.1f}%"
        if kpi_summary_snapshot["pretest_percent"] is not None
        else "Pendiente"
    )
    posttest_text = (
        f"{kpi_summary_snapshot['posttest_percent']:.1f}%"
        if kpi_summary_snapshot["posttest_percent"] is not None
        else "Pendiente"
    )
    improvement_text = (
        f"{kpi_summary_snapshot['improvement_points']:+.1f} pts"
        if kpi_summary_snapshot["improvement_points"] is not None
        else "Pendiente"
    )
    st.caption(
        f"Pretest: {pretest_text} | Posttest: {posttest_text} | Mejora: {improvement_text}"
    )

    if kpis_snapshot.get("assessment_history"):
        with st.expander("Historial de evaluaciones"):
            for item in reversed(kpis_snapshot.get("assessment_history", [])):
                st.caption(
                    f"{item.get('assessment_type', '')}: {float(item.get('score', 0.0)) * 100:.1f}% | "
                    f"{item.get('label', '')}"
                )

    st.divider()
    st.subheader("Diagnostico inicial")
    diag_col_1, diag_col_2, diag_col_3 = st.columns(3)
    with diag_col_1:
        diag_goal = st.selectbox(
            "Objetivo",
            ["fundamentos", "formalismo", "aplicaciones"],
            key="learning_goal_select",
        )
    with diag_col_2:
        diag_target = st.selectbox(
            "Nivel objetivo",
            ["beginner", "intermediate", "advanced"],
            key="learning_target_level_select",
        )
    with diag_col_3:
        st.write("")
        st.write("")
        if st.button(
            "Generar diagnostico" if not route_summary_snapshot["diagnostic_completed"] else "Regenerar diagnostico",
            key="learning_generate_diagnostic_btn",
            width="stretch",
        ):
            st.session_state.learning_diagnostic_payload = adaptive_learning.get_initial_diagnostic(
                learning_student_id,
                goal=diag_goal,
                target_level=diag_target,
                max_questions=4,
            )
            st.rerun()

    diagnostic_payload = st.session_state.get("learning_diagnostic_payload")
    if diagnostic_payload:
        with st.form("learning_diagnostic_form"):
            st.caption(
                f"Banco: {diagnostic_payload['question_bank_version']} | "
                f"Tiempo estimado: {diagnostic_payload['estimated_minutes']} min"
            )
            for question in diagnostic_payload["questions"]:
                st.markdown(f"**{question['prompt']}**")
                st.selectbox(
                    "Selecciona una respuesta",
                    options=[""] + list(question["options"]),
                    key=f"diag_answer_{question['id']}",
                )
            submitted_diag = st.form_submit_button("Evaluar diagnostico", use_container_width=True)

        if submitted_diag:
            selected_answers = []
            missing_answers = []
            for question in diagnostic_payload["questions"]:
                selected = st.session_state.get(f"diag_answer_{question['id']}", "")
                if not selected:
                    missing_answers.append(question["id"])
                selected_answers.append((question, selected))

            if missing_answers:
                st.warning("Responde todas las preguntas antes de evaluar el diagnostico.")
            else:
                results = []
                for question, selected in selected_answers:
                    result = adaptive_learning.evaluate_answer(
                        learning_student_id,
                        question["id"],
                        selected,
                    )
                    results.append(result)
                st.session_state.learning_last_feedback = results
                st.session_state.learning_diagnostic_payload = None
                st.session_state.learning_route = adaptive_learning.get_personalized_route(learning_student_id)
                st.session_state.learning_kpis = adaptive_learning.get_learning_kpis(learning_student_id)
                st.session_state.learning_cohort_report = adaptive_learning.get_cohort_report()
                st.rerun()

    if last_feedback:
        feedback_summary = summarize_feedback_rollup(last_feedback)
        st.divider()
        st.subheader("Feedback formativo")
        col_fb1, col_fb2, col_fb3 = st.columns(3)
        col_fb1.metric("Correctas", feedback_summary["correct_count"])
        col_fb2.metric("Por reforzar", feedback_summary["incorrect_count"])
        col_fb3.metric("Misconceptions", feedback_summary["misconception_count"])
        if feedback_summary["remediation_titles"]:
            st.caption("Refuerzo recomendado: " + ", ".join(feedback_summary["remediation_titles"]))
        for idx, result in enumerate(last_feedback, start=1):
            status_label = "Correcta" if result.get("correcto") else "Para reforzar"
            with st.expander(f"Resultado {idx}: {status_label}"):
                st.write(result.get("feedback", ""))
                feedback_steps = result.get("feedback_steps") or []
                if feedback_steps:
                    st.markdown("**Loop de feedback**")
                    for step_index, step in enumerate(feedback_steps, start=1):
                        st.markdown(f"{step_index}. {step}")
                st.caption("Pista: " + result.get("hint", ""))
                if result.get("misconceptions"):
                    st.caption("Misconceptions detectadas: " + ", ".join(result.get("misconceptions", [])))
                remediation = result.get("recommended_remediation", {}) or {}
                if remediation.get("title"):
                    st.caption("Micro-leccion sugerida: " + remediation["title"])

    st.divider()
    st.subheader("Ruta personalizada")
    next_node = route_snapshot.get("next_node") or {}
    if next_node:
        with st.container(border=True):
            st.markdown(f"#### {next_node.get('title', 'Siguiente nodo')}")
            st.write(next_node.get("summary", ""))
            st.caption(
                f"Modalidad sugerida: {next_node.get('recommended_modality', '-')} | "
                f"Tiempo estimado: {next_node.get('estimated_minutes', '-')} min | "
                f"Dificultad sugerida: {next_node.get('recommended_difficulty', 'medium')}"
            )
            st.caption(
                f"Motivo de ruteo: {next_node.get('route_reason', 'next_mastery_gap')} | "
                f"Dominio actual: {float(next_node.get('current_mastery', 0.0)) * 100:.1f}% / "
                f"Objetivo: {float(next_node.get('mastery_required', 0.0)) * 100:.1f}%"
            )
            if next_node.get("review_due"):
                st.info("Este nodo aparece por spaced repetition: corresponde repaso antes de abrir contenido nuevo.")
            if next_node.get("blocked_by"):
                st.caption("Bloqueado por prerequisitos: " + ", ".join(next_node.get("blocked_by", [])))
            st.caption("Simulador/lab: " + str(next_node.get("simulator", "Pendiente")))
            st.caption(
                f"Retencion: {float(next_node.get('retention_score', 0.0)) * 100:.1f}% | "
                f"Reviews: {int(next_node.get('review_count', 0) or 0)}"
            )

        with st.expander("Ver micro-leccion recomendada"):
            st.markdown(
                generate_micro_lesson(
                    next_node["id"],
                    engine=adaptive_learning,
                    persona=route_snapshot.get("persona", "beginner"),
                    mastery_threshold=float(route_snapshot.get("mastery_threshold", 0.85) or 0.85),
                ),
                unsafe_allow_html=False,
            )

        with st.expander("Ejercicios sugeridos"):
            for exercise in generate_exercises(
                next_node_theme(route_snapshot),
                kpi_summary_snapshot["recommended_difficulty"],
                2,
                persona=route_snapshot.get("persona", "beginner"),
                misconceptions=list((kpis_snapshot.get("misconceptions") or {}).keys()),
            ):
                st.markdown(f"**{exercise['prompt']}**")
                st.caption("Pista: " + exercise["hint"])
                st.caption("Solucion base: " + exercise["solution"])
                if exercise.get("remediation_focus"):
                    st.caption("Foco de remediacion: " + exercise["remediation_focus"])

        with st.form("learning_progress_form"):
            mastery_score = st.slider(
                "Nivel de dominio percibido para este nodo",
                min_value=0.0,
                max_value=1.0,
                value=max(float(next_node.get("current_mastery", 0.0) or 0.0), 0.75),
                step=0.05,
                key="learning_mastery_score",
            )
            mark_completed = st.checkbox(
                "Marcar este nodo como dominado",
                value=mastery_score >= float(route_snapshot.get("mastery_threshold", 0.85) or 0.85),
            )
            reflection = st.text_area(
                "Autoevaluacion breve",
                placeholder="Que parte te resulto mas clara o mas dificil?",
                key="learning_reflection",
            )
            submitted_progress = st.form_submit_button(
                "Registrar repaso" if next_node.get("review_due") else "Guardar progreso",
                use_container_width=True,
            )

        if submitted_progress:
            st.session_state.learning_last_progress = adaptive_learning.save_progress(
                learning_student_id,
                next_node["id"],
                mastery_score=mastery_score,
                completed=mark_completed,
                reflection=reflection,
            )
            st.session_state.learning_route = adaptive_learning.get_personalized_route(learning_student_id)
            st.session_state.learning_kpis = adaptive_learning.get_learning_kpis(learning_student_id)
            st.session_state.learning_cohort_report = adaptive_learning.get_cohort_report()
            st.rerun()
    else:
        st.success("No hay nodos pendientes en el mapa visible. Puedes regenerar diagnostico o seguir profundizando en chat.")

    if last_progress.get("saved"):
        st.success(
            "Progreso guardado en la ruta personalizada. "
            f"Mastery requerido: {float(last_progress.get('mastery_threshold', 0.85) or 0.85) * 100:.1f}%."
        )

    review_queue = route_snapshot.get("review_queue", []) or []
    if review_queue:
        st.divider()
        st.subheader("Repasos programados")
        st.dataframe(pd.DataFrame(review_queue), width="stretch", hide_index=True)

    st.divider()
    st.subheader("Milestones")
    for milestone in route_snapshot.get("milestones", []):
        label = "Desbloqueado" if milestone.get("unlocked") else "En progreso"
        st.markdown(f"**{milestone.get('label', '-')}:** {label}")
        st.progress(float(milestone.get("progress", 0.0) or 0.0))
        st.caption(
            f"{milestone.get('completed_count', 0)}/{milestone.get('required_count', 0)} nodos completos"
        )

    badges = (route_snapshot.get("gamification") or {}).get("badges", [])
    if badges:
        st.divider()
        st.subheader("Badges")
        for badge in badges:
            st.info(f"{badge.get('label', '')}: {badge.get('description', '')}")

    blocked_nodes = ((route_snapshot.get("knowledge_graph") or {}).get("blocked_nodes", [])) or []
    if blocked_nodes:
        st.divider()
        st.subheader("Knowledge Graph")
        for blocked in blocked_nodes:
            blocked_by = ", ".join(blocked.get("blocked_by", [])) or "Prerequisito pendiente"
            st.caption(f"{blocked.get('title', blocked.get('node_id', '-'))}: bloqueado por {blocked_by}")

with tab_analytics:
    st.markdown("### 🧠 Perfil de Comprensión Cuántica")
    analytics_kpis = st.session_state.get("learning_kpis", learning_kpis)
    analytics_kpi_summary = summarize_kpis(analytics_kpis)
    cohort_report_snapshot = st.session_state.get("learning_cohort_report", learning_cohort_report)
    cohort_summary_snapshot = summarize_cohort_report(cohort_report_snapshot)
    
    # Grid de métricas premium
    col_a, col_b, col_c = st.columns(3)
    
    with col_a:
        with st.container(border=True):
            st.markdown("<div style='text-align: center;'><div style='font-size: 0.8rem; opacity: 0.7;'>NIVEL DE ANDAMIAJE</div>", unsafe_allow_html=True)
            scaff = st.session_state.get("scaffolding", {"label": "Inicial", "modifier": "Punto de partida"})
            if isinstance(scaff, str):
                scaff = {"label": scaff.capitalize(), "modifier": ""}
            elif not isinstance(scaff, dict):
                scaff = {"label": "Inicial", "modifier": "Punto de partida"}
            st.markdown(f"<div style='font-size: 1.8rem; font-weight: bold; color: #d4af37;'>{scaff.get('label', 'Inicial')}</div>", unsafe_allow_html=True)
            st.caption(scaff.get("modifier", ""))
    
    with col_b:
        with st.container(border=True):
            st.markdown("<div style='text-align: center;'><div style='font-size: 0.8rem; opacity: 0.7;'>CONVERGENCIA RELACIONAL</div>", unsafe_allow_html=True)
            conv = st.session_state.get("relational_data", {"convergence": 0.0}).get("convergence", 0.0)
            st.markdown(f"<div style='font-size: 1.8rem; font-weight: bold; color: #d4af37;'>{conv*100:.1f}%</div>", unsafe_allow_html=True)
            st.progress(conv)

    with col_c:
        with st.container(border=True):
            st.markdown("<div style='text-align: center;'><div style='font-size: 0.8rem; opacity: 0.7;'>RIGOR CIENTÍFICO</div>", unsafe_allow_html=True)
            st.markdown("<div style='font-size: 1.8rem; font-weight: bold; color: #d4af37;'>MULTI-AUTHOR</div>", unsafe_allow_html=True)
            st.caption("Validado contra Galindo, Cohen, Sakurai")

    st.divider()
    st.subheader("📈 KPIs de Aprendizaje")
    col_kpi_1, col_kpi_2, col_kpi_3, col_kpi_4 = st.columns(4)
    col_kpi_1.metric(
        "Pretest",
        f"{analytics_kpi_summary['pretest_percent']:.1f}%"
        if analytics_kpi_summary["pretest_percent"] is not None else "Pendiente",
    )
    col_kpi_2.metric(
        "Posttest",
        f"{analytics_kpi_summary['posttest_percent']:.1f}%"
        if analytics_kpi_summary["posttest_percent"] is not None else "Pendiente",
    )
    col_kpi_3.metric(
        "Mejora",
        f"{analytics_kpi_summary['improvement_points']:+.1f} pts"
        if analytics_kpi_summary["improvement_points"] is not None else "Pendiente",
    )
    col_kpi_4.metric("Finalizacion", f"{analytics_kpi_summary['completion_percent']:.1f}%")

    col_kpi_5, col_kpi_6, col_kpi_7, col_kpi_8 = st.columns(4)
    col_kpi_5.metric("Progreso por nodo", f"{analytics_kpi_summary['average_node_progress_percent']:.1f}%")
    col_kpi_6.metric("Dominio global", f"{analytics_kpi_summary['overall_mastery_percent']:.1f}%")
    col_kpi_7.metric("Milestones", analytics_kpi_summary["milestones_text"])
    col_kpi_8.metric("Eventos desde chat", analytics_kpi_summary["chat_learning_events"])
    col_kpi_9, col_kpi_10, col_kpi_11, col_kpi_12 = st.columns(4)
    col_kpi_9.metric("Persona", analytics_kpi_summary["persona_label"])
    col_kpi_10.metric("Dificultad", analytics_kpi_summary["recommended_difficulty"])
    col_kpi_11.metric("Repasos vencidos", analytics_kpi_summary["due_review_count"])
    col_kpi_12.metric("Misconceptions", analytics_kpi_summary["misconception_count"])

    if analytics_kpis.get("node_progress"):
        progress_rows = pd.DataFrame(analytics_kpis["node_progress"])
        st.dataframe(progress_rows, width="stretch", hide_index=True)

    st.divider()
    st.subheader("👥 Cohorte y experimento")
    cohort_col_1, cohort_col_2, cohort_col_3, cohort_col_4 = st.columns(4)
    cohort_col_1.metric("Estudiantes", cohort_summary_snapshot["student_count"])
    cohort_col_2.metric("Diagnostico completo", f"{cohort_summary_snapshot['diagnostic_completed_percent']:.1f}%")
    cohort_col_3.metric("Prom. finalizacion", f"{cohort_summary_snapshot['average_completion_percent']:.1f}%")
    cohort_col_4.metric("Prom. dominio", f"{cohort_summary_snapshot['average_mastery_percent']:.1f}%")
    if cohort_summary_snapshot["average_improvement_points"] is not None:
        st.caption(f"Mejora promedio observada: {cohort_summary_snapshot['average_improvement_points']:+.1f} pts")
    st.caption(
        f"Experimento activo: {cohort_report_snapshot.get('experiment_name', 'gamification_v1')} | "
        f"Modulo con mayor traccion: {cohort_summary_snapshot['top_module_title']}"
    )

    variant_rows = cohort_report_snapshot.get("variants", [])
    if variant_rows:
        st.dataframe(pd.DataFrame(variant_rows), width="stretch", hide_index=True)

    st.subheader("🧩 Comparativa por módulo")
    module_rows = cohort_report_snapshot.get("module_comparison", [])
    if module_rows:
        module_df = pd.DataFrame(module_rows)
        st.dataframe(module_df, width="stretch", hide_index=True)

    if auth.get_role() in {"admin", "professor"}:
        st.divider()
        st.subheader("📤 Export de cohorte")
        if st.button("Exportar reporte de cohorte", key="learning_export_cohort_btn", width="stretch"):
            st.session_state.learning_last_export = adaptive_learning.export_cohort_report()
            st.session_state.learning_cohort_report = st.session_state.learning_last_export.get("report", cohort_report_snapshot)
            st.rerun()
        last_export = st.session_state.get("learning_last_export", {}) or {}
        if last_export.get("json_path"):
            st.success(
                "Export listo: "
                f"{last_export['json_path']} | {last_export['csv_path']}"
            )
            student_rows = (last_export.get("report", {}) or {}).get("students", [])
            if student_rows:
                st.dataframe(pd.DataFrame(student_rows), width="stretch", hide_index=True)

    st.divider()
    
    # Heatmap de Esfuerzo Cognitivo
    st.subheader("🔥 Mapa de Esfuerzo por Concepto")
    heatmap = analytics.get_content_heatmap()
    if heatmap:
        df_h = pd.DataFrame(heatmap)
        # Formato premium para el heatmap
        st.data_editor(
            df_h,
            column_config={
                "topic": "Concepto de Física",
                "struggle_index": st.column_config.ProgressColumn(
                    "Índice de Dificultad",
                    help="Mayor índice indica mayor necesidad de refuerzo socrático",
                    format="%.2f",
                    min_value=0,
                    max_value=1.0,
                ),
            },
            hide_index=True,
            width="stretch",
            disabled=True
        )
    else:
        st.info("Continúa la conversación para mapear tu progreso cognitivo.")

    # Radar de Malentendidos
    st.divider()
    col_d, col_e = st.columns(2)
    with col_d:
        st.subheader("🛠️ Anomalías Detectadas")
        clusters = analytics.get_misconception_clusters()
        if clusters["Error_Conceptual"] or clusters["Falla_Base"]:
            for err in (clusters["Error_Conceptual"] + clusters["Falla_Base"]):
                st.warning(f"**Anomalía:** {err}")
        else:
            st.success("No se han detectado brechas conceptuales críticas.")
    
    with col_e:
        st.subheader("✅ Terrenos Dominados")
        if clusters["Dominado"]:
            for dom in clusters["Dominado"]:
                st.info(f"**Sólido en:** {dom}")
        else:
            st.caption("Aún en fase de exploración inicial.")

with tab_admin_dashboard:
    _render_learning_intelligence_dashboard()
    st.divider()
    st.header("🔬 Resultados del Piloto & Learning Gain")
    import requests
    try:
        # Petición a nuestra propia API
        _res = requests.get(f"http://127.0.0.1:8000/api/pilot-results")
        if _res.status_code == 200:
            pilot_data = _res.json()
            col_z1, col_z2, col_z3, col_z4 = st.columns(4)
            col_z1.metric("Pretest Avg", f"{pilot_data.get('mean_pretest', 0.0):.2f}")
            col_z2.metric("Posttest Avg", f"{pilot_data.get('mean_posttest', 0.0):.2f}")
            col_z3.metric("Transfer Avg", f"{pilot_data.get('mean_transfer', 0.0):.2f}")
            col_z4.metric("Learning Gain Real", f"{pilot_data.get('mean_gain', 0.0):.2f}")
            
            st.metric("Correlación (Ganancia Real vs Interna)", f"{pilot_data.get('correlation_internal_external', 0.0):.2f}",
                help="Correlación lineal de Pearson. >0.6 sugiere altísima validez del algoritmo interno.")
            
            p_students = pilot_data.get("students", [])
            if p_students:
                import pandas as pd
                st.dataframe(pd.DataFrame(p_students), use_container_width=True)
            else:
                st.info("No hay datos de piloto procesados todavía.")
    except Exception as e:
        st.warning(f"No se pudo cargar datos de evaluación piloto: {e}")

with tab_evaluacion:
    st.markdown("### 📝 Evaluación Externa de Aprendizaje")
    st.caption("Esta sección mide tu comprensión conceptual real y retención. Para propósitos del Piloto.")
    
    test_type = st.selectbox("Selecciona la Evaluación a Responder", ["pretest", "posttest", "transfer"])
    
    # Preguntas en code hardcodeado (según sugerencias de piloto)
    eval_qs = {
        "pretest": [
            {"id": "pre_q1", "q": "¿Qué representa la función de onda (ψ) en mecánica cuántica?"},
            {"id": "pre_q2", "q": "Explica el principio de incertidumbre de Heisenberg."},
            {"id": "pre_q3", "q": "¿Qué es un operador en mecánica cuántica?"},
            {"id": "pre_q4", "q": "Si |ψ(x)|² es alto en una región, ¿qué significa físicamente?"},
            {"id": "pre_q5", "q": "Si reduces la incertidumbre en posición, ¿qué ocurre con la incertidumbre en el momento?"},
            {"id": "pre_q6", "q": "¿Por qué no podemos conocer la trayectoria exacta de un electrón como en la física clásica?"}
        ],
        "posttest": [
            {"id": "post_q1", "q": "¿Por qué la función de onda no describe directamente una posición definida?"},
            {"id": "post_q2", "q": "¿Qué implica físicamente que dos observables no conmutan?"},
            {"id": "post_q3", "q": "¿Qué significa medir un observable en mecánica cuántica?"},
            {"id": "post_q4", "q": "Si una función de onda está más “localizada”, ¿qué puedes decir de su momento?"},
            {"id": "post_q5", "q": "¿Qué indica que una función de onda esté normalizada?"},
            {"id": "post_q6", "q": "¿Por qué no podemos predecir exactamente dónde aparecerá una partícula, incluso con toda la información?"}
        ],
        "transfer": [
            {"id": "t_q1", "q": "Un electrón está confinado en una caja cuántica. ¿Qué ocurre con su energía si la caja se hace más pequeña? ¿Por qué?"},
            {"id": "t_q2", "q": "¿Por qué un electrón no cae al núcleo, a pesar de la atracción eléctrica?"},
            {"id": "t_q3", "q": "Si intentas medir repetidamente la posición de una partícula con alta precisión, ¿qué efecto tiene sobre su estado?"}
        ]
    }
    
    with st.form("pilot_evaluation_form"):
        st.write(f"Instrucciones: Responde a las preguntas del {test_type.upper()}")
        answers = {}
        for item in eval_qs[test_type]:
            answers[item["id"]] = st.text_area(item["q"], key=f"{test_type}_{item['id']}")
            
        submitted = st.form_submit_button("Enviar Evaluación", use_container_width=True)
        if submitted:
            import requests
            for q_id, ans in answers.items():
                if ans.strip():
                    try:
                        import os
                        requests.post("http://127.0.0.1:8000/api/external-evaluation", json={
                            "user_id": auth.get_user_email(),
                            "test_type": test_type,
                            "question_id": q_id,
                            "answer": ans
                        }, headers={"X-API-Key": os.getenv("API_KEY", "")})
                    except Exception as e:
                        pass
            st.success("Tus respuestas han sido evaluadas y registradas para el análisis pedagógico.")

def run_async_generator(async_gen, ctx):
    """Ejecuta generator async en entorno sync (Streamlit) de forma segura"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    async def consume():
        async for chunk in async_gen:
            if st.session_state.cancel_flag:
                ctx.mark_cancelled()
                break
            yield chunk
    async_gen_wrapped = consume()
    try:
        while True:
            chunk = loop.run_until_complete(async_gen_wrapped.__anext__())
            yield chunk
    except StopAsyncIteration:
        pass
    except Exception as e:
        yield f"\n\n[ERROR STREAM]: {str(e)}"
    finally:
        loop.close()

# --- Procesamiento de Input ---
prompt = None

# ── VOICE INPUT ────────────────────────────────────────────────────────────────
with st.expander("🎙️ Entrada de voz", expanded=False):
    audio_bytes_val = st.audio_input(
        "Graba tu pregunta y el tutor la transcribirá automáticamente",
        key="voice_recorder"
    )

if audio_bytes_val is not None and not st.session_state.get("_voice_processed"):
    st.session_state["_voice_processed"] = True
    import tempfile
    import google.generativeai as genai

    with st.spinner("🎙️ Transcribiendo audio..."):
        try:
            # Obtener la API key activa del orquestador
            _active_key = (
                tutor.current_api_key
                if hasattr(tutor, "current_api_key") and tutor.current_api_key
                else (tutor.api_keys[0] if hasattr(tutor, "api_keys") and tutor.api_keys else None)
            )
            if not _active_key:
                st.warning("⚠️ No hay API Key disponible para transcripción de voz.")
            else:
                genai.configure(api_key=_active_key)
                _transcription_client = genai.GenerativeModel("gemini-2.0-flash")

                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as _tmp_audio:
                    _tmp_audio.write(audio_bytes_val.getvalue())
                    _tmp_path = _tmp_audio.name

                try:
                    _audio_file = genai.upload_file(_tmp_path, mime_type="audio/wav")
                    _transcription_response = _transcription_client.generate_content(
                        ["Transcribe exactly what is said in this audio. Return only the transcribed text, no additional commentary.", _audio_file]
                    )
                    _transcribed_text = _transcription_response.text.strip()
                    if _transcribed_text:
                        prompt = _transcribed_text
                        st.success(f"🎙️ Transcripción: *{_transcribed_text}*")
                    else:
                        st.warning("⚠️ No se pudo transcribir audio. Intenta de nuevo.")
                finally:
                    import os as _os
                    if _os.path.exists(_tmp_path):
                        _os.remove(_tmp_path)
        except Exception as _ve:
                st.warning(f"⚠️ Error en transcripción de voz: `{str(_ve)[:200]}`")
elif audio_bytes_val is None:
    # Reset flag when widget is cleared so next recording works
    st.session_state.pop("_voice_processed", None)
# ── END VOICE INPUT ─────────────────────────────────────────────────────────────

chat_input_val = st.chat_input(
    "Ej: ¿Cómo se comporta la probabilidad en el centro de un pozo infinito para n=2?",
    key="main_chat_input",
    accept_file=True,
)

if st.session_state.pop("ignore_chat_input_once", False) and not st.session_state.get("vision_active_prompt"):
    chat_input_val = None

if chat_input_val:
    if isinstance(chat_input_val, dict):
        if chat_input_val.get("files"):
            uploaded_file = chat_input_val["files"][0]
            prompt_text = chat_input_val.get("text", "Por favor analiza esta derivación.")
            import tempfile
            import os
            with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(uploaded_file.name)[1]) as tmp_file:
                tmp_file.write(uploaded_file.getvalue())
                tmp_path = os.path.abspath(tmp_file.name)
            try:
                with st.spinner("Analizando derivación vision-sintáctica..."):
                    steps = vision_parser.parse_derivation_image(tmp_path)
                    vision_prompt = f"{prompt_text}\n\nHe subido una foto de mi derivación ({uploaded_file.name}). El modelo de visión detectó estos pasos:\n\n"
                    for step in steps:
                        is_err = step.get("error_flag", False)
                        flag = " ❌ [ERROR]" if is_err else " ✅ [OK]"
                        vision_prompt += f"- **Paso {step['step']}:** $${step['latex']}$${flag}\n"
                    vision_prompt += "\nAyúdame a entender mi lógica basándote en este análisis."
                    st.session_state.vision_active_prompt = vision_prompt
            finally:
                if os.path.exists(tmp_path): os.remove(tmp_path)
        else:
            prompt = chat_input_val.get("text", "")
    elif isinstance(chat_input_val, str):
        prompt = chat_input_val
    else:
        # Fallback for alternative Streamlit objects
        try:
            prompt = chat_input_val.text
        except AttributeError:
            prompt = str(chat_input_val)

if "vision_active_prompt" in st.session_state and st.session_state.vision_active_prompt:
    prompt = st.session_state.vision_active_prompt
    st.session_state.vision_active_prompt = None 

if prompt and isinstance(prompt, str) and prompt.strip():

    st.session_state.messages.append({"role": "user", "content": prompt})
    with tab_chat:
        with st.chat_message("user"):
            st.markdown(prompt)
        
        # Botón de Cancelación (UI)
        col_c1, col_c2 = st.columns([8, 2])
        with col_c2:
            cancel_btn = st.button("⛔ Cancelar Res.", key="btn_cancel_gen")
            if cancel_btn:
                st.session_state.cancel_flag = True

        with st.chat_message("assistant", avatar="✨"):
            response_placeholder = st.empty()
            full_response = ""
            image_pages_from_result = []

            ctx = QuantumRequestContext(
                user_id=auth.get_user_email() or "streamlit_user",
                session_id=st.session_state.session_id,
                user_input=prompt,
                conversation_history=st.session_state.messages,
                relational=session_data["relational"],
                analytics=session_data["analytics"],
                semantic_cache=session_data["cache"]
            )
            
            st.session_state.cancel_flag = False

            with st.spinner("Procesando respuesta (v6)..."):
                stream = st.session_state.orchestrator.handle_request(ctx)
                for chunk in run_async_generator(stream, ctx):
                    if chunk == "⚡_ROTATION_SIGNAL_⚡":
                        st.toast("⚡ Rotando nodo API — alta demanda.", icon="⚠️")
                        continue
                    full_response += chunk
                    
                    disp = full_response
                    if disp.count('$$') % 2 != 0: 
                        disp += "\n$$\n\n> *(generando...)*"
                    else:
                        disp += " ▌"
                    response_placeholder.markdown(disp)
                
                if ctx.cancelled:
                    full_response += "\n\n*(⛔ Respuesta cancelada por el usuario)*"
                
                response_placeholder.markdown(full_response)
                
                # Sincronización de Metadata Post-Generación
                meta = getattr(ctx, "metadata", {}) or {}
                if meta:
                    st.session_state.engine_status = meta.get("engine_status", "HYBRID_RELATIONAL")
                    st.session_state.relational_data = meta.get("relational_data", {})
                    st.session_state.scaffolding = meta.get("scaffolding", "default")
                    st.session_state.last_rate_limit_meta = meta.get("rate_limit", {}) or {}
                    st.session_state.last_backpressure_meta = meta.get("backpressure", {}) or {}
                    st.session_state.last_provider_retry_meta = meta.get("provider_retry", {}) or {}
                    image_pages_from_result = list(dict.fromkeys(meta.get("image_pages", [])))

                    if st.session_state.last_rate_limit_meta.get("limited"):
                        retry_after = float(st.session_state.last_rate_limit_meta.get("retry_after_seconds", 0.0) or 0.0)
                        st.toast(
                            f"Bucket temporal agotado. Reintento estimado en {_format_wait_hint(retry_after)}.",
                            icon="⚠️",
                        )
                    elif st.session_state.last_backpressure_meta.get("limited"):
                        retry_after = float(st.session_state.last_backpressure_meta.get("retry_after_seconds", 0.0) or 0.0)
                        st.toast(
                            f"Cola del proveedor saturada. Reintento estimado en {_format_wait_hint(retry_after)}.",
                            icon="⏳",
                        )

                if meta.get("context_retrieved") or (ctx.rag_data and ctx.rag_data.get("context")):
                    st.session_state.stats["rag_queries"] += 1
                if ctx.wolfram_result:
                    st.session_state.stats["wolfram_hits"] += 1
                if wolfram_metric_slot is not None:
                    _render_session_metric(wolfram_metric_slot, st.session_state.stats["wolfram_hits"], "W-CALLS")
                if rag_metric_slot is not None:
                    _render_session_metric(rag_metric_slot, st.session_state.stats["rag_queries"], "RAG-ANCHORS")

                response_outcome = _evaluate_response_outcome(ctx, full_response)
                st.session_state.last_response_quality = response_outcome["label"]
                st.session_state.last_response_notes = response_outcome["notes"]
                analytics.log_interaction(
                    ctx.topic or "General",
                    wolfram_invoked=bool(ctx.wolfram_result),
                    passed_socratic=response_outcome["passed_socratic"]
                )
                chat_learning_event = adaptive_learning.record_chat_learning_signal(
                    learning_student_id,
                    ctx.topic or "General",
                    passed_socratic=response_outcome["passed_socratic"],
                    response_quality=response_outcome["label"],
                    engine_status=st.session_state.get("engine_status", ""),
                    wolfram_used=bool(ctx.wolfram_result),
                    context_retrieved=bool(meta.get("context_retrieved")),
                    user_text=prompt,
                )
                if chat_learning_event.get("recorded"):
                    st.session_state.learning_route = chat_learning_event.get("route", adaptive_learning.get_personalized_route(learning_student_id))
                    st.session_state.learning_kpis = chat_learning_event.get("kpis", adaptive_learning.get_learning_kpis(learning_student_id))
                    st.session_state.learning_cohort_report = adaptive_learning.get_cohort_report()
                else:
                    st.session_state.learning_route = adaptive_learning.get_personalized_route(learning_student_id)
                    st.session_state.learning_kpis = adaptive_learning.get_learning_kpis(learning_student_id)
                    st.session_state.learning_cohort_report = adaptive_learning.get_cohort_report()

                if response_outcome["notes"]:
                    st.warning("Respuesta parcial detectada: " + ", ".join(response_outcome["notes"]))

            if image_pages_from_result:
                st.divider()
                st.subheader("📖 Referencias Bibliográficas")
                cols = st.columns(min(3, len(image_pages_from_result)))
                for i, page_num in enumerate(image_pages_from_result):
                    img_path = reference_viz.get_page_image(page_num)
                    
                    # Label formatting refined (v5.5)
                    raw_id = str(page_num)
                    if "cohen_page_" in raw_id:
                        page_label = raw_id.replace("cohen_page_", "Cohen Tannoudji p. ")
                    elif "sakurai_page_" in raw_id:
                        page_label = raw_id.replace("sakurai_page_", "Sakurai p. ")
                    elif "page_" in raw_id:
                        page_label = raw_id.replace("page_", "Galindo & Pascual p. ")
                    elif raw_id.isdigit():
                        page_label = f"Galindo & Pascual p. {raw_id}"
                    else:
                        page_label = raw_id
                    page_label = _format_reference_page_label(page_num)
                        
                    if img_path:
                        with cols[i % len(cols)]:
                            with st.container(border=True):
                                st.image(img_path, caption=f"Extracto: {page_label}", width="stretch")

    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response,
        "image_pages": image_pages_from_result
    })

# Cerrar wrapper de CSS
st.markdown("</div>", unsafe_allow_html=True)
