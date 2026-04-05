"""
QuantumTutor — Orquestador stateless y seguro para concurrencia
===============================================================
Arquitectura: núcleo stateless que aísla el estado por request mediante QuantumRequestContext.
Optimizaciones: Asyncio para RAG/Wolfram concurrente, snapshot de cliente y cancelación cooperativa.
"""

import os
import sys
import json
import re
import logging
import asyncio
import time
from contextlib import asynccontextmanager
from typing import AsyncGenerator, Dict, Any, Optional, List

import google.genai as genai
from dotenv import load_dotenv
from pathlib import Path

load_dotenv()

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wolfram_emulator import WolframAlphaEmulator
from deterministic_responder import DeterministicResponder
from rag_engine import RAGConnector
from quantum_request_context import QuantumRequestContext
from request_optimization import (
    BackpressureDecision,
    FileTokenBucketRateLimiter,
    LLMResponseCache,
    ModelRoute,
    RequestBackpressureError,
    RequestModelRouter,
    RequestRateLimitedError,
)
from security_audit import SecurityEventLogger
from security_controls import CircuitBreakerDecision, FileCircuitBreaker
from quantum_tutor_runtime import DEFAULT_TEXT_MODEL, RUNTIME_VERSION
from quantum_tutor_paths import RUNTIME_LOG_PATH, ensure_output_dirs

# ── Configuración de logging ─────────────
ensure_output_dirs()
log_path = str(RUNTIME_LOG_PATH)
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger("QuantumTutor.Orchestrator")

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'
))
logger.addHandler(console_handler)

TEMPORARY_KEY_STATES = {"RATE_LIMIT", "TIMEOUT", "UNAVAILABLE"}


class QuantumTutorOrchestrator:
    """
    Orquestador stateless y seguro para concurrencia.
    """

    def __init__(self, config_path='quantum_tutor_config.json', base_dir=None, scheduler=None):
        try:
            if base_dir:
                self.base_dir = Path(base_dir)
            else:
                self.base_dir = Path(__file__).resolve().parent
            
            self.base_dir_str = str(self.base_dir)
            
            if os.path.isabs(config_path):
                self.config_path = Path(config_path)
            else:
                self.config_path = self.base_dir / config_path
            
            self.config_path_str = str(self.config_path)
            self.config: dict = {}
            self.load_config(self.config_path_str)
        except Exception as e:
            logger.error(f"FALLBACK fatal en __init__: {e}")
            self.base_dir = Path(".")
            self.config_path = Path(config_path)
            self.config = {"temperature": 0.2, "top_k": 5, "version": RUNTIME_VERSION, "model": DEFAULT_TEXT_MODEL}

        self.wolfram = WolframAlphaEmulator(app_id=os.getenv("WOLFRAM_APP_ID", ""))
        self.deterministic_responder = DeterministicResponder()
        self._rag = None  # Carga diferida
        self.scheduler = scheduler
        self.system_prompt = self.load_system_prompt()
        self.version = RUNTIME_VERSION

        # --- Integración Gemini del runtime stateless (rotación de claves y resiliencia) ---
        raw_keys = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
        self.api_keys = [k.strip() for k in raw_keys.split(",") if k.strip()]
        self.key_index = 0
        self.key_cooldowns = {key: 0.0 for key in self.api_keys}
        self.key_health: dict = {key: "UNKNOWN" for key in self.api_keys}
        self._key_check_done = False
        self._next_key_check_at = 0.0
        self.llm_enabled = False
        self._rotation_lock = asyncio.Lock()
        self._startup_lock = asyncio.Lock()
        self.api_key = ""
        self.client = None
        self.model_name = str(self.config.get("model", DEFAULT_TEXT_MODEL))
        self.rate_limiter = FileTokenBucketRateLimiter()
        self.response_cache = LLMResponseCache()
        self.model_router = RequestModelRouter(default_model=self.model_name)
        self.provider_concurrency_limit = max(int(os.getenv("QT_PROVIDER_MAX_CONCURRENCY", "3")), 1)
        self.provider_queue_timeout_seconds = max(float(os.getenv("QT_PROVIDER_QUEUE_TIMEOUT_SECONDS", "1.5")), 0.1)
        self.provider_name = os.getenv("QT_PROVIDER_BREAKER_NAME", "gemini_text")
        self.provider_circuit_breaker = FileCircuitBreaker()
        self.security_audit = SecurityEventLogger()
        self._provider_semaphore = asyncio.Semaphore(self.provider_concurrency_limit)
        self._provider_waiters = 0

        if self.api_keys:
            try:
                self.api_key = self.api_keys[self.key_index]
                self.client = genai.Client(api_key=self.api_key)
                self.llm_enabled = True
                logger.info(f"LLM Engine (google-genai) {self.version} habilitado con {len(self.api_keys)} nodos.")
            except Exception as e:
                logger.error(f"Error inicializando Gemini SDK: {e}")

    def load_config(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                full_config = json.load(f)

            self.config = {
                "temperature": full_config.get("llm_config", {}).get("temperature", 0.2),
                "model": full_config.get("llm_config", {}).get("model", DEFAULT_TEXT_MODEL),
                "version": RUNTIME_VERSION,
            }
        except FileNotFoundError:
            self.config = {"temperature": 0.2, "version": RUNTIME_VERSION, "model": DEFAULT_TEXT_MODEL}

    def load_system_prompt(self) -> str:
        prompt_path = self.base_dir / 'system_prompt.md'
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return "Eres un tutor socrático de física cuántica altamente riguroso."

    @property
    def rag(self):
        if self._rag is None:
            self._rag = RAGConnector(base_dir=self.base_dir)
        return self._rag

    async def _close_test_client(self, client) -> None:
        if not client:
            return
        try:
            aio_client = getattr(client, "aio", None)
            close_method = getattr(aio_client, "aclose", None)
            if callable(close_method):
                maybe_coro = close_method()
                if asyncio.iscoroutine(maybe_coro):
                    await maybe_coro
        except Exception:
            pass

    def _extract_retry_delay_seconds(self, error: Exception, default_seconds: float = 80.0) -> float:
        error_text = str(error or "")
        retry_match = re.search(r"retryDelay['\"]?\s*:\s*['\"](\d+)s['\"]", error_text, re.IGNORECASE)
        if retry_match:
            return max(float(retry_match.group(1)), 1.0)

        human_match = re.search(r"retry in\s+([0-9]+(?:\.[0-9]+)?)s", error_text, re.IGNORECASE)
        if human_match:
            return max(float(human_match.group(1)), 1.0)

        return default_seconds

    def _classify_provider_error(self, error: Exception) -> tuple[str, float | None]:
        error_text = str(error or "")
        upper_text = error_text.upper()
        lower_text = error_text.lower()

        if isinstance(error, asyncio.TimeoutError) or "timed out" in lower_text or "timeout" in lower_text:
            return "TIMEOUT", 30.0
        if "429" in upper_text or "RESOURCE_EXHAUSTED" in upper_text:
            return "RATE_LIMIT", self._extract_retry_delay_seconds(error)
        if "503" in upper_text or "UNAVAILABLE" in upper_text or "500" in upper_text or "502" in upper_text:
            return "UNAVAILABLE", 20.0
        if (
            "401" in upper_text
            or "403" in upper_text
            or "API_KEY_INVALID" in upper_text
            or "INVALID_API_KEY" in upper_text
            or "PERMISSION_DENIED" in upper_text
            or "forbidden" in lower_text
            or "permission" in lower_text
        ):
            return "INVALID", None
        return "ERROR", None

    def _set_key_cooldown(self, key: str, seconds: float | None) -> None:
        if not key or not seconds or seconds <= 0:
            return
        self.key_cooldowns[key] = max(self.key_cooldowns.get(key, 0.0), time.time() + seconds)

    def _mark_key_failure(self, key: str, status: str, retry_after: float | None = None) -> None:
        if not key:
            return
        self.key_health[key] = status
        self._set_key_cooldown(key, retry_after)

    def _degrade_to_local_fallback(self, reason: str) -> None:
        now = time.time()
        temporary_keys = [
            key for key in self.api_keys
            if self.key_health.get(key) in TEMPORARY_KEY_STATES and self.key_cooldowns.get(key, 0.0) > now
        ]

        if temporary_keys:
            next_retry = min(self.key_cooldowns[key] for key in temporary_keys)
            self._next_key_check_at = next_retry
            retry_in = max(next_retry - now, 0.0)
            logger.warning(
                f"[LLM] {reason} Entrando en LOCAL_FALLBACK temporal; "
                f"reintento automatico en ~{retry_in:.1f}s."
            )
        else:
            self._next_key_check_at = 0.0
            logger.warning(f"[LLM] {reason} Entrando en LOCAL_FALLBACK sin reintento programado.")

        self.llm_enabled = False
        self.client = None
        self.api_key = ""

    async def _recover_after_provider_failure(
        self,
        snapshot: Dict[str, Any],
        status: str,
        retry_after: float | None = None,
        context: str = "runtime",
    ) -> bool:
        failed_key = snapshot.get("api_key", "")
        self._mark_key_failure(failed_key, status, retry_after)

        if status not in TEMPORARY_KEY_STATES and status != "INVALID":
            return False

        try:
            await self.rotate_client()
            self.llm_enabled = True
            self._next_key_check_at = 0.0
            logger.info(
                f"[LLM] Recuperacion tras {context}: nodo {failed_key[:8] if failed_key else 'N/A'} "
                f"marcado como {status} y rotacion aplicada."
            )
            return True
        except Exception as rot_err:
            logger.warning(f"[LLM] Sin nodos disponibles tras {context} ({status}): {rot_err}")
            self._degrade_to_local_fallback(f"{context}: todos los nodos quedaron no disponibles.")
            return False

    # =========================================================
    # VERIFICACIÓN DE SALUD DE CLAVES (ARRANQUE)
    # =========================================================

    async def _startup_key_check(self, force: bool = False):
        if ((self._key_check_done and not force) or not self.api_keys):
            return
        if not force and self._next_key_check_at and time.time() < self._next_key_check_at:
            return
            
        async with self._startup_lock:
            # Doble verificación dentro del lock
            if self._key_check_done and not force:
                return
            if not force and self._next_key_check_at and time.time() < self._next_key_check_at:
                return
                
            logger.info(f"[KEY-CHECK] Verificando {len(self.api_keys)} nodos API...")
            for i, key in enumerate(self.api_keys):
                short_key = f"{key[:8]}...{key[-4:]}"
                test_client = None
                try:
                    test_client = genai.Client(api_key=key)
                    start = time.perf_counter()
                    async with self._provider_semaphore:
                        response = await asyncio.wait_for(
                            test_client.aio.models.generate_content(
                                model=self.model_name,
                                contents="Hi",
                                config={"max_output_tokens": 1}
                            ),
                            timeout=10.0
                        )
                    latency = time.perf_counter() - start
                    self.key_health[key] = "OK"
                    self.key_cooldowns[key] = 0.0
                    logger.info(f"[KEY-CHECK] Nodo {i} ({short_key}) OK en {latency:.2f}s.")
                except Exception as e:
                    status, retry_after = self._classify_provider_error(e)
                    self._mark_key_failure(key, status, retry_after)
                    if status == "RATE_LIMIT":
                        logger.warning(f"[KEY-CHECK] Nodo {i} ({short_key}) en RATE_LIMIT. Retry aprox en {float(retry_after or 0):.1f}s.")
                    elif status in TEMPORARY_KEY_STATES:
                        logger.warning(f"[KEY-CHECK] Nodo {i} ({short_key}) temporalmente no disponible ({status}).")
                    elif status == "INVALID":
                        logger.error(f"[KEY-CHECK] Nodo {i} ({short_key}) invalido o sin permisos.")
                    else:
                        logger.error(f"[KEY-CHECK] Nodo {i} ({short_key}) fallo con estado {status}: {e}")
                finally:
                    await self._close_test_client(test_client)
            self._key_check_done = True
            healthy_indexes = [
                idx for idx, key in enumerate(self.api_keys)
                if self.key_health.get(key) == "OK"
            ]

            if not healthy_indexes:
                temporary_indexes = [
                    idx for idx, key in enumerate(self.api_keys)
                    if self.key_health.get(key) in TEMPORARY_KEY_STATES
                ]
                if temporary_indexes:
                    next_retry = min(
                        self.key_cooldowns.get(self.api_keys[idx], time.time() + 30.0)
                        for idx in temporary_indexes
                    )
                    self._next_key_check_at = next_retry
                    retry_in = max(next_retry - time.time(), 0.0)
                    logger.warning(
                        f"[KEY-CHECK] Ningun nodo listo ahora. Estados transitorios detectados; "
                        f"reintento automatico en ~{retry_in:.1f}s."
                    )
                else:
                    self._next_key_check_at = 0.0
                    logger.warning("[KEY-CHECK] Ningun nodo API quedo saludable. Degradando a LOCAL_FALLBACK.")
                self.llm_enabled = False
                self.client = None
                self.api_key = ""
                return

            self._next_key_check_at = 0.0
            self.llm_enabled = True
            if self.key_health.get(self.api_key) != "OK":
                healthy_idx = healthy_indexes[0]
                self.key_index = healthy_idx
                self.api_key = self.api_keys[healthy_idx]
                self.client = genai.Client(api_key=self.api_key)
                logger.info(f"[KEY-CHECK] Nodo activo cambiado a {healthy_idx} ({self.api_key[:8]}...).")

    # =========================================================
    # SNAPSHOT DE CLIENTE (CRÍTICO)
    # =========================================================

    async def get_client_snapshot(self) -> Dict[str, Any]:
        async with self._rotation_lock:
            return {
                "client": self.client,
                "api_key": self.api_key,
                "model": self.model_name
            }

    @property
    def current_api_key(self) -> str:
        return self.api_key

    async def rotate_client(self):
        async with self._rotation_lock:
            for i in range(1, len(self.api_keys) + 1):
                idx = (self.key_index + i) % len(self.api_keys)
                key = self.api_keys[idx]

                if self.key_health.get(key) == "INVALID":
                    continue  # BUGFIX: skip this key, don't stop rotation entirely
                if time.time() > self.key_cooldowns[key]:
                    self.key_index = idx
                    self.api_key = key
                    self.client = genai.Client(api_key=key)
                    logger.info(f"[ROTATION] Rotando a nodo {idx} ({key[:8]}...)")
                    return
            raise Exception("RESOURCE_EXHAUSTED_ALL_NODES")

    def register_rate_limit(self, snapshot: Dict[str, Any], cooldown_seconds: float = 80.0):
        """Registra un rate limit (cooldown) de 80s de forma segura usando el snapshot que falló."""
        failed_key = snapshot["api_key"]
        if failed_key:
            self._mark_key_failure(failed_key, "RATE_LIMIT", cooldown_seconds)

    # =========================================================
    # ENRUTAMIENTO (PURO, SIN EFECTOS)
    # =========================================================

    def detect_intent(self, text: str) -> str:
        t = text.lower().strip()
        if len(t.split()) <= 6 and any(w in t for w in ["hola", "saludos", "buenos días", "hello"]):
            return "GREETING"
        if any(w in t for w in ["imagen", "foto", "dibujo", "grafica", "referencia"]):
            return "VISUAL"
        return "GENERAL"

    def needs_wolfram(self, text: str) -> bool:
        pattern = r"(∫|\\int|d/dx|∑|\\sum|sqrt|\\sqrt|[\d\w\(\)]+\s*[\+\-\*/\^]\s*[\d\w\(\)]+)"
        keywords = ["integral", "normalización", "derivar", "conmutador", "integrate", "commutator", "calcular"]
        has_math_structure = bool(re.search(pattern, text))
        has_keyword = any(k in text.lower().split() for k in keywords)
        return has_math_structure or has_keyword

    def detect_topic(self, text: str) -> str:
        t = text.lower()
        if "pozo" in t: return "Pozo Infinito"
        elif "oscilador" in t: return "Oscilador Armónico"
        return "General"

    def _prior_history_turns(self, ctx: QuantumRequestContext) -> int:
        history = list(ctx.history or [])
        if (
            history
            and history[-1].get("role") == "user"
            and history[-1].get("content", "").strip() == ctx.user_input.strip()
        ):
            history = history[:-1]
        return len(history)

    def _select_model_route(self, ctx: QuantumRequestContext) -> ModelRoute:
        route = self.model_router.route(
            query=ctx.user_input,
            intent=ctx.intent or "GENERAL",
            prior_history_turns=self._prior_history_turns(ctx),
        )
        ctx.model_route = route.as_metadata()
        ctx.metadata["model_route"] = dict(ctx.model_route)
        return route

    def _try_deterministic_response(self, ctx: QuantumRequestContext) -> Optional[str]:
        match = self.deterministic_responder.match(
            query=ctx.user_input,
            topic=ctx.topic or "General",
            intent=ctx.intent or "GENERAL",
            history_turns=self._prior_history_turns(ctx),
        )
        if not match:
            return None

        ctx.metadata["deterministic"] = {
            "hit": True,
            "kind": match.kind,
            **(match.metadata or {}),
        }
        return match.response

    def _lookup_response_cache(self, ctx: QuantumRequestContext, route: ModelRoute) -> Optional[dict]:
        cache_meta = ctx.metadata.setdefault("cache", {"eligible": route.cacheable, "hit": False})
        if not route.cacheable:
            return None
        lookup = self.response_cache.lookup(ctx.user_input, namespace=route.cache_namespace)
        if not lookup:
            return None
        cache_meta.update(
            {
                "eligible": True,
                "hit": True,
                "match_type": lookup.get("match_type"),
                "similarity": lookup.get("similarity"),
            }
        )
        return lookup

    def _should_store_response_cache(self, ctx: QuantumRequestContext, route: ModelRoute, response_text: str) -> bool:
        if not route.cacheable or not response_text.strip() or ctx.cancelled:
            return False

        normalized = response_text.lower()
        blocked_markers = (
            "modo local de contingencia",
            "error en proveedor de ia",
            "respuesta cancelada",
            "[error sistem",
            "_rotation_signal_",
        )
        if any(marker in normalized for marker in blocked_markers):
            return False
        return True

    def _apply_rate_limit(self, ctx: QuantumRequestContext):
        decision = self.rate_limiter.consume(ctx.user_id or "anonymous")
        ctx.metadata["rate_limit"] = decision.as_metadata()
        return decision

    def _build_rate_limited_fallback(self, ctx: QuantumRequestContext, decision) -> str:
        retry_after = max(decision.retry_after_seconds, 0.0)
        notice = (
            "Guard de consumo activo: alcance el limite temporal de requests al proveedor. "
            f"El bucket se recupera en ~{retry_after:.1f}s, asi que sigo en modo local por ahora."
        )
        return f"{notice}\n\n{self._build_local_fallback(ctx)}"

    def _provider_retry_seconds(self) -> float:
        now = time.time()
        breaker_retry = self.provider_circuit_breaker.status(self.provider_name).retry_after_seconds
        if self._next_key_check_at and self._next_key_check_at > now:
            return max(self._next_key_check_at - now, breaker_retry, 0.0)

        future_cooldowns = [
            cooldown for cooldown in self.key_cooldowns.values()
            if cooldown > now
        ]
        if future_cooldowns:
            return max(min(future_cooldowns) - now, breaker_retry, 0.0)
        return max(breaker_retry, 0.0)

    def _active_cooldown_nodes(self) -> int:
        now = time.time()
        return sum(1 for cooldown in self.key_cooldowns.values() if cooldown > now)

    def _build_backpressure_fallback(self, ctx: QuantumRequestContext, decision: BackpressureDecision) -> str:
        retry_after = max(decision.retry_after_seconds, 0.0)
        notice = (
            "Backpressure activo: la cola del proveedor esta saturada en este momento. "
            f"Estimacion de nuevo intento en ~{retry_after:.1f}s mientras respondo en modo local."
        )
        return f"{notice}\n\n{self._build_local_fallback(ctx)}"

    def _apply_provider_circuit_breaker(self, ctx: QuantumRequestContext) -> CircuitBreakerDecision:
        decision = self.provider_circuit_breaker.allow_request(self.provider_name)
        ctx.metadata["circuit_breaker"] = decision.as_metadata()
        if decision.blocked:
            self.security_audit.log_event(
                event_type="provider_resilience",
                action="circuit_breaker_blocked_request",
                severity="WARNING",
                fields={
                    "provider": self.provider_name,
                    "state": decision.state,
                    "retry_after_seconds": decision.retry_after_seconds,
                    "failure_count": decision.failure_count,
                    "session_id": getattr(ctx, "session_id", ""),
                },
            )
        return decision

    def _record_provider_failure(self, category: str) -> CircuitBreakerDecision:
        decision = self.provider_circuit_breaker.record_failure(self.provider_name, category)
        self.security_audit.log_event(
            event_type="provider_resilience",
            action="circuit_breaker_failure_recorded",
            severity="WARNING",
            fields={
                "provider": self.provider_name,
                "category": category,
                "state": decision.state,
                "blocked": decision.blocked,
                "retry_after_seconds": decision.retry_after_seconds,
                "failure_count": decision.failure_count,
            },
        )
        return decision

    def _record_provider_success(self) -> CircuitBreakerDecision:
        decision = self.provider_circuit_breaker.record_success(self.provider_name)
        self.security_audit.log_event(
            event_type="provider_resilience",
            action="circuit_breaker_recovered",
            severity="INFO",
            fields={
                "provider": self.provider_name,
                "state": decision.state,
                "failure_count": decision.failure_count,
            },
        )
        return decision

    def _build_circuit_breaker_fallback(self, ctx: QuantumRequestContext, decision: CircuitBreakerDecision) -> str:
        retry_after = max(decision.retry_after_seconds, 0.0)
        notice = (
            "Circuit breaker activo: el proveedor externo se pauso temporalmente tras fallos repetidos. "
            f"Nuevo intento estimado en ~{retry_after:.1f}s mientras respondo en modo local."
        )
        return f"{notice}\n\n{self._build_local_fallback(ctx)}"

    @asynccontextmanager
    async def _provider_slot(
        self,
        ctx: Optional[QuantumRequestContext] = None,
        operation: str = "provider",
        timeout_override: Optional[float] = None,
    ):
        timeout_seconds = timeout_override
        if timeout_seconds is None and ctx is not None:
            timeout_seconds = self.provider_queue_timeout_seconds

        wait_started = time.perf_counter()
        acquired = False
        self._provider_waiters += 1

        try:
            acquire_coro = self._provider_semaphore.acquire()
            if timeout_seconds is not None:
                try:
                    await asyncio.wait_for(acquire_coro, timeout=timeout_seconds)
                except asyncio.TimeoutError as exc:
                    queue_depth = max(self._provider_waiters - self.provider_concurrency_limit + 1, 1)
                    retry_after = max(
                        1.0,
                        min(timeout_seconds * max(queue_depth / self.provider_concurrency_limit, 1.0), 5.0),
                    )
                    decision = BackpressureDecision(
                        limited=True,
                        retry_after_seconds=retry_after,
                        queue_timeout_seconds=timeout_seconds,
                        queue_depth=queue_depth,
                        concurrency_limit=self.provider_concurrency_limit,
                        operation=operation,
                        wait_time_seconds=time.perf_counter() - wait_started,
                    )
                    if ctx is not None:
                        ctx.metadata["backpressure"] = decision.as_metadata()
                    raise RequestBackpressureError(
                        decision,
                        f"Backpressure while waiting for {operation}.",
                    ) from exc
            else:
                await acquire_coro

            acquired = True
            wait_time = time.perf_counter() - wait_started
            if ctx is not None:
                ctx.metadata["backpressure"] = BackpressureDecision(
                    limited=False,
                    retry_after_seconds=0.0,
                    queue_timeout_seconds=timeout_seconds or 0.0,
                    queue_depth=max(self._provider_waiters - 1, 0),
                    concurrency_limit=self.provider_concurrency_limit,
                    operation=operation,
                    wait_time_seconds=wait_time,
                ).as_metadata()
            yield
        finally:
            self._provider_waiters = max(self._provider_waiters - 1, 0)
            if acquired:
                self._provider_semaphore.release()

    # =========================================================
    # INTERNAL REASONING (CoT)
    # =========================================================

    async def _reason_about_query(self, ctx: QuantumRequestContext, snapshot: Dict[str, Any], route: Optional[ModelRoute] = None) -> dict:
        if not self.llm_enabled or ctx.intent == "GREETING":
            return {}

        reasoning_prompt = f"""You are a quantum physics pedagogy expert.
Analyze the following student query and return a valid JSON object with your pedagogical reasoning.

STUDENT QUERY: {ctx.user_input}
DETECTED INTENT: {ctx.intent}
RAG CONTEXT AVAILABLE: {"yes" if ctx.rag_data and ctx.rag_data.get("context") else "no"}
WOLFRAM TOOL NEEDED: {"yes" if ctx.needs_wolfram else "no"}

Return ONLY a JSON object (no markdown) with:
- "pedagogical_strategy": (string)
- "key_concepts": (list)
- "tone": (string)
- "wolfram_override": (bool)
- "warning": (string)
"""
        client = snapshot["client"]
        model = route.reasoning_model if route else snapshot["model"]
        max_output_tokens = route.reasoning_max_tokens if route else 250
        try:
            async with self._provider_slot(ctx, operation="reasoning"):
                response = await asyncio.wait_for(
                    client.aio.models.generate_content(
                        model=model,
                        contents=reasoning_prompt,
                        config={"max_output_tokens": max_output_tokens, "temperature": 0.1}
                    ),
                    timeout=8.0
                )
            raw_text = getattr(response, 'text', '') or ''
            clean = re.sub(r'^```(?:json)?\s*', '', raw_text.strip(), flags=re.IGNORECASE)
            clean = re.sub(r'\s*```$', '', clean)
            return json.loads(clean)
        except RequestBackpressureError as e:
            ctx.metadata["backpressure"] = e.decision.as_metadata()
            logger.warning(f"[REASONING] Backpressure en razonamiento: {e}")
            return {}
        except Exception as e:
            status, retry_after = self._classify_provider_error(e)
            if status in TEMPORARY_KEY_STATES or status == "INVALID":
                if status in TEMPORARY_KEY_STATES:
                    ctx.metadata["circuit_breaker"] = self._record_provider_failure(status).as_metadata()
                await self._recover_after_provider_failure(
                    snapshot,
                    status,
                    retry_after,
                    context="reasoning",
                )
            logger.warning(f"[REASONING] Error en CoT ({status}): {e}")
            return {}

    # =========================================================
    # CORE ENTRYPOINT
    # =========================================================

    class _FallbackPlan:
        def __init__(self, run_rag, run_wolfram):
            self.run_rag = run_rag
            self.run_wolfram = run_wolfram
            self.wolfram_mode = "late"

    def _fallback_plan(self, ctx: QuantumRequestContext):
        return self._FallbackPlan(True, self.needs_wolfram(ctx.user_input))

    def _update_metadata(self, ctx: QuantumRequestContext):
        latency = ctx.metadata.setdefault("latency", {})
        latency["total"] = ctx.latency()
        latency.setdefault("total_pre_stream", ctx.latency())

        deterministic_meta = ctx.metadata.get("deterministic", {}) or {}
        cache_meta = ctx.metadata.get("cache", {}) or {}
        rate_limit_meta = ctx.metadata.get("rate_limit", {}) or {}
        backpressure_meta = ctx.metadata.get("backpressure", {}) or {}
        circuit_breaker_meta = self.provider_circuit_breaker.status(self.provider_name).as_metadata()
        ctx.metadata["circuit_breaker"] = circuit_breaker_meta
        provider_retry_seconds = self._provider_retry_seconds()
        ctx.metadata["provider_retry"] = {
            "scheduled": provider_retry_seconds > 0,
            "retry_after_seconds": round(provider_retry_seconds, 3),
            "active_cooldown_nodes": self._active_cooldown_nodes(),
            "circuit_breaker_active": circuit_breaker_meta.get("active", False),
            "circuit_breaker_state": circuit_breaker_meta.get("state", "closed"),
        }
        if deterministic_meta.get("hit"):
            engine_status = deterministic_meta.get("engine_status", "DETERMINISTIC_LOCAL")
        elif cache_meta.get("hit"):
            engine_status = "RESPONSE_CACHE"
        elif rate_limit_meta.get("limited"):
            engine_status = "RATE_LIMITED_LOCAL"
        elif backpressure_meta.get("limited"):
            engine_status = "BACKPRESSURE_LOCAL"
        elif circuit_breaker_meta.get("blocked"):
            engine_status = "CIRCUIT_BREAKER_LOCAL"
        else:
            engine_status = "HYBRID_RELATIONAL" if self.llm_enabled and self.client else "LOCAL_FALLBACK"

        ctx.metadata.update({
            "topic": ctx.topic,
            "context_retrieved": bool(ctx.rag_data and ctx.rag_data.get("context")),
            "image_pages": ctx.rag_data.get("image_pages", []) if ctx.rag_data else [],
            "wolfram_used": ctx.wolfram_result is not None,
            "engine_status": engine_status,
            "relational_data": ctx.relational.get_affinity_data() if ctx.relational else {},
            "scaffolding": ctx.analytics.get_scaffolding_level(ctx.topic) if ctx.analytics else "default",
        })

    async def _resolve_wolfram_task(
        self,
        ctx: QuantumRequestContext,
        timeout: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        if not ctx.wolfram_task or ctx.wolfram_emitted:
            return None

        if timeout is None:
            if not ctx.wolfram_task.done():
                return None
            try:
                result = ctx.wolfram_task.result()
            except Exception:
                ctx.wolfram_emitted = True
                return None
        else:
            try:
                result = await asyncio.wait_for(ctx.wolfram_task, timeout=timeout)
            except Exception:
                ctx.wolfram_emitted = True
                return None

        ctx.wolfram_emitted = True
        if result and result.get("status") == "success":
            ctx.wolfram_result = result
            return result
        return None

    def _yield_wolfram_result_chunks(
        self,
        result: Dict[str, Any],
        heading: str,
    ) -> List[str]:
        chunks = ["\n\n---\n", f"{heading}\n"]
        if result.get("result_latex"):
            chunks.append(f"$$ {result['result_latex']} $$\n")
        elif result.get("result_numeric"):
            chunks.append(f"Valor: `{result['result_numeric']}`\n")
        return chunks

    def _build_targeted_fallback_guidance(self, ctx: QuantumRequestContext) -> List[str]:
        query_l = ctx.user_input.lower()
        parts: List[str] = []

        if ctx.topic == "Pozo Infinito" and "centro" in query_l and ("n=2" in query_l or "n 2" in query_l):
            parts.append(
                "Respuesta directa de contingencia: en el pozo infinito unidimensional "
                "la autofunción es "
                "$$ \\psi_n(x) = \\sqrt{\\frac{2}{L}}\\sin\\left(\\frac{n\\pi x}{L}\\right) $$. "
                "En el centro del pozo, $x=L/2$, para $n=2$ se obtiene "
                "$$ \\psi_2(L/2)=\\sqrt{\\frac{2}{L}}\\sin(\\pi)=0 $$. "
                "Como la probabilidad es $|\\psi|^2$, allí también vale cero."
            )
            parts.append(
                "Intuición física: el estado $n=2$ tiene un nodo en el centro. "
                "No significa que la partícula no exista, sino que en ese estado estacionario "
                "la interferencia de la onda hace imposible detectarla exactamente en ese punto."
            )

        if ctx.wolfram_result and "integral" in query_l:
            numeric = ctx.wolfram_result.get("result_numeric")
            if numeric == 1.0:
                parts.append(
                    "Interpretación: el valor 1 indica que el área total bajo $e^{-x}$ entre 0 e infinito "
                    "es finita y está completamente normalizada. Es la misma idea que aparece cuando una "
                    "densidad exponencial ya está bien ajustada."
                )

        return parts

    def _build_local_fallback(self, ctx: QuantumRequestContext) -> str:
        if ctx.intent == "GREETING":
            return "Hola. Estoy disponible para trabajar mecánica cuántica contigo. Si quieres, planteamos el problema paso a paso."

        parts: List[str] = [
            f"Estoy operando en modo local de contingencia, así que te respondo con el contexto recuperado sobre **{ctx.topic or 'mecánica cuántica'}**."
        ]

        if ctx.wolfram_result:
            latex = ctx.wolfram_result.get("result_latex")
            numeric = ctx.wolfram_result.get("result_numeric")
            if latex:
                parts.append("Resultado simbólico verificado:")
                parts.append(f"$$ {latex} $$")
            elif numeric is not None:
                parts.append(f"Resultado simbólico verificado: `{numeric}`")

        parts.extend(self._build_targeted_fallback_guidance(ctx))

        context = (ctx.rag_data or {}).get("context", "").strip()
        if context:
            trimmed = context[:1400].strip()
            if len(context) > len(trimmed):
                trimmed += "\n...[Contexto truncado]..."
            parts.append("Base bibliográfica recuperada:")
            parts.append(trimmed)
        else:
            parts.append("No recuperé un fragmento bibliográfico suficientemente fuerte, así que conviene reformular la consulta con el concepto, operador o sistema físico específico.")

        if ctx.intent == "VISUAL" and ctx.metadata.get("image_pages"):
            parts.append("También encontré referencias visuales asociadas a esta consulta.")

        parts.append("Para seguir con rigor: ¿quieres que ataquemos primero la intuición física, la derivación formal o el cálculo?")
        return "\n\n".join(parts)

    async def generate_response_stream_async(
        self,
        user_input: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_id: str = "legacy_user",
        session_id: Optional[str] = None,
        rate_limit_mode: str = "soft",
        relational=None,
        analytics=None,
        semantic_cache=None,
    ):
        ctx = QuantumRequestContext(
            user_id=user_id,
            session_id=session_id or f"legacy_{int(time.time() * 1000)}",
            user_input=user_input,
            conversation_history=conversation_history or [],
            rate_limit_mode=rate_limit_mode,
            relational=relational,
            analytics=analytics,
            semantic_cache=semantic_cache,
        )

        async def wrapped_stream():
            try:
                async for chunk in self.handle_request(ctx):
                    yield chunk
            finally:
                self._update_metadata(ctx)

        return ctx.metadata, wrapped_stream()

    async def generate_response_async(
        self,
        user_input: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_id: str = "legacy_user",
        session_id: Optional[str] = None,
        rate_limit_mode: str = "soft",
        relational=None,
        analytics=None,
        semantic_cache=None,
    ) -> Dict[str, Any]:
        metadata, stream = await self.generate_response_stream_async(
            user_input=user_input,
            conversation_history=conversation_history,
            user_id=user_id,
            session_id=session_id,
            rate_limit_mode=rate_limit_mode,
            relational=relational,
            analytics=analytics,
            semantic_cache=semantic_cache,
        )

        response_parts: List[str] = []
        async for chunk in stream:
            response_parts.append(chunk)

        metadata["response"] = "".join(response_parts)
        return metadata

    async def _safe_execute_pipeline(self, ctx: QuantumRequestContext) -> AsyncGenerator[str, None]:
        """Wrapper con timeout global para proteger contra I/O bloqueado en generadores asíncronos."""
        try:
            # Python 3.11+ asyncio.timeout support
            if hasattr(asyncio, 'timeout'):
                async with asyncio.timeout(15.0):
                    async for chunk in self._execute_pipeline(ctx):
                        yield chunk
            else:
                # Fallback
                async for chunk in self._execute_pipeline(ctx):
                    yield chunk
                    
        except (asyncio.TimeoutError, TimeoutError):
            logger.error(f"Pipeline timeout | session={ctx.session_id}")
            ctx.cancelled = True
            yield "\n\n*[ERROR] Tiempo de espera de la solicitud agotado (Timeout).* "

    async def handle_request(
        self,
        ctx: QuantumRequestContext
    ) -> AsyncGenerator[str, None]:
        """
        Entrada principal v7.0 — Stateless, Resiliente y Observable.
        """
        should_recheck_keys = (
            not self._key_check_done
            or (
                self.api_keys
                and not self.llm_enabled
                and self._next_key_check_at
                and time.time() >= self._next_key_check_at
            )
        )
        if should_recheck_keys:
            await self._startup_key_check(force=self._key_check_done)

        # --- Base Routing ---
        ctx.intent = self.detect_intent(ctx.user_input)
        ctx.topic = self.detect_topic(ctx.user_input)
        
        # Ground Truth Heurístico
        heuristic_wl = self.needs_wolfram(ctx.user_input)
        
        # Defensa de Diccionarios y Metadata
        scheduler_meta = ctx.metadata.setdefault("scheduler", {})
        scores = scheduler_meta.setdefault("scores", {})
        features = scheduler_meta.setdefault("features", {})

        if ctx.intent == "GREETING":
            plan = self._FallbackPlan(run_rag=False, run_wolfram=False)
            scheduler_meta["selected"] = []
            scheduler_meta["scores"] = scores
            scheduler_meta["features"] = features
            scheduler_wl = False
            decision_source = "greeting_short_circuit"
            selected = []
        elif getattr(self, "scheduler", None):
            plan = self.scheduler.plan(ctx)
            scheduler_wl = plan.run_wolfram
            decision_source = "scheduler"
            selected = scheduler_meta.setdefault(
                "selected",
                ["wolfram" if plan.run_wolfram else "", "rag" if getattr(plan, "run_rag", True) else ""],
            )
            selected = [s for s in selected if s]
        else:
            plan = self._fallback_plan(ctx)
            scheduler_wl = plan.run_wolfram
            decision_source = "fallback"
            selected = ["wolfram" if plan.run_wolfram else "", "rag" if getattr(plan, "run_rag", True) else ""]
            selected = [s for s in selected if s]
        
        # Enriquecimiento Semántico
        heuristic_agreement = (heuristic_wl == scheduler_wl)
        wolfram_score = scores.get("wolfram", 0.0)
        rag_score = scores.get("rag", 0.0)
        confidence_delta = abs(wolfram_score - rag_score)
        
        # Logging Condicional No-Bloqueante
        if logger.isEnabledFor(logging.INFO):
            metrics = {
                "event": "SCHED_METRICS",
                "query": ctx.user_input,
                "selected": selected,
                "scores": scores,
                "features": features,
                "latency": ctx.latency(),
                "session_id": ctx.session_id,
                "decision_source": decision_source,
                "heuristic_agreement": heuristic_agreement,
                "confidence_delta": confidence_delta,
                "executed_wolfram": scheduler_wl
            }
            logger.info("SCHED_METRICS %s", json.dumps(metrics))
            
            if not heuristic_agreement:
                logger.warning("SCHED_DIFF %s", json.dumps({"query": ctx.user_input, "heuristic": heuristic_wl, "scheduler": scheduler_wl, "session_id": ctx.session_id}))

        ctx.metadata["execution_plan"] = {
            "run_rag": getattr(plan, "run_rag", True),
            "run_wolfram": plan.run_wolfram
        }

        ctx.needs_wolfram = plan.run_wolfram
        ctx.run_rag = getattr(plan, "run_rag", True)

        if ctx.relational:
            ctx.relational.update_state(ctx.topic)

        # --- Ejecución del Pipeline Seguro ---
        success = True
        try:
            async for chunk in self._safe_execute_pipeline(ctx):
                yield chunk
        except Exception:
            success = False
            raise
        finally:
            if logger.isEnabledFor(logging.INFO):
                outcome = {
                    "event": "PIPELINE_OUTCOME",
                    "session_id": ctx.session_id,
                    "success": success,
                    "executed_wolfram": getattr(ctx, "wolfram_emitted", False),
                    "total_latency": ctx.latency()
                }
                logger.info("PIPELINE_OUTCOME %s", json.dumps(outcome))

    # =========================================================
    # PIPELINE DE ORQUESTACION
    # =========================================================

    async def _execute_pipeline_legacy(self, ctx: QuantumRequestContext) -> AsyncGenerator[str, None]:
        try:
            # 1. RAG (bloqueante parcial) y Wolfram (Late Fusion Fire & Forget)
            rag_task = None
            if getattr(ctx, "run_rag", True):
                rag_task = asyncio.create_task(self._run_rag(ctx))
            
            if ctx.needs_wolfram and self.wolfram:
                ctx.wolfram_task = asyncio.create_task(self._run_wolfram(ctx.user_input))
                yield "⏳ _Calculando resultado simbólico en paralelo..._\n\n"

            # 2. Esperar Resultados RAG (tolerancia a fallos rápida)
            if rag_task:
                try:
                    ctx.rag_data = await asyncio.wait_for(rag_task, timeout=3.5)
                except asyncio.TimeoutError:
                    logger.warning("[RAG] Timeout en búsqueda. Avanzando sin contexto.")
                    ctx.rag_data = {"context": "", "image_pages": []}
            else:
                ctx.rag_data = {"context": "", "image_pages": []}

            # 3. Snapshot cliente (para operaciones con LLM)
            snapshot = await self.get_client_snapshot()

            # 4. CoT Dinámico (Wolfram override triggerea late fusion)
            ctx.reasoning_trace = await self._reason_about_query(ctx, snapshot)
            if ctx.reasoning_trace.get("wolfram_override") is True and not ctx.wolfram_task:
                ctx.wolfram_task = asyncio.create_task(self._run_wolfram(ctx.user_input))

            # 5. Construcción de prompt y validación de cliente
            prompt = self._build_prompt(ctx)

            # 6. Metadata del Contexto
            ctx.metadata = {
                "topic": ctx.topic,
                "context_retrieved": bool(ctx.rag_data and ctx.rag_data.get("context")),
                "image_pages": ctx.rag_data.get("image_pages", []) if ctx.rag_data else [],
                "wolfram_used": ctx.wolfram_result is not None,
                "engine_status": "HYBRID_RELATIONAL",
                "relational_data": ctx.relational.get_affinity_data() if ctx.relational else {},
                "scaffolding": ctx.analytics.get_scaffolding_level(ctx.topic) if ctx.analytics else "default",
                "latency": {"total_pre_stream": ctx.latency()}
            }

            # 7. Streaming Resiliente
            async for chunk in self._stream_llm(ctx, prompt):
                yield chunk

            # =====================================================
            # 8. POST-STREAM LATE FUSION (si llegó tarde)
            # =====================================================
            if ctx.wolfram_task and not ctx.wolfram_emitted:
                try:
                    result = await asyncio.wait_for(ctx.wolfram_task, timeout=2.0)
                    if result and result.get("status") == "success":
                        ctx.wolfram_result = result
                        yield "\n\n---\n"
                        yield "✔ **Resultado computacional (Wolfram Alpha):**\n"
                        if result.get("result_latex"):
                            yield f"$$ {result['result_latex']} $$\n"
                        elif result.get("result_numeric"):
                            yield f"Valor: `{result['result_numeric']}`\n"
                except Exception:
                    pass
                finally:
                    ctx.wolfram_emitted = True

        except asyncio.CancelledError:
            ctx.mark_cancelled()
            logger.info(f"[PIPELINE RUNNER] Sesion {ctx.session_id} cancelada cooperativamente por el usuario.")
            raise
        except Exception as e:
            yield f"\n\n[ERROR SISTÉMICO]: {str(e)}"

    # =========================================================
    # HELPERS DE TAREAS (RAG & WOLFRAM)
    # =========================================================

    async def _run_rag(self, ctx: QuantumRequestContext) -> dict:
        def _run_sync():
            return self.rag.query_with_images(ctx.user_input, k=3, relational_mind=ctx.relational)
        return await asyncio.to_thread(_run_sync)

    async def _run_wolfram(self, user_input: str) -> dict:
        def _run_sync():
            return self.wolfram.query(user_input)
        res = await asyncio.to_thread(_run_sync)
        if res and res.get("status") == "success":
            return res
        return None

    # =========================================================
    # CONSTRUCTOR DE PROMPTS PURO
    # =========================================================

    def _build_prompt(self, ctx: QuantumRequestContext) -> str:
        intent = ctx.intent
        context = ctx.rag_data.get("context", "") if ctx.rag_data else ""
        MAX_CONTEXT_CHARS = 4500
        if len(context) > MAX_CONTEXT_CHARS:
            context = context[:MAX_CONTEXT_CHARS] + "\n...[Contexto truncado]..."

        if intent == "GREETING":
            return (
                f"INSTRUCCIÓN: Eres el tutor de física cuántica de Quantum Tutor {RUNTIME_VERSION}. "
                f"El estudiante te saluda. Responde brevemente.\nCONSULTA: {ctx.user_input}"
            )

        fmt_history = ""
        for msg in ctx.history[-3:]:
            role = "Estudiante" if msg["role"] == "user" else "Tutor"
            fmt_history += f"{role}: {msg['content']}\n"

        entropy = ctx.relational.calculate_entropy() if ctx.relational else 0.0
        r_data = ctx.relational.get_affinity_data() if ctx.relational else {"convergence": 0.0}

        cot_block = ""
        if ctx.reasoning_trace:
            s_strategy = ctx.reasoning_trace.get("pedagogical_strategy", "")
            s_tone = ctx.reasoning_trace.get("tone", "")
            s_warn = ctx.reasoning_trace.get("warning")
            cot_block = f"""
[PREACONDICIONAMIENTO QUANTUM TUTOR {RUNTIME_VERSION}]:
- Tono forzado: {s_tone}
- Directiva pedagógica: {s_strategy}
"""
            if s_warn: cot_block += f"- Warning cognitivo sobre la pregunta: {s_warn}\n"

        wl_context = ""
        if ctx.wolfram_result:
            wl_context = f"\nRESULTADO WOLFRAM ALPHA:\n- Sym: {ctx.wolfram_result.get('result_symbolic')}\n- Num: {ctx.wolfram_result.get('result_numeric')}\n- LaTeX: {ctx.wolfram_result.get('result_latex')}\n"

        prompt = f"""
{self.system_prompt}

CONFIGURACIÓN DE CAMPO:
- TÓPICO: {ctx.topic}
- ENTROPÍA: {entropy:.2f}
- CONVERGENCIA: {r_data.get('convergence', 0.0):.2f}
{cot_block}
HISTORIAL RECIENTE:
{fmt_history or "Sin historial directo cercano."}

CONTEXTO BIBLIOGRÁFICO:
{context or "Sin contexto"}{wl_context}

---
CONSULTA DEL ESTUDIANTE:
{ctx.user_input}

INSTRUCCIONES DE FORMATO:
1. Todo bloque matemático debe ir entre dólares (`$$`) en su propia línea obligatoriamente.
"""
        if intent == "VISUAL":
            prompt += "\nINSTRUCCIÓN VISUAL: Identifica las imágenes de [IMAGEN_DISPONIBLE: references/X.png].\n"

        return prompt

    # =========================================================
    # MOTOR DE STREAMING (SEGURO ANTE CANCELACIÓN Y ROTACIÓN)
    # =========================================================

    async def _stream_llm(self, ctx: QuantumRequestContext, prompt: str, route: Optional[ModelRoute] = None) -> AsyncGenerator[str, None]:
        MAX_RECOVERY = 2
        attempt = 0
        MAX_ROTATIONS = len(self.api_keys) if self.api_keys else 1
        key_rotations = 0

        while attempt <= MAX_RECOVERY:
            # Pedir un snapshot inmutable para este intento.
            # Lo tomamos internamente para mantener segura la rotación de red.
            snapshot = await self.get_client_snapshot()
            client = snapshot["client"]
            model = route.model_name if route else snapshot["model"]
            emitted_text = False

            try:
                async with self._provider_slot(ctx, operation="stream"):
                    stream = await client.aio.models.generate_content_stream(
                        model=model,
                        contents=prompt,
                        config={
                            "max_output_tokens": route.max_output_tokens if route else 512,
                            "temperature": route.temperature if route else self.config.get("temperature", 0.2),
                        },
                    )

                    # BUGFIX: consumir el stream DENTRO del _provider_slot para que
                    # el semaphore no se libere antes de terminar el consumo.
                    async for chunk in stream:
                        # CANCELACIÓN COOPERATIVA EN RUNTIME
                        if ctx.cancelled:
                            logger.info(f"Stream de sesión {ctx.session_id} abortado. Liberando LLM.")
                            break

                        text = getattr(chunk, 'text', None)
                        if text:
                            emitted_text = True
                            yield text

                        # =====================================================
                        # LATE FUSION CHECK (NO BLOQUEANTE)
                        # =====================================================
                        if ctx.wolfram_task and not ctx.wolfram_emitted and ctx.wolfram_task.done():
                            try:
                                result = ctx.wolfram_task.result()
                                if result and result.get("status") == "success":
                                    ctx.wolfram_result = result
                                    yield "\n\n---\n"
                                    yield "✔ **Resultado computacional (Wolfram Alpha):**\n"
                                    if result.get("result_latex"):
                                        yield f"$$ {result['result_latex']} $$\n"
                                    elif result.get("result_numeric"):
                                        yield f"Valor: `{result['result_numeric']}`\n"
                            except Exception:
                                pass
                            finally:
                                ctx.wolfram_emitted = True

                    if not emitted_text and not ctx.cancelled:
                        logger.warning("[STREAM] El proveedor cerro el stream sin texto. Activando fallback local.")
                        yield self._build_local_fallback(ctx)

                # Éxito (salimos del loop de recovery)
                ctx.metadata["circuit_breaker"] = self._record_provider_success().as_metadata()
                return

            except asyncio.CancelledError:
                ctx.mark_cancelled()
                raise

            except RequestBackpressureError as e:
                ctx.metadata["backpressure"] = e.decision.as_metadata()
                if ctx.rate_limit_mode == "hard":
                    return
                yield self._build_backpressure_fallback(ctx, e.decision)
                return

            except Exception as e:
                status, retry_after = self._classify_provider_error(e)
                short_key = snapshot["api_key"][:8] if snapshot.get("api_key") else "N/A"
                err_str = str(e)
                if status == "RATE_LIMIT":
                    ctx.metadata["circuit_breaker"] = self._record_provider_failure(status).as_metadata()
                    logger.warning(f"Rate limit en nodo {short_key}. Rotando ({key_rotations+1}/{MAX_ROTATIONS})...")
                    self.register_rate_limit(snapshot, retry_after or 80.0)
                    key_rotations += 1
                    if key_rotations >= MAX_ROTATIONS:
                        self._degrade_to_local_fallback("stream: todos los nodos entraron en RATE_LIMIT.")
                        break
                    
                    recovered = await self._recover_after_provider_failure(
                        snapshot,
                        status,
                        retry_after,
                        context="stream",
                    )
                    if recovered:
                        yield "⚡_ROTATION_SIGNAL_⚡"
                        continue
                    break

                if status in {"TIMEOUT", "UNAVAILABLE"}:
                    ctx.metadata["circuit_breaker"] = self._record_provider_failure(status).as_metadata()
                    logger.warning(
                        f"Error transitorio {status} en nodo {short_key}. "
                        f"Recuperando (intento {attempt+1}): {e}"
                    )
                    recovered = await self._recover_after_provider_failure(
                        snapshot,
                        status,
                        retry_after,
                        context="stream",
                    )
                    attempt += 1
                    if recovered and attempt <= MAX_RECOVERY:
                        await asyncio.sleep(0.5 * attempt)
                        continue
                    break

                if status == "INVALID" or "400" in err_str or "INVALID_ARGUMENT" in err_str:
                    await self._recover_after_provider_failure(
                        snapshot,
                        "INVALID" if status == "INVALID" else "ERROR",
                        retry_after,
                        context="stream",
                    )
                    logger.error(f"Error fatal de request en stream ({status}): {e}")
                    break

                attempt += 1
                if attempt <= MAX_RECOVERY:
                    await asyncio.sleep(0.5 * attempt)

        if not ctx.cancelled:
            yield f"\n\n*(⚠️ Error en proveedor de IA)*"
    async def _execute_pipeline(self, ctx: QuantumRequestContext) -> AsyncGenerator[str, None]:
        try:
            route = self._select_model_route(ctx)
            deterministic_response = self._try_deterministic_response(ctx)
            if deterministic_response:
                self._update_metadata(ctx)
                yield deterministic_response
                return

            cached_response = self._lookup_response_cache(ctx, route)
            if cached_response:
                self._update_metadata(ctx)
                yield cached_response["response"]
                return

            rag_task = None
            if getattr(ctx, "run_rag", True):
                rag_task = asyncio.create_task(self._run_rag(ctx))

            if ctx.needs_wolfram and self.wolfram:
                ctx.wolfram_task = asyncio.create_task(self._run_wolfram(ctx.user_input))
                yield "[Calculando resultado simbólico en paralelo...]\n\n"

            if rag_task:
                try:
                    ctx.rag_data = await asyncio.wait_for(rag_task, timeout=3.5)
                except asyncio.TimeoutError:
                    logger.warning("[RAG] Timeout en búsqueda. Avanzando sin contexto.")
                    ctx.rag_data = {"context": "", "image_pages": []}
            else:
                ctx.rag_data = {"context": "", "image_pages": []}

            snapshot = await self.get_client_snapshot()
            self._update_metadata(ctx)

            if not self.llm_enabled or not snapshot.get("client"):
                await self._resolve_wolfram_task(ctx, timeout=4.0)

                self._update_metadata(ctx)
                yield self._build_local_fallback(ctx)
                return

            breaker_decision = self._apply_provider_circuit_breaker(ctx)
            if not breaker_decision.allowed:
                await self._resolve_wolfram_task(ctx, timeout=4.0)
                self._update_metadata(ctx)
                yield self._build_circuit_breaker_fallback(ctx, breaker_decision)
                return

            decision = self._apply_rate_limit(ctx)
            if not decision.allowed:
                await self._resolve_wolfram_task(ctx, timeout=4.0)
                self._update_metadata(ctx)
                if ctx.rate_limit_mode == "hard":
                    raise RequestRateLimitedError(
                        decision,
                        "Rate limit exceeded before contacting the provider.",
                    )
                yield self._build_rate_limited_fallback(ctx, decision)
                return

            ctx.reasoning_trace = {}
            if route.reasoning_enabled:
                ctx.reasoning_trace = await self._reason_about_query(ctx, snapshot, route)
            if ctx.reasoning_trace.get("wolfram_override") is True and not ctx.wolfram_task:
                ctx.wolfram_task = asyncio.create_task(self._run_wolfram(ctx.user_input))

            prompt = self._build_prompt(ctx)
            response_parts: List[str] = []

            try:
                async for chunk in self._stream_llm(ctx, prompt, route):
                    response_parts.append(chunk)
                    yield chunk
            except RequestBackpressureError as e:
                ctx.metadata["backpressure"] = e.decision.as_metadata()
                self._update_metadata(ctx)
                if ctx.rate_limit_mode == "hard":
                    raise
                yield self._build_backpressure_fallback(ctx, e.decision)
                return

            result = await self._resolve_wolfram_task(ctx, timeout=2.0)
            if result:
                for chunk in self._yield_wolfram_result_chunks(
                    result,
                    "[Resultado computacional (Wolfram Alpha)]",
                ):
                    response_parts.append(chunk)
                    yield chunk

            full_response = "".join(response_parts)
            if self._should_store_response_cache(ctx, route, full_response):
                self.response_cache.store(
                    query=ctx.user_input,
                    response=full_response,
                    namespace=route.cache_namespace,
                    metadata={
                        "topic": ctx.topic,
                        "tier": route.tier,
                        "model_name": route.model_name,
                    },
                    semantic_enabled=True,
                )
                ctx.metadata.setdefault("cache", {"eligible": route.cacheable, "hit": False})
                ctx.metadata["cache"]["stored"] = True

            self._update_metadata(ctx)

        except asyncio.CancelledError:
            ctx.mark_cancelled()
            logger.info(f"[PIPELINE RUNNER] Sesión {ctx.session_id} cancelada cooperativamente por el usuario.")
            raise
        except Exception as e:
            yield f"\n\n[ERROR SISTÉMICO]: {str(e)}"
