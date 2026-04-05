# Quantum Tutor

Current runtime: `v6.1-stateless`

Quantum Tutor is a quantum mechanics tutor built around a stateless orchestrator, multi-source RAG, optional Wolfram-style symbolic support, a Streamlit app, and a FastAPI surface.

## Runtime Truth

The current source of truth for runtime identity is:

- `quantum_tutor_runtime.py`
- `quantum_tutor_orchestrator.py`
- `quantum_tutor_config.json`

The project no longer matches the older `v1.x`, `v2.0`, `v4.3`, or `v5.1` labels that still appear in historical artifacts.

## Main Components

- `quantum_tutor_orchestrator.py`: stateless request pipeline, scheduling, RAG/Wolfram coordination, fallback behavior.
- `rag_engine.py`: ingestion, retrieval, image/page reference mapping, and keyword fallback.
- `api_quantum_tutor.py`: FastAPI wrapper for chat and vision endpoints.
- `app_quantum_tutor.py`: Streamlit interface.
- `multimodal_vision_parser.py`: image-to-steps parsing for handwritten or uploaded derivations.
- `tool_scheduler.py`: routing policy for RAG/Wolfram execution.
- `adaptive_learning_engine.py`: curriculum graph, diagnostic bank, personalized route, milestones, and gamification state.
- `learning_content.py`: deterministic exercise and micro-lesson generators.

## Adaptive Learning Foundation

- A first guided-learning layer now exists on top of the tutor runtime.
- New endpoints:
  - `GET /api/diagnostico-inicial`
  - `POST /api/evaluar-respuesta`
  - `GET /api/ruta-personalizada`
  - `POST /api/guardar-progreso`
  - `GET /api/curriculum`
  - `GET /api/learning-kpis`
  - `GET /api/learning-review-queue`
  - `GET /api/learning-insights`
  - `POST /api/guardar-evaluacion`
  - `GET /api/learning-cohort-report`
  - `POST /api/learning-cohort-export`
- The adaptive engine persists state under:
  - `outputs/state/learning_curriculum.json`
  - `outputs/state/learning_progress.json`
  - `outputs/state/learning_diagnostics.json`
  - `outputs/state/learning_gamification.json`
- Deterministic content assets now live in:
  - `scripts/generar_ejercicios.py`
  - `scripts/generar_leccion.py`
  - `prompts/generar_ejercicios.md`
  - `prompts/generar_feedback.md`
  - `templates/micro_leccion.md`
- High-level design and roadmap: `adaptive_learning_blueprint.md`
- Streamlit now exposes this layer in the `Learning Journey` tab with diagnostic, mastery threshold, spaced reviews, misconceptions, micro-lessons, exercise suggestions, and progress save.
- Chat interactions now contribute lightweight automatic progress signals on mapped topics.
- The analytics dashboard now surfaces pretest/posttest, improvement, completion rate, node progress, personas, spaced-review pressure, misconceptions, milestones, and chat-derived learning events.
- Cohort analytics and simple A/B gamification flags are now available from the adaptive engine, API, and analytics dashboard.
- Cohort exports are written to `outputs/reports/learning_cohort_report.json` and `outputs/reports/learning_cohort_students.csv`.
- The static web console now surfaces route status in the sidebar and can launch the adaptive diagnostic directly from the browser.
- The adaptive loop now enforces `mastery >= 0.85` before progression, schedules spaced repetition reviews, tracks learner persona, and syncs those signals into `student_profile.json`.
- Experimental pedagogy analytics now compute multidimensional cohorts (`persona|misconception|module|variant`), learning gain, time to mastery, retention, error reduction, misconception resolution, and optimization recommendations through `GET /api/learning-insights`.
- Streamlit now exposes an `Admin Dashboard` for `admin` and `professor` roles with experiment readiness, ITS metric semaphores, top misconceptions by module, A/B comparison, critical cohorts, and human-readable recommendations.

## How To Run

## Gemini API Keys

- Prefer `GEMINI_API_KEYS` with comma-separated keys for rotation and cooldown on `429/RESOURCE_EXHAUSTED`.
- `GEMINI_API_KEY` remains supported as a single-key fallback.
- Before starting a shared or production-like environment, run `python verify_api_keys.py` to validate configured nodes.

## Usage Control

- The runtime now applies a token-bucket guard before Gemini requests.
- Common definitions and small symbolic tasks are now answered locally before the bucket/provider path.
- A lightweight backpressure guard now protects the provider queue under concurrent bursts.
- Defaults: `20` requests capacity, refill `1` request every `3` seconds.
- API clients receive `429` plus `Retry-After` when the bucket is exhausted.
- API clients also receive `429` plus `Retry-After` when provider backpressure trips.
- The Streamlit UI and the static web monitor now surface the estimated next retry for quota and provider queue pressure.
- Tune with `QT_RATE_LIMIT_CAPACITY`, `QT_RATE_LIMIT_REFILL_TOKENS`, and `QT_RATE_LIMIT_REFILL_SECONDS`.
- Tune backpressure with `QT_PROVIDER_MAX_CONCURRENCY` and `QT_PROVIDER_QUEUE_TIMEOUT_SECONDS`.
- LLM response caching is persisted under `outputs/cache/llm_response_cache.json`.
- Model routing can be tuned with `QT_MODEL_SIMPLE`, `QT_MODEL_MEDIUM`, `QT_MODEL_COMPLEX`, `QT_MAX_TOKENS_SIMPLE`, `QT_MAX_TOKENS_MEDIUM`, and `QT_MAX_TOKENS_COMPLEX`.

## API Edge Security

- `/api/chat` and `/api/vision` now apply an edge token bucket before hitting the core runtime.
- Forwarded headers are ignored by default. Enable trusted proxy resolution with `QT_TRUST_PROXY_HEADERS=true` and `QT_TRUSTED_PROXY_RANGES`.
- Authenticated user identity should arrive from a trusted proxy through `X-Authenticated-User`. Direct `user_id` claims are disabled by default.
- Repeated edge abuse now accumulates score and can trigger a temporary block with `403` plus `Retry-After`.
- Tune edge buckets with `QT_EDGE_CHAT_CAPACITY`, `QT_EDGE_CHAT_REFILL_TOKENS`, `QT_EDGE_CHAT_REFILL_SECONDS`, `QT_EDGE_VISION_CAPACITY`, `QT_EDGE_VISION_REFILL_TOKENS`, and `QT_EDGE_VISION_REFILL_SECONDS`.
- Tune request guards with `QT_API_MAX_BODY_BYTES`, `QT_API_MAX_HISTORY_MESSAGES`, `QT_API_MAX_HISTORY_CHARS`, `QT_API_MAX_HISTORY_ENTRY_CHARS`, `QT_VISION_MAX_UPLOAD_BYTES`, `QT_VISION_ALLOWED_TYPES`, and `QT_VISION_ALLOWED_SUFFIXES`.
- Tune temporary abuse blocking with `QT_ABUSE_BLOCK_THRESHOLD`, `QT_ABUSE_DECAY_SECONDS`, `QT_ABUSE_BLOCK_SECONDS`, and `QT_ABUSE_MAX_BLOCK_SECONDS`.
- Edge rate-limit state is persisted under `outputs/state/api_edge_rate_limits.json`.
- Abuse-block state is persisted under `outputs/state/api_abuse_state.json`.
- Security events are appended to `outputs/logs/security_events.jsonl`.
- Admin review is available from the Streamlit `Admin Security Review` expander and from `python security_admin.py`.

## Provider Resilience

- Gemini calls now honor a provider circuit breaker before entering the expensive runtime path.
- Repeated transient provider failures (`RATE_LIMIT`, `TIMEOUT`, `UNAVAILABLE`) open the breaker and force local fallback until the retry window expires.
- Tune the breaker with `QT_PROVIDER_BREAKER_FAILURE_THRESHOLD`, `QT_PROVIDER_BREAKER_WINDOW_SECONDS`, `QT_PROVIDER_BREAKER_OPEN_SECONDS`, `QT_PROVIDER_BREAKER_HALF_OPEN_RETRY_SECONDS`, and `QT_PROVIDER_BREAKER_NAME`.
- Circuit-breaker state is persisted under `outputs/state/provider_circuit_breakers.json`.

## Gateway Deployment

- Production gateway assets live in `deployment/nginx/quantum_tutor.conf` and `deployment/cloudflare/cloudflared-config.yml.example`.
- Recommended topology: `Client -> Cloudflare Edge -> cloudflared -> Nginx -> FastAPI + Streamlit`.
- Current production host split: `quantumtutor.cl` for public UI, `api.quantumtutor.cl` for API, and `admin.quantumtutor.cl` for the admin UI protected by Access.
- Nginx should be the only trusted reverse proxy for the app process and should forward `X-Authenticated-User` plus the real client IP.
- Access and gateway logs should be reviewed together with `outputs/logs/security_events.jsonl` during abuse investigations or manual unblock operations.
- Production env and service templates live in `deployment/env/quantum_tutor.env.example` and `deployment/systemd/`.
- The admin security console is only exposed on `admin.quantumtutor.cl`.
- In production, keep `QT_ALLOW_ADMIN_REVIEW_ANY_HOST=false`.
- A safe smoke test is available at `python deployment/scripts/smoke_check.py --ui-url https://quantumtutor.cl --api-url https://api.quantumtutor.cl`.

## Auth Bootstrap

- On a fresh deployment, provision the initial admin with `QT_BOOTSTRAP_ADMIN_EMAIL` and `QT_BOOTSTRAP_ADMIN_PASSWORD`.
- The old hardcoded default admin path is now opt-in only through `QT_ALLOW_INSECURE_DEFAULT_ADMIN=true` and should stay disabled outside local dev.

## API CORS

- Configure API browser access with `QUANTUM_TUTOR_CORS_ORIGINS`.
- `*` is still supported, but it disables credentialed CORS by design.

Streamlit app:

```powershell
streamlit run app_quantum_tutor.py
```

FastAPI app:

```powershell
uvicorn api_quantum_tutor:app --reload
```

Test suite:

```powershell
python -m pytest -q
```

## Documentation Status

Current operational docs:

- `README.md`
- `manual_quantum_tutor.md`

Operational support scripts kept in the active workspace surface:

- `verify_api_keys.py`
- `check_gemini_models.py`
- `quantum_stress_test.py`
- `batch_ingest_ocr.py`
- `deploy_tutor.py`

Generated artifacts kept in the active workspace surface:

- `outputs/`

Runtime-local state now lives under:

- `outputs/state/`: auth DB, rate-limit state, learning profile.
- `outputs/cache/`: semantic cache and RAG index cache.
- `outputs/logs/`: runtime logs and crash dumps.

Historical design docs kept for context:

- `legacy/docs/QuantumTutor_v1.2_Especificacion.md`
- `legacy/docs/Roadmap_v2.0.md`
- `legacy/docs/conversacion_completa.md`
- `legacy/tools/`

Those historical files are useful to understand how the project evolved, but they should not be treated as the runtime contract.
