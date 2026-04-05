# Quantum Tutor Manual Operativo

Version operativa actual: `v6.1-stateless`

## 1. Que es hoy el proyecto

Quantum Tutor es un tutor de mecanica cuantica con estas capas activas:

- Orquestador stateless por request.
- RAG multi-fuente sobre Galindo & Pascual, Cohen-Tannoudji y Sakurai.
- Scheduler para decidir cuando usar contexto bibliografico y cuando lanzar calculo simbolico.
- Fallback local cuando el cliente LLM no esta disponible.
- Interfaz Streamlit y API FastAPI.
- Soporte multimodal para analizar derivaciones subidas como imagen.

## 2. Contrato tecnico actual

El runtime vigente se define por estos archivos:

- `quantum_tutor_runtime.py`
- `quantum_tutor_orchestrator.py`
- `quantum_tutor_config.json`

Si alguno de esos archivos contradice documentos mas antiguos, el runtime actual tiene prioridad.

## 3. Flujo principal

1. Se crea un `QuantumRequestContext` por consulta.
2. El orquestador detecta intento, tema y plan de ejecucion.
3. Se ejecuta RAG, y Wolfram puede correr en paralelo si el scheduler lo decide.
4. Antes de tocar el proveedor, el runtime intenta responder por via deterministica o con contenido precomputado para consultas comunes.
5. Si hay cliente LLM disponible y la consulta sigue requiriendo generacion, se hace streaming de respuesta.
6. Si no hay cliente LLM, o si la cuota temporal se agota, el sistema responde con fallback local usando contexto recuperado y, si existe, resultado simbolico.
7. Se devuelve metadata consistente con latencia, imagenes, tema, cache, routeo y uso de Wolfram.

## 4. Entradas importantes del repo

- `app_quantum_tutor.py`: UI Streamlit.
- `api_quantum_tutor.py`: API HTTP.
- `rag_engine.py`: indexacion y busqueda.
- `multimodal_vision_parser.py`: vision.
- `tool_scheduler.py`: politica de herramientas.
- `adaptive_learning_engine.py`: mapa curricular, diagnostico, ruta personalizada, milestones y badges.
- `learning_content.py`: generadores deterministas de ejercicios y micro-lecciones.
- `tests`: hoy se expresan como archivos `test_*.py` ejecutables por `pytest`.

## 4.1 Capa de aprendizaje guiado

- Endpoints nuevos:
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
- Estado persistente:
  - `outputs/state/learning_curriculum.json`
  - `outputs/state/learning_progress.json`
  - `outputs/state/learning_diagnostics.json`
  - `outputs/state/learning_gamification.json`
- Scripts auxiliares:
  - `python scripts/generar_ejercicios.py --tema efecto_tunel --dificultad medium --count 3`
  - `python scripts/generar_leccion.py --node-id qm_ecuacion_schrodinger`
- Diseno de referencia: `adaptive_learning_blueprint.md`
- Streamlit ya expone una pestana `Learning Journey` para ejecutar diagnostico, ver ruta, mastery, reviews espaciados, misconceptions, milestones, badges y guardar progreso.
- Las interacciones del chat ahora suman senales de progreso suaves sobre nodos mapeados, sin marcar completitud automatica.
- El dashboard analitico ahora muestra KPIs de aprendizaje: pretest, posttest, mejora, finalizacion, progreso por nodo, persona, dificultad adaptativa, repasos vencidos, misconceptions y eventos derivados del chat.
- El engine asigna una variante A/B estable de gamificacion por estudiante (`control` o `challenge`) para analitica experimental.
- Los exportes de cohorte quedan en `outputs/reports/learning_cohort_report.json` y `outputs/reports/learning_cohort_students.csv`.
- La consola `static_web` ya muestra nivel, puntos, siguiente nodo y permite lanzar el diagnostico inicial desde el cliente web.
- La progresion ahora exige `mastery >= 0.85`, usa prerrequisitos reales del knowledge graph y programa `next_review_at`, `retention_score` y `review_count` por nodo.
- La nueva capa `learning insights` agrega cohortes multidimensionales por persona, misconception dominante, modulo y variante A/B, junto con learning gain, time-to-mastery, retention, error reduction y misconception resolution.
- El engine puede aplicar ajustes automaticos de andamiaje, dificultad y remediacion cuando una cohorte queda por debajo de los umbrales de efectividad.
- Streamlit expone ahora una pestana `Admin Dashboard` para roles `admin` y `professor`, con readiness experimental, semaforos pedagogicos, top misconceptions por modulo, comparacion A/B, cohortes criticas y recomendaciones interpretables.

## 5. Ejecucion local

## 5.1 Sistema API keys Gemini

- El runtime acepta `GEMINI_API_KEYS` con multiples claves separadas por coma.
- Si solo existe una credencial, tambien funciona `GEMINI_API_KEY`.
- El orquestador verifica salud al arranque, aplica cooldown al nodo que cae en `429/RESOURCE_EXHAUSTED` y rota al siguiente nodo disponible.
- Antes de llamar a Gemini, se aplica token bucket por usuario y se intentan respuestas precomputadas / simbolicas locales.
- La UI Streamlit y la consola web exponen el tiempo estimado del proximo reintento cuando hay cuota agotada, cooldown o backpressure.
- Antes de levantar entornos compartidos, conviene correr `python verify_api_keys.py`.

## 5.2 Bootstrap de autenticacion

- En despliegues nuevos, el admin inicial debe provisionarse con `QT_BOOTSTRAP_ADMIN_EMAIL` y `QT_BOOTSTRAP_ADMIN_PASSWORD`.
- El admin hardcodeado historico ya no se crea por defecto; solo puede reactivarse con `QT_ALLOW_INSECURE_DEFAULT_ADMIN=true` para dev local.
- Las sesiones de login ya no se restauran desde query params.

## 5.3 CORS de la API

- La API usa `QUANTUM_TUTOR_CORS_ORIGINS` para definir orígenes permitidos.
- Si se usa `*`, FastAPI desactiva credenciales CORS deliberadamente.

## 5.4 Seguridad de borde de la API

- `/api/chat` y `/api/vision` aplican un token bucket de borde antes de tocar el core del tutor.
- Los headers `X-Forwarded-For`, `X-Real-IP` y `X-User-Id` no se confian por defecto.
- Para aceptar identidad desde un reverse proxy, habilitar `QT_TRUST_PROXY_HEADERS=true` y definir `QT_TRUSTED_PROXY_RANGES`.
- La identidad autenticada para rate limit debe llegar por `X-Authenticated-User` desde un proxy confiable.
- Los claims directos `user_id` quedan deshabilitados por defecto y solo deben activarse en entornos controlados.
- El abuso repetido de la API ahora acumula score y puede activar un bloqueo temporal con `403` y `Retry-After`.
- Los uploads de vision ahora validan tamano, MIME type y extension antes de parsear la imagen.
- Estado persistente de esta capa: `outputs/state/api_edge_rate_limits.json`.
- Eventos persistentes: `outputs/logs/security_events.jsonl`.

## 5.5 Circuit breaker del proveedor

- El runtime ahora aplica circuit breaker antes de entrar al camino costoso de Gemini.
- Fallos transitorios repetidos (`RATE_LIMIT`, `TIMEOUT`, `UNAVAILABLE`) abren el breaker y fuerzan fallback local temporal.
- La UI puede reflejar este estado como `CIRCUIT_BREAKER_LOCAL` mientras dure la ventana de recuperacion.
- Estado persistente: `outputs/state/provider_circuit_breakers.json`.

## 5.6 Review admin y gateway

- La consola `Admin Security Review` en Streamlit permite revisar eventos, ver identidades bloqueadas y resetear circuit breakers manualmente.
- Los desbloqueos manuales y resets quedan auditados en `outputs/logs/security_events.jsonl`.
- Si la UI no esta disponible, existe soporte CLI:
  - `python security_admin.py events --limit 50`
  - `python security_admin.py abuse-list`
  - `python security_admin.py abuse-unblock <identity>`
  - `python security_admin.py breaker-list`
  - `python security_admin.py breaker-reset gemini_text`
- Para despliegue real con reverse proxy, usar `deployment/nginx/quantum_tutor.conf` y `deployment/cloudflare/cloudflared-config.yml.example`.
- Topologia recomendada: `Cliente -> Cloudflare Edge -> cloudflared -> Nginx -> FastAPI + Streamlit`.
- Hostnames de produccion previstos: `quantumtutor.cl`, `api.quantumtutor.cl` y `admin.quantumtutor.cl`.
- La consola `Admin Security Review` solo se expone en `admin.quantumtutor.cl`.
- En produccion, mantener `QT_ALLOW_ADMIN_REVIEW_ANY_HOST=false`.
- Plantilla de entorno productivo: `deployment/env/quantum_tutor.env.example`.
- Servicios de sistema: `deployment/systemd/`.
- Smoke check de borde: `python deployment/scripts/smoke_check.py --ui-url https://quantumtutor.cl --api-url https://api.quantumtutor.cl`.

App Streamlit:

```powershell
streamlit run app_quantum_tutor.py
```

API:

```powershell
uvicorn api_quantum_tutor:app --reload
```

Suite:

```powershell
python -m pytest -q
```

## 6. Estado de pruebas

La suite rapida del repo esta pensada para ser determinista y no depender de PDF reales ni de llamadas externas para el ciclo diario de desarrollo.

Objetivo operativo:

- `pytest -q` debe seguir verde.
- Los tests no deben depender de nombres de version historicos.
- Los scripts de exploracion o artefactos viejos no deben contaminar la suite rapida.

## 7. Documentos historicos

Estos archivos se conservan como referencia de diseno, no como especificacion vigente:

- `legacy/docs/QuantumTutor_v1.2_Especificacion.md`
- `legacy/docs/Roadmap_v2.0.md`
- `legacy/docs/conversacion_completa.md`

## 8. Artefactos generados

Los reportes y snapshots activos viven en `outputs/`. No son documentacion fuente, sino resultados generados o snapshots auxiliares.

Estado local vigente del runtime:

- `outputs/state/`: autenticacion, estado de rate limit y perfil cognitivo.
- `outputs/cache/`: cache semantica e indice RAG serializado.
- `outputs/logs/`: log principal del orquestador y crash dumps de API.

## 9. Mantenimiento recomendado

- Mantener las versiones visibles alineadas con `quantum_tutor_runtime.py`.
- Evitar duplicar logica de metadata o resolucion de tareas en el orquestador.
- Tratar `static`, `static_web`, reportes y dashboards antiguos como artefactos que pueden quedar desfasados si no se actualizan junto al runtime.
