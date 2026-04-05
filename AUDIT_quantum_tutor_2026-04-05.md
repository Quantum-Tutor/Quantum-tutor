# Auditoría Técnica Total de Quantum Tutor

Fecha: 2026-04-05  
Auditor: Codex (modo auditoría técnica crítica)  
Workspace: `C:\Users\abske\.gemini\antigravity\scratch\quantum_tutor`

## Alcance y método

Esta auditoría prioriza el **código que realmente participa en el runtime productivo**:

- API FastAPI
- UI Streamlit
- consola web estática
- motor ITS / adaptive learning
- seguridad / rate limit / circuit breaker
- orquestador LLM / RAG / visión
- persistencia y estado
- despliegue Nginx / systemd / cloudflared
- tests críticos

Se hizo además inventario del resto del repositorio.  
Hallazgo transversal importante: el repo está **muy contaminado con artefactos runtime** (`api_abuse_state_*.json`, `api_edge_rate_limits_*.json`, `outputs/*`) y eso ya es en sí un riesgo operativo y de disciplina de release.

## Resumen ejecutivo

### Veredicto

**Quantum Tutor no está listo para producción real multiusuario ni para exposición institucional pública en su estado actual.**

La plataforma ya tiene muchísimo valor funcional y pedagógico, pero hoy mantiene varios riesgos de primer orden:

1. **Exposición de datos y mutación no autorizada del estado pedagógico**.
2. **Escalada de privilegios funcional por auto-registro como `professor`.**
3. **XSS real en la consola web estática.**
4. **Persistencia file-backed con riesgos serios de corrupción/race conditions.**
5. **Controles de backpressure y streaming parcialmente inefectivos.**
6. **Analítica ITS y dashboard con señales que pueden sesgar decisiones pedagógicas.**

### Hallazgos críticos principales

1. **IDOR / bypass de identidad en endpoints de aprendizaje**  
   `api_quantum_tutor.py:278-280`, `api_quantum_tutor.py:448-567`  
   El API acepta `student_id` explícito y lo prioriza sobre la identidad resuelta por seguridad.

2. **Endpoints de learning analytics sin autenticación ni autorización**  
   `api_quantum_tutor.py:448-567`  
   Cualquier cliente puede leer KPI, cohortes, insights y exportes.

3. **Auto-registro como `professor` habilitado desde UI pública**  
   `auth_module.py:563-564`, `auth_module.py:591`, `app_quantum_tutor.py:612`, `app_quantum_tutor.py:834`, `app_quantum_tutor.py:1797-1801`  
   Esto abre dashboards docentes e insights a terceros sin control institucional.

4. **XSS real en la consola web**  
   `static_web/app.js:302`, `static_web/app.js:313`, `static_web/app.js:150`, `static_web/app.js:263`  
   Se usa `marked.parse()` + `innerHTML` sin sanitización.

5. **GET `/api/learning-insights` con side effects**  
   `api_quantum_tutor.py:533-549`, `adaptive_learning_engine.py:2167-2288`  
   Ver un dashboard puede modificar perfiles y recomendaciones.

6. **Backpressure del proveedor no cubre toda la vida del stream**  
   `quantum_tutor_orchestrator.py:1239-1249`  
   El semáforo protege el arranque del stream, no su consumo.

7. **Rotación de claves Gemini puede abortar prematuramente**  
   `quantum_tutor_orchestrator.py:381`  
   `break` sobre clave `INVALID` corta la búsqueda de claves sanas posteriores.

8. **Vision fallback fabrica resultados falsos en vez de degradar honestamente**  
   `multimodal_vision_parser.py:37-39`, `multimodal_vision_parser.py:74-77`, `multimodal_vision_parser.py:79-114`  
   Si falla Gemini o no hay imagen válida, el sistema devuelve pasos simulados.

## Detalle por archivo

## 📁 `api_quantum_tutor.py`

### 🔴 Problemas críticos

- **Bypass de identidad en endpoints de aprendizaje**  
  `api_quantum_tutor.py:278-280`  
  `_resolved_learning_student_id()` devuelve `explicit_student_id` antes que la identidad resuelta por `api_security`.  
  Impacto: cualquier actor puede leer o modificar progreso ajeno si conoce o adivina un `student_id`.  
  Reproducción:
  1. Llamar `GET /api/learning-kpis?student_id=student-api`.
  2. Repetir con cualquier otro ID arbitrario.
  3. El sistema responde sin autenticación ni ownership check.

- **Endpoints pedagógicos sensibles sin authz**  
  `api_quantum_tutor.py:448-567`  
  `learning-kpis`, `learning-review-queue`, `learning-cohort-report`, `learning-insights`, `learning-cohort-export` no exigen usuario autenticado ni rol.  
  Impacto: fuga de analítica pedagógica, mutación de cohortes, exportes no autorizados, problemas RGPD/FERPA.

- **GET con efectos laterales**  
  `api_quantum_tutor.py:533-549`  
  `apply_optimization=True` por defecto en un `GET`.  
  Impacto: observación cambia el sistema; rompe semántica HTTP, auditoría y causalidad experimental.  
  Reproducción:
  1. Invocar `/api/learning-insights`.
  2. Revisar `optimization_profile` o estado persistido.
  3. Se observan cambios sin operación explícita de escritura.

- **Leaking de errores internos**  
  `api_quantum_tutor.py:689-699`, `api_quantum_tutor.py:773-778`  
  El API devuelve `details: str(e)` o `message: str(e)` al cliente.  
  Impacto: fuga de paths, SDK state, errores internos, pistas útiles para explotación.

### 🟡 Problemas importantes

- **PII / contenido sensible en logs**  
  `api_quantum_tutor.py:575`, `api_quantum_tutor.py:673`  
  Se imprime el inicio del prompt del usuario y el resultado del request.  
  Impacto: exposición de consultas educativas en stdout / journald.

- **La API usa `LearningAnalytics` legacy y `AdaptiveLearningEngine` en paralelo**  
  `api_quantum_tutor.py:642-656`  
  El chat actualiza `analytics.log_interaction(...)`, no el motor ITS principal.  
  Impacto: doble modelo de estudiante, insights inconsistentes entre chat, Streamlit y learning journey.

- **Validación de longitud del query en endpoint, no en schema**  
  `api_quantum_tutor.py:577-589`  
  No es un bug grave, pero deja contratos mezclados entre Pydantic, seguridad y endpoint.

### 🟢 Mejoras recomendadas

- Unificar resolución de identidad: `resolved_student_id = identity.authenticated_user or identity.provider_user_id`; ignorar `student_id` externo salvo modo explícitamente confiable.
- Proteger todo `/api/learning-*` con authn + authz por rol/owner.
- Cambiar `GET /api/learning-insights` a lectura pura y mover optimización a `POST /api/learning-optimize`.
- Reemplazar logs `print(...)` por logging estructurado sin texto de usuario.

### 💡 Sugerencias avanzadas

- Separar la API pública de tutoría de la API institucional/analytics.
- Emitir contratos OpenAPI distintos para `student`, `teacher`, `admin`.

## 📁 `api_security.py`

### 🔴 Problemas críticos

- No encontré un bug crítico autónomo en este archivo; el problema grave está en que **`api_quantum_tutor.py` lo bypassa** para learning endpoints.

### 🟡 Problemas importantes

- **Body-size enforcement parcial**  
  `api_security.py:376-383`, `api_security.py:403-410`  
  La pre-validación depende de `Content-Length`.  
  Impacto: requests chunked o maliciosos pueden esquivar parte del control previo y consumir memoria antes del rechazo.

- **Abuse identity simplificada por IP**  
  `api_security.py:289-299`  
  `abuse_key` cae a `ip:{client_ip}` cuando no hay usuario autenticado.  
  Impacto: bloqueos colectivos detrás de NAT institucional.

### 🟢 Mejoras recomendadas

- Aplicar middleware de tamaño máximo real a nivel ASGI, no solo header checks.
- Diferenciar throttling duro por IP y score pedagógico / usuario.

### 💡 Sugerencias avanzadas

- Añadir `TrustedHostMiddleware`; hoy `ALLOWED_HOSTS` se documenta pero no se aplica en runtime.

## 📁 `auth_module.py`

### 🔴 Problemas críticos

- **Auto-registro como `professor` desde UI pública**  
  `auth_module.py:563-564`, `auth_module.py:591`  
  Cualquier visitante puede crear una cuenta con rol `professor`.  
  Impacto: acceso a dashboard docente, cohortes, exportes y learning intelligence sin validación institucional.  
  Reproducción:
  1. Abrir pestaña registro.
  2. Elegir rol `professor`.
  3. Crear cuenta.
  4. Acceder al dashboard pedagógico.

- **Admin por defecto inseguro todavía presente**  
  `auth_module.py:199-216`  
  Sigue existiendo `admin@quantumtutor.edu / admin2024` condicionado por env.  
  Impacto: error operacional catastrófico si esa flag se activa por descuido.

### 🟡 Problemas importantes

- **Fallback a SHA-256 sin salt si falta bcrypt**  
  `auth_module.py:183-196`  
  Impacto: almacenamiento de password débil si el entorno arranca sin bcrypt.

- **Lockout file-backed sin coordinación multi-proceso**  
  `auth_module.py:283-335`  
  Impacto: estados de lockout inconsistentes en despliegues con más de un worker.

- **UI auth con abundante `unsafe_allow_html=True`**  
  `auth_module.py:439-508`  
  Hoy la mayoría del HTML es propio, pero el patrón es frágil.

### 🟢 Mejoras recomendadas

- Eliminar auto-selección de `professor`; registrar solo `student`.
- Elevar `professor/admin` solo por bootstrap seguro o panel de administración cerrado.
- Fallar cerrado si `bcrypt` no está disponible en producción.

### 💡 Sugerencias avanzadas

- Migrar a auth institucional (`OIDC`, `SAML`, `Access + header validation`) y usar la DB local solo como fallback dev.

## 📁 `app_quantum_tutor.py`

### 🔴 Problemas críticos

- **El orquestador pesado se crea por sesión Streamlit, no como singleton real**  
  `app_quantum_tutor.py:216-219`  
  Está en `st.session_state`, no en `@st.cache_resource`.  
  Impacto: cada usuario crea su propio `QuantumTutorOrchestrator`, RAG, caches, semáforos y estado. Esto dispara memoria, cold starts y hace inefectivos controles globales.

- **Dashboard pedagógico visible a cualquier `professor`, incluso en host público**  
  `app_quantum_tutor.py:612-620`, `app_quantum_tutor.py:1862`  
  El dashboard exige rol, pero no host admin.  
  Impacto: combinado con auto-registro como `professor`, expone inteligencia pedagógica a terceros.

### 🟡 Problemas importantes

- **AdaptiveLearningEngine compartido globalmente sin locks**  
  `app_quantum_tutor.py:239-241`  
  Se cachea como recurso global, pero el engine muta estado file-backed sin sincronización.  
  Impacto: race conditions intra-proceso entre usuarios.

- **Monkeypatch global de `sys.stderr.flush` y `sys.stdout.flush` a no-op**  
  `app_quantum_tutor.py:8-17`  
  Impacto: observabilidad degradada, riesgo de comportamientos extraños en librerías y pérdida de diagnóstico real.

- **Archivo masivo y altamente acoplado**  
  Mezcla UI, auth, seguridad, diagnósticos, admin, orquestación, PWA, sidebar, analytics, learning journey y exportes en un único módulo.

- **El panel admin usa llamadas directas al engine en vez de pasar por un servicio controlado**  
  `app_quantum_tutor.py:454-460`, `app_quantum_tutor.py:1801`  
  Impacto: difumina fronteras entre capa UI y dominio.

### 🟢 Mejoras recomendadas

- Convertir el orquestador en `@st.cache_resource`.
- Mover dashboard docente a host admin o a un backend protegido separado.
- Dividir el archivo por dominios: `ui_chat`, `ui_learning`, `ui_admin`, `ui_security`.

### 💡 Sugerencias avanzadas

- Introducir una capa de presenters/view-models y desacoplar Streamlit del engine.

## 📁 `static_web/app.js`

### 🔴 Problemas críticos

- **XSS almacenado/reflejado por `marked.parse()` + `innerHTML`**  
  `static_web/app.js:302`, `static_web/app.js:313`  
  Cualquier contenido HTML en mensajes de usuario o respuesta del modelo termina inyectado en DOM sin sanitización.  
  Impacto: ejecución arbitraria en navegador, robo de `localStorage`, secuestro de sesión web, falsificación de UI.  
  Reproducción:
  1. Enviar `<img src=x onerror=alert(1)>`.
  2. El mensaje se renderiza vía `marked.parse(content)`.
  3. `msgDiv.innerHTML = innerHtml` ejecuta el payload.

- **Persistencia local de historial y estado de aprendizaje sin protección**  
  `static_web/app.js:21`, `static_web/app.js:27`, `static_web/app.js:90-123`  
  Impacto: privacidad débil en equipos compartidos.

### 🟡 Problemas importantes

- **Inconsistencia funcional entre chat público y learning journey**  
  `static_web/app.js:371-416`  
  El chat manda `user_id: getLearningStudentId()`, pero el backend público no usa ese ID de forma confiable para progreso adaptativo; luego el frontend refresca la ruta igual.  
  Impacto: la UI sugiere una adaptación que en realidad no se alimenta de la actividad de chat público.

- **El diagnóstico también usa `student_id` explícito por query param**  
  `static_web/app.js:71`, `static_web/app.js:169`  
  Agrava el problema de IDOR del backend.

- **HTML dinámico adicional inyectado con `innerHTML`**  
  `static_web/app.js:150`, `static_web/app.js:263`, `static_web/app.js:358`, `static_web/app.js:457`  
  Incluso si hoy la fuente es interna, el patrón sigue siendo frágil.

### 🟢 Mejoras recomendadas

- Sanitizar Markdown/HTML (`DOMPurify`).
- No guardar historial sensible por defecto en `localStorage`.
- No usar `student_id` controlado por cliente como identidad de backend.

### 💡 Sugerencias avanzadas

- Migrar la consola web a render seguro por nodos DOM, no por `innerHTML`.

## 📁 `static_web/index.html`

### 🟡 Problemas importantes

- **Dependencia de CDNs públicos sin SRI ni CSP**  
  `static_web/index.html:7-12`  
  Impacto: supply-chain risk en el frontend público.

### 🟢 Mejoras recomendadas

- Fijar versiones con `integrity` y política CSP.

## 📁 `static_web/styles.css`

### 🟢 Mejoras recomendadas

- No detecté riesgos funcionales críticos; es principalmente deuda de mantenibilidad visual.

## 📁 `adaptive_learning_engine.py`

### 🔴 Problemas críticos

- **Engine compartido y mutado sin ningún lock**  
  `adaptive_learning_engine.py:553-605`, `app_quantum_tutor.py:239-241`  
  El engine maneja estado mutable global y persiste múltiples archivos sin sincronización.  
  Impacto: condiciones de carrera, last-writer-wins, corrupción lógica del perfil del alumno.

- **GET analytics puede disparar optimización y escritura**  
  `adaptive_learning_engine.py:2167-2288`  
  Impacto: el observador modifica el sistema; confunde cohortes y experimentos.

### 🟡 Problemas importantes

- **Muestra experimental inflada por asignación, no por engagement real**  
  `adaptive_learning_engine.py:676-708`, `adaptive_learning_engine.py:1814-1825`  
  `sample_size = len(assignments)` cuenta estudiantes simplemente asignados, no estudiantes activos/completados.

- **`current_module` es heurístico y frágil**  
  `adaptive_learning_engine.py:992-1007`  
  Usa `last_recommended_node`, luego `lesson_history`, luego `chat_events`.  
  Impacto: cohortes y recomendaciones pueden agruparse por “última recomendación” más que por trabajo real.

- **`error_reduction_rate` es una métrica muy débil**  
  `adaptive_learning_engine.py:1030-1038`  
  Divide el historial en dos mitades temporales arbitrarias.  
  Impacto: resultados ruidosos con pocas observaciones.

- **`misconception_resolution_rate` sobreestima resolución**  
  `adaptive_learning_engine.py:1041-1047`  
  Usa `resolved_count / total_detected` sin validar profundidad, recaídas o estabilidad temporal.

- **Persistencia compartida con `LearningAnalytics` sobre el mismo `student_profile.json`**  
  `adaptive_learning_engine.py:1075-1103`, `learning_analytics.py`  
  Impacto: colisiones de escritura y modelos paralelos.

### 🟢 Mejoras recomendadas

- Añadir locking de proceso y/o backend transaccional real.
- Separar “lectura de insights” de “aplicación de optimizaciones”.
- Contar solo estudiantes activos/completados como muestra experimental.

### 💡 Sugerencias avanzadas

- Formalizar eventos ITS en un store append-only y derivar métricas desde ahí.

## 📁 `learning_ui_helpers.py`

### 🟡 Problemas importantes

- **El readiness experimenta sobre `sample_size` potencialmente sesgado**  
  `learning_ui_helpers.py:74-106`  
  Hereda el problema del engine y lo comunica como semáforo confiable.

- **Top issues usa la misconception dominante por cohorte, no distribución real completa**  
  `learning_ui_helpers.py:334-360`  
  Impacto: puede simplificar demasiado la lectura pedagógica.

### 🟢 Mejoras recomendadas

- Exponer intervalos de confianza y número de estudiantes activos.
- Mostrar “cohorte elegible” vs “cohorte asignada”.

## 📁 `learning_content.py`

### 🟡 Problemas importantes

- El motor depende de un banco bastante pequeño y mayormente estático.  
  Impacto: la personalización puede parecer rica en UI pero quedar pobre en variedad real.

### 🟢 Mejoras recomendadas

- Versionar banco de contenidos, hints y misconceptions por módulo.

## 📁 `learning_analytics.py`

### 🟡 Problemas importantes

- **Segundo modelo de alumno en paralelo al ITS principal**  
  `learning_analytics.py:42-78`, `api_quantum_tutor.py:642-656`  
  Mantiene `topics`, `struggle_index`, `wolfram_reliance`, `plateau` por heurísticas propias.  
  Impacto: el sistema tiene dos verdades pedagógicas divergentes.

- **Plateau threshold extremadamente bajo**  
  `learning_analytics.py:26`  
  Dos bloqueos consecutivos disparan plateau.  
  Impacto: sobre-intervención.

- **Persistencia sobre el mismo archivo de perfil que usa el adaptive engine**  
  `learning_analytics.py:6`, `learning_analytics.py:40`  
  Impacto: colisiones y sobrescrituras.

### 🟢 Mejoras recomendadas

- O integrar este modelo al engine central o retirarlo.

## 📁 `quantum_tutor_orchestrator.py`

### 🔴 Problemas críticos

- **Rotación de claves aborta prematuramente**  
  `quantum_tutor_orchestrator.py:381`  
  `break` ante `INVALID` debería ser `continue`.  
  Impacto: falsa degradación a fallback cuando aún quedan nodos sanos.

- **Backpressure parcial en streaming**  
  `quantum_tutor_orchestrator.py:1239-1249`  
  El `_provider_slot` se libera antes de consumir el stream.  
  Impacto: múltiples streams largos pueden coexistir fuera del control de concurrencia.

### 🟡 Problemas importantes

- **Timeout global duro de 15s**  
  `quantum_tutor_orchestrator.py:934`  
  Impacto: respuestas legítimas complejas pueden ser abortadas artificialmente.

- **Logs con contenido de usuario**  
  `quantum_tutor_orchestrator.py:1026`  
  `SCHED_DIFF` incluye `ctx.user_input`.  
  Impacto: fuga de prompts a logs.

- **Logging de prefijos de API key**  
  `quantum_tutor_orchestrator.py:306-317`, `quantum_tutor_orchestrator.py:387`  
  No es la clave completa, pero sí un identificador parcial sensible.

### 🟢 Mejoras recomendadas

- Corregir `break -> continue` en rotación.
- Mantener el semáforo durante toda la vida útil del stream.
- Parametrizar timeout por ruta/tier/modelo.

### 💡 Sugerencias avanzadas

- Unificar provider concurrency a nivel proceso, no por instancia de sesión Streamlit.

## 📁 `request_optimization.py`

### 🟡 Problemas importantes

- **Persistencia file-backed con lock solo intra-proceso**  
  `request_optimization.py:138`, `request_optimization.py:195-221`, `request_optimization.py:400`, `request_optimization.py:452-554`  
  Impacto: con varios workers el token bucket y response cache divergen o pisan datos.

- **Carga de SentenceTransformer en módulo adicional**  
  `request_optimization.py:406-407`  
  Impacto: más memoria duplicada, cold start más lento.

### 🟢 Mejoras recomendadas

- Mover rate limit/cache a Redis o SQLite transaccional.
- Reusar un embedding service compartido.

## 📁 `security_controls.py`

### 🟡 Problemas importantes

- **`inspect()` escribe estado aunque solo esté leyendo**  
  `security_controls.py:112-118`  
  Impacto: write amplification, más I/O y más superficie de race.

- **Locking solo intra-proceso**  
  `security_controls.py:78`, `security_controls.py:236`  
  Impacto: denylists y circuit breakers inconsistentes en multi-worker.

### 🟢 Mejoras recomendadas

- Separar lectura pura de normalización persistente.
- Mover estado crítico a backend transaccional.

## 📁 `security_audit.py`

### 🟡 Problemas importantes

- **Lee el archivo completo de eventos en memoria**  
  `security_audit.py:41-44`  
  Impacto: el panel admin puede degradar a medida que crece el log.

### 🟢 Mejoras recomendadas

- Leer tail eficiente, no `readlines()`.

## 📁 `security_admin.py`

### 🟡 Problemas importantes

- **Actor de auditoría fácilmente falsificable en CLI**  
  `security_admin.py:12-13`, `security_admin.py:49`, `security_admin.py:56`  
  Impacto: trazabilidad débil si múltiples operadores usan el mismo host.

### 🟢 Mejoras recomendadas

- Registrar UID real del sistema y exigir motivo en acciones manuales.

## 📁 `session_manager.py`

### 🟡 Problemas importantes

- **El método `cleanup()` no se usa en ninguna parte**  
  `session_manager.py:82-92`  
  Impacto: crecimiento de `_store` y `_locks` con sesiones abandonadas.

- **Cada sesión crea `LearningAnalytics` y `SemanticCache` propios apuntando a archivos compartidos**  
  `session_manager.py:95-110`  
  Impacto: colisiones de estado y más duplicación de memoria.

### 🟢 Mejoras recomendadas

- Programar limpieza real.
- Evitar crear caches/escritores file-backed por sesión.

## 📁 `semantic_cache.py`

### 🟡 Problemas importantes

- **Otra carga más de SentenceTransformer**  
  `semantic_cache.py:34-36`  
  Impacto: duplicación de memoria.

- **Sin límites de tamaño / pruning**  
  La caché crece de forma más libre que `LLMResponseCache`.

### 🟢 Mejoras recomendadas

- Consolidar con `LLMResponseCache` o eliminar este módulo legacy.

## 📁 `rag_engine.py`

### 🔴 Problemas críticos

- **Uso de `pickle.load` sobre cache en disco**  
  `rag_engine.py:207-208`  
  Impacto: ejecución arbitraria si el archivo cache es manipulado.

### 🟡 Problemas importantes

- **Monkeypatch global de `sys.stderr.flush`**  
  `rag_engine.py:21-33`  
  Impacto: observabilidad y comportamiento global inciertos.

- **Carga pesada del encoder durante ingesta**  
  `rag_engine.py:157-163`, `rag_engine.py:374`  
  Impacto: cold start costoso.

- **Persistencia cache pickle no verificada ni versionada**  
  `rag_engine.py:205-255`  
  Impacto: incompatibilidades silenciosas entre versiones del vector store.

### 🟢 Mejoras recomendadas

- Sustituir pickle por formato seguro.
- Versionar el índice RAG y validar schema al cargar.

## 📁 `local_symbolic_engine.py`

### 🟡 Problemas importantes

- Las reglas de parsing son útiles pero frágiles para expresiones no triviales; hay riesgo de falsos positivos por regex permisivas.

### 🟢 Mejoras recomendadas

- Añadir tests de regresión con expresiones ambiguas o mal formadas.

## 📁 `multimodal_vision_parser.py`

### 🔴 Problemas críticos

- **Mock engañoso en producción**  
  `multimodal_vision_parser.py:37-39`, `multimodal_vision_parser.py:74-77`, `multimodal_vision_parser.py:79-114`  
  Si falla el proveedor, el parser devuelve pasos simulados plausibles.  
  Impacto: feedback visual falso, pérdida de confianza y daño pedagógico.

### 🟡 Problemas importantes

- No valida suficientemente que la salida del modelo sea JSON bien formado con schema esperado.

### 🟢 Mejoras recomendadas

- Devolver estado degradado explícito (`vision_status=DEGRADED`) en vez de mock.

## 📁 `deterministic_responder.py`

### 🟢 Mejoras recomendadas

- Sin fallos críticos claros; el mayor riesgo es cobertura limitada y reglas demasiado específicas.

## 📁 `reference_visualizer.py`

### 🟡 Problemas importantes

- Usa `fitz` sobre PDFs locales en runtime; útil, pero conviene aislar esto de la request path pública si la carga crece.

### 🟢 Mejoras recomendadas

- Pre-renderizar páginas o cachear por lotes en despliegue real.

## 📁 `relational_engine.py`

### 🟡 Problemas importantes

- Modelo relacional interesante pero heurístico y no calibrado; hoy funciona más como feature experimental que como componente defendible de aprendizaje.

### 🟢 Mejoras recomendadas

- Marcarlo explícitamente como experimental o someterlo a validación offline.

## 📁 `quantum_tutor_paths.py`

### 🔴 Problemas críticos

- **“Atomic write” no segura entre procesos**  
  `quantum_tutor_paths.py:82-88`, `quantum_tutor_paths.py:94-97`, `quantum_tutor_paths.py:100-106`  
  Usa siempre el mismo `*.tmp` por destino. Con dos escritores concurrentes hay carrera sobre el mismo archivo temporal.  
  Impacto: corrupción, `FileNotFoundError`, estado truncado o last-writer-wins silencioso.

### 🟡 Problemas importantes

- Centraliza correctamente rutas, pero toda la arquitectura depende de archivos JSON/pickle locales como si fueran store transaccional.

### 🟢 Mejoras recomendadas

- Usar temporales únicos + fsync + file locks, o mover estado a Redis/Postgres.

## 📁 `quantum_tutor_runtime.py`

### 🟢 Mejoras recomendadas

- Sin riesgo funcional relevante; solo conviene limpiar mojibake heredado y alinear branding/versionado real.

## 📁 `deployment/nginx/quantum_tutor.conf`

### 🟡 Problemas importantes

- **Rate limit de borde solo para `/api/chat` y `/api/vision`**  
  `deployment/nginx/quantum_tutor.conf:146-176`  
  Los endpoints `/api/learning-*` quedan fuera del rate limit de edge.  
  Impacto: analytics/exportes sin auth y además sin rate limit.

### 🟢 Mejoras recomendadas

- Aplicar política explícita a `/api/learning-`.

## 📁 `deployment/scripts/deploy_quantumtutor_ubuntu.sh`

### 🟡 Problemas importantes

- **`rsync -a --delete` sobre el directorio activo**  
  `deployment/scripts/deploy_quantumtutor_ubuntu.sh:82`  
  Impacto: si `QT_REPO_SRC` apunta mal, el despliegue borra contenido productivo.

- El script automatiza `cloudflared tunnel route dns` directamente. Útil, pero agresivo para entornos con control de cambios más rígido.

### 🟢 Mejoras recomendadas

- Añadir `--dry-run` y confirmación sobre delete.

## 📁 `deployment/scripts/smoke_check.py`

### 🟡 Problemas importantes

- **No verifica que `admin.quantumtutor.cl` esté realmente protegido por Access**  
  `deployment/scripts/smoke_check.py:16-74`  
  Impacto: el despliegue puede pasar en verde con el admin expuesto públicamente.

### 🟢 Mejoras recomendadas

- Añadir chequeo explícito del hostname admin esperando challenge/redirect de Access.

## 📁 `deployment/systemd/quantum-tutor-api.service`

### 🟢 Mejoras recomendadas

- Está razonablemente bien endurecido, pero no resuelve los problemas de concurrencia file-backed del propio runtime.

## 📁 `test_learning_api_endpoints.py`

### 🔴 Problemas críticos

- **La suite codifica el comportamiento inseguro actual**  
  `test_learning_api_endpoints.py:30-183`  
  Todos los endpoints se prueban con `student_id` arbitrario, sin auth.  
  Impacto: la suite hoy normaliza un patrón vulnerable.

### 🟡 Problemas importantes

- No hay tests de ownership, authz ni negative cases de acceso cruzado.

## 📁 `test_api_robustness.py`

### 🟡 Problemas importantes

- Buena cobertura de `chat` y edge guards, pero no cubre que los endpoints de learning deban estar protegidos.

## 📁 `test_auth_hardening.py`

### 🟡 Problemas importantes

- No detecta el auto-registro como `professor`.

## 📁 `test_usage_controls.py`

### 🟡 Problemas importantes

- Cubre bucket/circuit breaker, pero no la liberación prematura del semáforo durante el streaming real.

## 📁 `test_adaptive_learning_engine.py`

### 🟡 Problemas importantes

- Valida que el engine produzca insights, pero no cuestiona la calidad metodológica de la muestra ni el side effect de `get_learning_insights(apply_optimization=True)`.

## 📁 `test_learning_ui_helpers.py`

### 🟡 Problemas importantes

- Cubre formateo de dashboard, no validez causal/pedagógica de las métricas.

## 📁 `test_learning_ui_assets.py`

### 🟢 Mejoras recomendadas

- Tests de presencia/contrato visual útiles, pero de bajo poder para riesgos reales.

## 📁 `test_deployment_assets.py`

### 🟡 Problemas importantes

- Verifica assets, no comportamiento real de Access ni de host protection.

## Riesgos globales antes de producción

1. **Data exposure / unauthorized writes** por endpoints ITS sin auth y por bypass de `student_id`.
2. **Escalada funcional de rol** por auto-registro como `professor`.
3. **XSS público** en consola web.
4. **Corrupción de estado** por stores file-backed, engine global sin locks y “atomic writes” no seguras entre procesos.
5. **Desalineación de modelos pedagógicos** (`LearningAnalytics` legacy vs `AdaptiveLearningEngine`).
6. **Analítica experimental no causalmente robusta** por sample inflation y side effects en lecturas.
7. **Backpressure no fiable en streams** y controles globales duplicados por sesión.
8. **Visión multimodal deshonesta en degradación** al devolver mock como si fuese análisis real.

## Evaluación global

### 1. Riesgos críticos antes de producción

- Sí, existen riesgos ocultos suficientes para romper:
  - privacidad y gobernanza de datos
  - estabilidad multiusuario
  - confianza pedagógica
  - seguridad del frontend

### 2. Nivel de calidad (0–10)

**5.6 / 10**

Razón:

- 8.5/10 en ambición funcional y breadth.
- 4/10 en hardening real de identidad, estado compartido y seguridad frontend.

### 3. Deuda técnica estimada

**Alta**.  
Corrección mínima para despliegue serio: **3 a 5 semanas-persona**.  
Refactor correcto para operación institucional: **6 a 10 semanas-persona**.

### 4. Probabilidad de fallos en producción

**Media-alta** en single-host con pocos usuarios.  
**Alta** en multiusuario o entorno institucional.

Estimación cualitativa:

- fallo de seguridad / exposición: alta
- inconsistencia de estado: alta
- degradación de performance: media-alta
- regresión pedagógica silenciosa: media

### 5. Evaluación del ITS (pedagógica real)

**Potencial pedagógico: alto.**  
**Confiabilidad pedagógica operativa actual: media.**

Fortalezas:

- mastery learning
- spaced repetition
- knowledge graph
- adaptive difficulty
- cohortes y analítica

Debilidades reales:

- dos modelos pedagógicos coexistiendo
- métricas experimentales todavía sesgadas
- insights que pueden modificar el sistema al consultarse
- feedback visual falso en degradación

### 6. Recomendaciones prioritarias (TOP 10)

1. Bloquear inmediatamente el bypass de `student_id` y exigir ownership/authz en `/api/learning-*`.
2. Eliminar auto-registro como `professor`; dejar solo `student`.
3. Sanitizar la consola web (`DOMPurify`) y eliminar `innerHTML` inseguro.
4. Cambiar `GET /api/learning-insights` a lectura pura; mover optimización a `POST`.
5. Reemplazar estado file-backed crítico por Redis/Postgres o, como mínimo, file locks reales + tmp únicos.
6. Convertir el orquestador Streamlit en singleton real compartido y revisar límites globales.
7. Corregir `rotate_client()` (`break` -> `continue`) y mantener el semáforo durante todo el streaming.
8. Retirar el mock engañoso de visión; degradar honestamente con estado explícito.
9. Unificar `LearningAnalytics` y `AdaptiveLearningEngine` en un único modelo de estudiante.
10. Reescribir la suite de seguridad/learning para que falle ante acceso cruzado, roles indebidos y side effects en lectura.

## Conclusión final

Quantum Tutor ya tiene núcleo de producto serio, pero **todavía no tiene el nivel de seguridad, consistencia de estado ni disciplina experimental que exige una puesta en producción real**.

Hoy lo defendería como:

- **muy prometedor como sistema ITS en desarrollo avanzado**
- **no listo aún para despliegue institucional público**

La decisión correcta no es “agregar más features”.  
La decisión correcta es **cerrar seguridad, identidad, persistencia y causalidad analítica** antes de exponerlo a usuarios reales.
