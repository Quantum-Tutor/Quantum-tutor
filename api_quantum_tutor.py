import os
import sys
import tempfile
import uuid
from contextlib import asynccontextmanager
from typing import List, Optional

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from external_evaluation import pilot_db, ExternalEvaluatorLLM
from external_evaluation import pilot_db, ExternalEvaluatorLLM
from quantum_tutor_runtime import API_TITLE, API_VERSION, DISPLAY_VERSION, SHORT_DESCRIPTION
from learning_analytics import LearningAnalytics
from adaptive_learning_engine import AdaptiveLearningEngine
from multimodal_vision_parser import MultimodalVisionParser
from api_security import APISecurityManager
from quantum_tutor_paths import CRASH_LOG_PATH, STUDENT_PROFILE_PATH, write_text_atomic

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
static_dir = os.path.join(BASE_DIR, "static_web")
tutor = None
vision_parser = None
analytics = None
adaptive_learning = None
security = APISecurityManager()

try:
    tutor = QuantumTutorOrchestrator(base_dir=BASE_DIR)
    vision_parser = MultimodalVisionParser()
    analytics = LearningAnalytics(STUDENT_PROFILE_PATH)
    adaptive_learning = AdaptiveLearningEngine()
except Exception as e:
    print(f"Error al inicializar el nucleo del tutor: {e}")


def _cors_settings():
    default_origins = [
        "http://localhost",
        "http://127.0.0.1",
        "http://localhost:8501",
        "http://127.0.0.1:8501",
    ]
    raw_origins = os.getenv(
        "QUANTUM_TUTOR_CORS_ORIGINS",
        os.getenv("CORS_ALLOWED_ORIGINS", ""),
    ).strip()

    if not raw_origins:
        return {
            "allow_origins": default_origins,
            "allow_credentials": True,
        }

    if raw_origins == "*":
        return {
            "allow_origins": ["*"],
            "allow_credentials": False,
        }

    allow_origins = []
    for origin in raw_origins.split(","):
        cleaned = origin.strip().rstrip("/")
        if cleaned and cleaned not in allow_origins:
            allow_origins.append(cleaned)

    return {
        "allow_origins": allow_origins or default_origins,
        "allow_credentials": True,
    }


def _configured_gemini_keys():
    raw_keys = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
    return [key.strip() for key in raw_keys.split(",") if key.strip()]


def _short_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 10:
        return key
    return f"{key[:6]}...{key[-3:]}"


def _startup_snapshot():
    configured_keys = _configured_gemini_keys()
    wolfram_ok = bool(os.getenv("WOLFRAM_APP_ID"))

    rag_ok = False
    gemini_runtime = "LOCAL_FALLBACK"
    gemini_ok = False
    active_key = ""
    key_health = {}
    gemini_next_retry_seconds = 0.0

    if tutor is not None:
        try:
            rag_ok = bool(tutor.rag and len(tutor.rag.vector_store) > 0)
        except Exception as e:
            print(f"[*] RAG Engine: [ERROR] {e}")

        key_health = dict(getattr(tutor, "key_health", {}) or {})
        active_key = getattr(tutor, "current_api_key", "") or getattr(tutor, "api_key", "")
        gemini_ok = bool(getattr(tutor, "llm_enabled", False) and getattr(tutor, "client", None))
        gemini_next_retry_seconds = max(float(getattr(tutor, "_provider_retry_seconds", lambda: 0.0)() or 0.0), 0.0)
        if gemini_ok:
            gemini_runtime = "HYBRID_RELATIONAL"

    prompt_ok = os.path.exists(os.path.join(BASE_DIR, "system_prompt.md"))
    status = "READY" if gemini_ok and rag_ok else "DEGRADED"

    return {
        "status": status,
        "gemini_ok": gemini_ok,
        "gemini_configured": bool(configured_keys),
        "gemini_node_count": len(configured_keys),
        "gemini_active_key": _short_key(active_key),
        "gemini_runtime": gemini_runtime,
        "gemini_next_retry_seconds": round(gemini_next_retry_seconds, 3),
        "gemini_key_health": key_health,
        "wolfram_ok": wolfram_ok,
        "rag_ok": rag_ok,
        "prompt_ok": prompt_ok,
    }


@asynccontextmanager
async def lifespan(app: FastAPI):
    if (
        tutor is not None
        and hasattr(tutor, "_startup_key_check")
        and not getattr(tutor, "_key_check_done", True)
    ):
        try:
            await tutor._startup_key_check()
        except Exception as e:
            print(f"[*] Gemini key check: [ERROR] {e}")

    snapshot = _startup_snapshot()
    healthy_nodes = sum(
        1 for state in snapshot["gemini_key_health"].values()
        if state == "OK"
    )
    gemini_status = "[OK]" if snapshot["gemini_ok"] else "[DEGRADED]"
    active_key = f" | activo {snapshot['gemini_active_key']}" if snapshot["gemini_active_key"] else ""
    health_summary = (
        f" | salud {healthy_nodes}/{snapshot['gemini_node_count']} OK"
        if snapshot["gemini_key_health"]
        else ""
    )
    retry_summary = (
        f" | reintento ~{snapshot['gemini_next_retry_seconds']:.1f}s"
        if snapshot.get("gemini_next_retry_seconds", 0.0) > 0
        else ""
    )

    print("\n" + "=" * 50)
    print(f" {API_TITLE} {DISPLAY_VERSION} - BOOT SEQUENCE")
    print("=" * 50)
    print(f"[*] STATUS: {snapshot['status']}")
    if snapshot["gemini_configured"]:
        print(
            f"[*] GEMINI_API_KEYS: {gemini_status} {snapshot['gemini_node_count']} nodos configurados"
            f"{active_key}{health_summary}{retry_summary} | runtime {snapshot['gemini_runtime']}"
        )
    else:
        print("[*] GEMINI_API_KEYS: [MISSING] (Safety Mode forced)")
    print(f"[*] WOLFRAM_APP_ID: {'[OK]' if snapshot['wolfram_ok'] else '[MISSING] (Emulator fallback)'}")
    print(f"[*] RAG Engine: {'[OK]' if snapshot['rag_ok'] else '[ERROR] Vector store empty'}")
    print(f"[*] System Prompt: {'[OK]' if snapshot['prompt_ok'] else '[ERROR] Using internal default'}")
    print("=" * 50 + "\n")
    yield


app = FastAPI(
    title=API_TITLE,
    version=API_VERSION,
    description=SHORT_DESCRIPTION,
    lifespan=lifespan,
)

cors_settings = _cors_settings()
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_settings["allow_origins"],
    allow_credentials=cors_settings["allow_credentials"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class ChatMessage(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    message: str
    history: List[ChatMessage] = []
    user_id: Optional[str] = None


class DiagnosticAnswerRequest(BaseModel):
    student_id: Optional[str] = None
    question_id: str
    answer: str
    self_assessment: Optional[float] = None


class SaveLearningProgressRequest(BaseModel):
    student_id: Optional[str] = None
    node_id: str
    question_id: Optional[str] = None
    correct: Optional[bool] = None
    mastery_score: Optional[float] = None
    completed: bool = False
    time_spent_seconds: Optional[float] = None
    reflection: str = ""


class AssessmentScoreRequest(BaseModel):
    student_id: Optional[str] = None
    assessment_type: str
    score: float
    label: str = ""
    notes: str = ""


class CohortExportRequest(BaseModel):
    experiment_name: str = "gamification_v1"

class ExternalEvaluationRequest(BaseModel):
    user_id: Optional[str] = None
    test_type: str
    question_id: str
    answer: str


def _json_error(
    *,
    status_code: int,
    error_code: str,
    message: str,
    request_id: str,
    retry_after_seconds: float | None = None,
):
    headers = {"X-Request-ID": request_id}
    payload = {
        "error_code": error_code,
        "message": message,
        "request_id": request_id,
    }
    if retry_after_seconds is not None:
        normalized = max(float(retry_after_seconds), 1.0)
        headers["Retry-After"] = str(max(int(normalized + 0.999), 1))
        payload["retry_after_seconds"] = normalized
    return JSONResponse(status_code=status_code, headers=headers, content=payload)


def _request_id_from_request(request: Request) -> str:
    forwarded = (request.headers.get("x-request-id", "") or "").strip()
    if forwarded:
        cleaned = "".join(ch for ch in forwarded if ch.isalnum() or ch in {"-", "_", "."})
        if cleaned:
            return cleaned[:64]
    return str(uuid.uuid4())[:8]


def _temporary_block_response(request_id: str, retry_after_seconds: float):
    return _json_error(
        status_code=403,
        error_code="TEMPORARILY_BLOCKED",
        message="Este origen fue bloqueado temporalmente por patron de abuso o saturacion reiterada. Intenta nuevamente mas tarde.",
        request_id=request_id,
        retry_after_seconds=retry_after_seconds,
    )


def _resolved_learning_student_id(http_request: Request, explicit_student_id: str | None = None) -> str:
    # SECURITY: nunca confiar en el student_id enviado por el cliente.
    # La identidad se deriva siempre desde el middleware de seguridad.
    identity = security.resolve_identity(http_request, None)
    resolved = identity.authenticated_user or identity.provider_user_id
    if resolved:
        return resolved
        
    # IDOR Fix: Only allow explicit student_id if the caller is an authenticated admin/professor
    try:
        _require_professor_or_admin(http_request)
        return explicit_student_id or "anonymous"
    except Exception:
        return "anonymous"


def _require_professor_or_admin(http_request: Request) -> None:
    """Guard de autorización seguro para endpoints administrativos.
    No confía en cabeceras de proxy transitivas. Requiere validación de Token Nativa.
    """
    if os.getenv("QT_AUTHZ_ADMIN_ENDPOINTS_DISABLED", "").strip().lower() in {"1", "true", "yes"}:
        return

    client_key = (http_request.headers.get("X-API-Key", "")).strip()
    valid_key = os.getenv("API_KEY", "").strip()

    # Si NO hay valid_key configurada, en producción es inseguro.
    if not valid_key or client_key != valid_key:
        raise HTTPException(
            status_code=403,
            detail="Acceso Administrativo Denegado. API_KEY inválida o faltante.",
        )


def get_detailed_topic(text):
    text_lower = text.lower()
    import re

    mapping = {
        r"pozo.*infinito": "Pozo Infinito",
        r"pozo.*finito": "Pozo Finito",
        r"tunel|t[úu]nel": "Efecto Túnel",
        r"espin|esp[íi]n": "Espín",
        r"oscilador.*armonico|oscilador.*arm[óo]nico": "Oscilador Armónico",
        r"conmutador": "Conmutadores",
    }
    for pattern, topic in mapping.items():
        if re.search(pattern, text_lower):
            return topic
    return "General"


@app.get("/health")
@app.get("/healthz")
async def health_endpoint(http_request: Request):
    req_id = _request_id_from_request(http_request)
    snapshot = _startup_snapshot()
    payload = {
        "status": "ok",
        "request_id": req_id,
        "runtime_status": snapshot["status"],
        "gemini_runtime": snapshot["gemini_runtime"],
        "gemini_next_retry_seconds": snapshot["gemini_next_retry_seconds"],
        "rag_ok": snapshot["rag_ok"],
    }
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.get("/api/diagnostico-inicial")
@app.get("/diagnostico_inicial")
async def diagnostic_initial_endpoint(
    http_request: Request,
    student_id: Optional[str] = None,
    goal: str = "fundamentos",
    target_level: str = "beginner",
    max_questions: int = 5,
):
    req_id = _request_id_from_request(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    resolved_student_id = _resolved_learning_student_id(http_request, student_id)
    payload = adaptive_learning.get_initial_diagnostic(
        resolved_student_id,
        goal=goal,
        target_level=target_level,
        max_questions=max(1, min(max_questions, 8)),
    )
    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.post("/api/evaluar-respuesta")
@app.post("/evaluar_respuesta")
async def evaluate_answer_endpoint(http_request: Request, request: DiagnosticAnswerRequest):
    req_id = _request_id_from_request(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    resolved_student_id = _resolved_learning_student_id(http_request, request.student_id)
    try:
        payload = adaptive_learning.evaluate_answer(
            resolved_student_id,
            request.question_id,
            request.answer,
            self_assessment=request.self_assessment,
        )
    except KeyError:
        return _json_error(
            status_code=404,
            error_code="QUESTION_NOT_FOUND",
            message="La pregunta solicitada no existe en el banco diagnostico actual.",
            request_id=req_id,
        )

    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.get("/api/ruta-personalizada")
@app.get("/ruta_personalizada")
async def personalized_route_endpoint(http_request: Request, student_id: Optional[str] = None):
    req_id = _request_id_from_request(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    resolved_student_id = _resolved_learning_student_id(http_request, student_id)
    payload = adaptive_learning.get_personalized_route(resolved_student_id)
    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.post("/api/guardar-progreso")
@app.post("/guardar_progreso")
async def save_learning_progress_endpoint(http_request: Request, request: SaveLearningProgressRequest):
    req_id = _request_id_from_request(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    resolved_student_id = _resolved_learning_student_id(http_request, request.student_id)
    try:
        payload = adaptive_learning.save_progress(
            resolved_student_id,
            request.node_id,
            question_id=request.question_id,
            correct=request.correct,
            mastery_score=request.mastery_score,
            completed=request.completed,
            time_spent_seconds=request.time_spent_seconds,
            reflection=request.reflection,
        )
    except KeyError:
        return _json_error(
            status_code=404,
            error_code="NODE_NOT_FOUND",
            message="El nodo curricular solicitado no existe en el mapa actual.",
            request_id=req_id,
        )

    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.get("/api/curriculum")
async def curriculum_overview_endpoint(http_request: Request):
    req_id = _request_id_from_request(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    payload = adaptive_learning.curriculum_overview()
    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.get("/api/learning-kpis")
async def learning_kpis_endpoint(http_request: Request, student_id: Optional[str] = None):
    req_id = _request_id_from_request(http_request)
    _require_professor_or_admin(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    resolved_student_id = _resolved_learning_student_id(http_request, student_id)
    payload = adaptive_learning.get_learning_kpis(resolved_student_id)
    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.get("/api/learning-review-queue")
async def learning_review_queue_endpoint(http_request: Request, student_id: Optional[str] = None):
    req_id = _request_id_from_request(http_request)
    _require_professor_or_admin(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    resolved_student_id = _resolved_learning_student_id(http_request, student_id)
    payload = {
        "student_id": resolved_student_id,
        "review_queue": adaptive_learning.get_review_queue(resolved_student_id),
    }
    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.post("/api/guardar-evaluacion")
async def save_assessment_score_endpoint(http_request: Request, request: AssessmentScoreRequest):
    req_id = _request_id_from_request(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    resolved_student_id = _resolved_learning_student_id(http_request, request.student_id)
    try:
        payload = adaptive_learning.record_assessment_score(
            resolved_student_id,
            assessment_type=request.assessment_type,
            score=request.score,
            label=request.label,
            notes=request.notes,
        )
    except KeyError:
        return _json_error(
            status_code=400,
            error_code="INVALID_ASSESSMENT_TYPE",
            message="El tipo de evaluacion debe ser pretest o posttest.",
            request_id=req_id,
        )

    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.get("/api/learning-cohort-report")
async def learning_cohort_report_endpoint(http_request: Request, experiment_name: str = "gamification_v1"):
    req_id = _request_id_from_request(http_request)
    _require_professor_or_admin(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    payload = adaptive_learning.get_cohort_report(experiment_name=experiment_name)
    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.get("/api/learning-insights")
async def learning_insights_endpoint(
    http_request: Request,
    experiment_name: str = "gamification_v1",
    apply_optimization: bool = False,
):
    req_id = _request_id_from_request(http_request)
    _require_professor_or_admin(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    payload = adaptive_learning.get_learning_insights(
        experiment_name=experiment_name,
        apply_optimization=bool(apply_optimization),
    )
    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})


@app.post("/api/learning-cohort-export")
async def learning_cohort_export_endpoint(http_request: Request, request: CohortExportRequest):
    req_id = _request_id_from_request(http_request)
    _require_professor_or_admin(http_request)
    if adaptive_learning is None:
        return _json_error(
            status_code=500,
            error_code="LEARNING_NOT_INITIALIZED",
            message="El motor de aprendizaje adaptativo no pudo inicializarse.",
            request_id=req_id,
        )

    payload = adaptive_learning.export_cohort_report(experiment_name=request.experiment_name)
    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})

@app.post("/api/external-evaluation")
async def external_evaluation_endpoint(http_request: Request, request: ExternalEvaluationRequest):
    req_id = _request_id_from_request(http_request)
    resolved_student_id = _resolved_learning_student_id(http_request, request.user_id)
    
    if request.test_type not in ["pretest", "posttest", "transfer"]:
        return _json_error(
            status_code=400,
            error_code="INVALID_TEST_TYPE",
            message="El test_type debe ser pretest, posttest o transfer.",
            request_id=req_id
        )

    # Evaluación cruzada vía API
    try:
        from quantum_tutor_orchestrator import QuantumTutorOrchestrator
        from external_evaluation import ExternalEvaluatorLLM, pilot_db
        # Re-crear un micro orchestrator o usar init (solo modo demostracion/piloto)
        # Se asume que el modulo 'orchestrator' subyacente está global o pasamos mock
        class MockOrchestrator:
            async def generate_response_async(self, prompt, context, require_json=False):
                return '{"score": 0.8, "justificacion": "Buena definicion basica."}'
        evaluator = ExternalEvaluatorLLM(MockOrchestrator())
        eval_result = await evaluator.evaluate_answer(request.question_id, request.answer)
    except Exception as e:
        eval_result = {"score": 0.0, "justificacion": "Error evaluando."}
        
    pilot_db.save_evaluation(
        student_id=resolved_student_id,
        test_type=request.test_type,
        question_id=request.question_id,
        score=eval_result["score"],
        answer=request.answer,
        justification=eval_result["justificacion"]
    )
    
    payload = {
        "status": "success",
        "student_id": resolved_student_id,
        "score": eval_result["score"],
        "justification": eval_result["justificacion"],
        "request_id": req_id
    }
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})

@app.get("/api/pilot-results")
async def pilot_results_endpoint(http_request: Request):
    req_id = _request_id_from_request(http_request)
    _require_professor_or_admin(http_request)
    
    internal_kpis = {}
    if adaptive_learning:
        report = adaptive_learning.get_cohort_report()
        for stud in report.get("students", []):
            internal_kpis[stud["student_id"]] = stud.get("improvement_points", 0.0)
            
    payload = pilot_db.get_pilot_results(internal_kpis=internal_kpis)
    payload["request_id"] = req_id
    return JSONResponse(content=payload, headers={"X-Request-ID": req_id})





@app.post("/api/chat")
async def chat_endpoint(http_request: Request, request: ChatRequest):
    req_id = _request_id_from_request(http_request)
    print(f"[{req_id}] Chat hit with message: '{request.message[:50]}...'")

    if not request.message or not request.message.strip():
        return _json_error(
            status_code=400,
            error_code="EMPTY_QUERY",
            message="La consulta no puede estar vacia.",
            request_id=req_id,
        )

    if len(request.message) > 4000:
        return _json_error(
            status_code=400,
            error_code="QUERY_TOO_LONG",
            message="La consulta es demasiado larga (max 4000 caracteres).",
            request_id=req_id,
        )

    if tutor is None:
        return _json_error(
            status_code=500,
            error_code="CORE_NOT_INITIALIZED",
            message="El nucleo del tutor no pudo inicializarse.",
            request_id=req_id,
        )

    try:
        identity = security.resolve_identity(http_request, request.user_id)
        block_decision = security.check_temporary_block(identity, req_id)
        if block_decision.blocked:
            return _temporary_block_response(req_id, block_decision.retry_after_seconds)

        chat_guard_ok, guard_status, guard_code, guard_message = security.validate_chat_request(http_request, request.history)
        if not chat_guard_ok:
            security.record_abuse(identity, guard_code, request_id=req_id)
            return _json_error(
                status_code=guard_status,
                error_code=guard_code,
                message=guard_message,
                request_id=req_id,
            )

        edge_decision = security.enforce_edge_rate_limit("chat", identity)
        if not edge_decision.allowed:
            security.record_abuse(identity, "EDGE_RATE_LIMITED", request_id=req_id)
            return _json_error(
                status_code=429,
                error_code="EDGE_RATE_LIMITED",
                message="La API recibio demasiadas solicitudes desde este origen. Intenta nuevamente en unos segundos.",
                request_id=req_id,
                retry_after_seconds=edge_decision.retry_after_seconds,
            )

        conv_hist = [{"role": msg.role, "content": msg.content} for msg in request.history]
        response_data_meta, stream = await tutor.generate_response_stream_async(
            request.message,
            conversation_history=conv_hist,
            user_id=identity.provider_user_id,
            rate_limit_mode="hard",
        )

        full_text = ""
        async for chunk in stream:
            full_text += chunk

        response_data = response_data_meta
        rate_limit_meta = response_data.get("rate_limit", {}) or {}
        if rate_limit_meta.get("limited"):
            return _json_error(
                status_code=429,
                error_code="RATE_LIMITED",
                message="Has alcanzado el limite temporal de uso del proveedor. Intenta nuevamente mas tarde.",
                request_id=req_id,
                retry_after_seconds=float(rate_limit_meta.get("retry_after_seconds", 1.0) or 1.0),
            )
        backpressure_meta = response_data.get("backpressure", {}) or {}
        if backpressure_meta.get("limited"):
            return _json_error(
                status_code=429,
                error_code="BACKPRESSURE",
                message="La cola del proveedor esta saturada temporalmente. Intenta nuevamente en unos segundos.",
                request_id=req_id,
                retry_after_seconds=float(backpressure_meta.get("retry_after_seconds", 1.0) or 1.0),
            )
        response_data["response"] = full_text

        topic = get_detailed_topic(request.message)
        prompt_lower = request.message.lower()
        passed_soc = not ("dime" in prompt_lower or "respuesta" in prompt_lower or len(prompt_lower) < 15)
        misconception_clusters = {
            "Error_Calculo": [],
            "Error_Conceptual": [],
            "Falla_Base": [],
            "Dominado": [],
        }
        if analytics is not None:
            analytics.log_interaction(
                topic,
                wolfram_invoked=response_data.get("wolfram_used", True),
                passed_socratic=passed_soc,
            )
            misconception_clusters = analytics.get_misconception_clusters()

        response_data["analytics"] = {
            "topic": topic,
            "misconception_clusters": misconception_clusters,
        }
        response_data["request_id"] = req_id

        print(f"[{req_id}] SUCCESS: Enviando respuesta con llaves: {list(response_data.keys())}")
        return JSONResponse(content=response_data, headers={"X-Request-ID": req_id})

    except Exception as e:
        import traceback

        write_text_atomic(CRASH_LOG_PATH, traceback.format_exc())
        print(f"[{req_id}] ERROR: {e}")
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": req_id},
            content={
                "error_code": "INTERNAL_CORE_ERROR",
                "message": "Encontre un problema tecnico en mis circuitos cuanticos.",
                "details": str(e),
                "request_id": req_id,
            },
        )


@app.post("/api/vision")
async def vision_endpoint(http_request: Request, file: UploadFile = File(...)):
    req_id = _request_id_from_request(http_request)
    if vision_parser is None:
        return _json_error(
            status_code=500,
            error_code="VISION_NOT_INITIALIZED",
            message="El parser visual no pudo inicializarse.",
            request_id=req_id,
        )

    tmp_path = ""
    try:
        identity = security.resolve_identity(http_request)
        block_decision = security.check_temporary_block(identity, req_id)
        if block_decision.blocked:
            return _temporary_block_response(req_id, block_decision.retry_after_seconds)

        upload_guard_ok, guard_status, guard_code, guard_message = security.validate_vision_upload(http_request, file)
        if not upload_guard_ok:
            security.record_abuse(identity, guard_code, request_id=req_id)
            return _json_error(
                status_code=guard_status,
                error_code=guard_code,
                message=guard_message,
                request_id=req_id,
            )

        edge_decision = security.enforce_edge_rate_limit("vision", identity)
        if not edge_decision.allowed:
            security.record_abuse(identity, "EDGE_RATE_LIMITED", request_id=req_id)
            return _json_error(
                status_code=429,
                error_code="EDGE_RATE_LIMITED",
                message="La API recibio demasiadas cargas de imagen desde este origen. Intenta nuevamente en unos segundos.",
                request_id=req_id,
                retry_after_seconds=edge_decision.retry_after_seconds,
            )

        upload_ok, upload_bytes, upload_status, upload_code, upload_message = await security.read_limited_upload(file)
        if not upload_ok:
            security.record_abuse(identity, upload_code, request_id=req_id)
            return _json_error(
                status_code=upload_status,
                error_code=upload_code,
                message=upload_message,
                request_id=req_id,
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename or "upload.bin")[1]) as tmp_file:
            tmp_file.write(upload_bytes)
            tmp_path = tmp_file.name

        steps = vision_parser.parse_derivation_image(tmp_path)

        vision_prompt = f"He subido mi derivacion ({file.filename}). El modelo de vision detecto esto:\n\n"
        for step in steps:
            is_err = step.get("error_flag", False)
            flag = " [ERROR DETECTADO]" if is_err else " [OK]"
            vision_prompt += f"- **Paso {step['step']}:** $${step['latex']}$$ ({step.get('description', '')}){flag}\n"
            if is_err:
                vision_prompt += f"  > *Razonamiento Vision:* {step.get('error_reason')}\n"

        vision_prompt += "\nPor favor, actua como mi tutor y ayudame a entender donde fallo mi logica sin la respuesta directa."

        return JSONResponse(
            content={"vision_prompt": vision_prompt, "steps": steps},
            headers={"X-Request-ID": req_id},
        )
    except Exception as e:
        return JSONResponse(
            status_code=500,
            headers={"X-Request-ID": req_id},
            content={"error_code": "VISION_INTERNAL_ERROR", "message": str(e), "request_id": req_id},
        )
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass


app.mount("/", StaticFiles(directory=static_dir, html=True), name="static")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("api_quantum_tutor:app", host="0.0.0.0", port=8000, reload=True)
