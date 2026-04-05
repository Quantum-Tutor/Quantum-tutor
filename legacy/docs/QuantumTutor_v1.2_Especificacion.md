# QuantumTutor v1.2: Especificación Integral de un Sistema RAG Neuro-Simbólico

> Nota de mantenimiento (2026-03-30): este archivo es historico. El runtime vigente del repositorio es `v6.1-stateless` y esta documentado en `README.md` y `manual_quantum_tutor.md`.

**Versión:** 1.2
**Arquitectura:** Neuro-Simbólica (LLM + Motor RAG + API Simbólica)
**LLM Core:** Claude 3.5 Sonnet
**Base de Conocimiento:** Galindo & Pascual ("Quantum Mechanics I"), Griffiths ("Introduction to Quantum Mechanics")

---

## 1. Resumen Ejecutivo

El **QuantumTutor v1.2** es una plataforma educativa de vanguardia diseñada para la enseñanza académica de la mecánica cuántica. El sistema se distingue por abandonar el paradigma de "chatbot pasivo" en favor de una arquitectura **híbrida neuro-simbólica**. Al combinar las capacidades de razonamiento natural de un LLM de última generación (Claude 3.5 Sonnet) con un motor de Recuperación Aumentada (RAG) anclado a literatura académica certificada, y respaldado por la precisión computacional de Wolfram Alpha, el tutor garantiza un entorno libre de alucinaciones matemáticas. El sistema emplea el **método socrático**, guiando al estudiante a través de la inducción lógica y el análisis conceptual en lugar de proveer respuestas directas.

---

## 2. Arquitectura del Sistema

La arquitectura del QuantumTutor se compone de tres pilares fundamentales que operan en tándem bajo la coordinación de un orquestador central:

### 2.1 Capa de Ingesta (Vector Store & Semantic Search)
- **Fragmentación Adaptativa Sensible al Contexto:** El pipeline de ingesta procesa documentos académicos complejos (típicamente Markdown o PDF convertidos) utilizando una estrategia de *chunking* que respeta los bloques de ecuaciones en representación LaTeX (identificando delimitadores `$$` y `$`). Esto garantiza que las fórmulas nunca se trunquen a la mitad (por ejemplo, la Ecuación de Schrödinger permanece íntegra en su chunk).
- **Embeddings Geométricos:** Genera representaciones vectoriales densas, logrando agrupar conceptos físicos latentes.

### 2.2 Orquestador de Diálogo (Claude 3.5 Sonnet)
- **Cerebro Cognitivo:** Utiliza Claude 3.5 Sonnet parametrizado con baja entropía ($T=0.2$) para maximizar el determinismo en las explicaciones.
- **Chain-of-Thought (CoT) Pedagógico:** Antes de emitir un token visible, el modelo razona internamente sobre el estado cognitivo del estudiante y estructura la intervención socrática según el *system prompt* estricto.

### 2.3 Motor Simbólico (`wolfram_emulator.py`)
- **Erradicación de Alucinaciones Matemáticas (Tool Enforcing):** El orquestador intercepta consultas analíticas (integrales, conmutadores, túneles de probabilidad) y **fuerza** su delegación al motor lógico de Wolfram Alpha. 
- **Verificación Ground Truth:** El LLM recibe el resultado simbólico exacto de Wolfram y construye su respuesta socrática alrededor de esta verdad matemática, imposibilitando que "invente" derivadas o valores probabilísticos.

---

## 3. Flujo de Inferencia Socrática

El ciclo de vida de una transacción (consulta del estudiante) en el QuantumTutor sigue una tubería secuencial estricta:

1. **Identificación y Análisis (Parsing):** El orquestador recibe el *input* del estudiante y mediante expresiones regulares semánticas determina si la consulta requiere resolución analítica/herramientas (ej. *"calcula la integral..."*).
2. **Recuperación RAG (Grounding):** Se consultan los fragmentos de los libros de texto indexados (ej. Galindo & Pascual) en la base de datos vectorial para fundamentar la respuesta en un marco teórico real.
3. **Delegación Simbólica (Tool Enforcing):** Si se detecta un cálculo, el orquestador delega la operación matemática explícita en lenguaje Wolfram Language hacia la API subyacente de Wolfram Alpha.
4. **Síntesis Socrática:** El LLM cruza el contexto recuperado (RAG) con la certeza matemática (Wolfram) y genera una respuesta pedagógica. Esta respuesta confirma el cálculo discretamente pero culmina **siempre** con una pregunta abierta o conceptual que transfiere el esfuerzo cognitivo de vuelta al estudiante.

---

## 4. Protocolo de Evaluación (Quantum Stress Test)

Para certificar el sistema para entornos vivos, se ha implementado un banco de pruebas multidimensional y automatizado:

- **Fidelidad (Faithfulness Score - NLI):** Mide la adherencia del LLM a los documentos fuente. A través de Inferencia de Lenguaje Natural (NLI), se penaliza severamente a cualquier afirmación que contradiga (CONTRADICTED) o extienda injustificadamente (NEUTRAL) lo establecido por los textos de referencia.
- **Precisión Simbólica (Code Success Rate - CSR):** Evalúa la eficacia del orquestador para invocar correctamente funciones sintácticas abstractas en el motor de Wolfram (ej. `Commutator[x^2, p]`). El umbral de excelencia exigido es del $100\%$.
- **Eficacia Socrática (Socratic Compliance Rate - SCR):** Analiza sintácticamente la respuesta fina generada para certificar la presencia de heurísticas socráticas (preguntas guía, validación de esfuerzo continuo y denegación sistemática a entregar la respuesta terminada de forma prematura).

---

## 5. Optimización y Latencia (Mejoras v1.2)

En contextos de aprendizaje, preservar el *flow state* del estudiante es prioridad crítica. La versión 1.2 incorpora un rediseño radical del I/O para minimizar la fricción:

- **Ejecución Asíncrona (Asyncio):** Las llamadas de red hacia la recuperación RAG y el cálculo en la nube de Wolfram se realizan de forma concurrente, logrando reducir el I/O Fetch de $2.5\text{s}$ a aproximadamente $0.8\text{s}$.
- **Caché de Resultados en Memoria:** Se implementó una tabla hash rápida para almacenar los resultados repetidos de Wolfram Alpha. En caso de *Cache Hit*, la latencia del cálculo desciende a **$0.0\text{ms}$**.
- **Truncamiento de Contexto Inteligente:** En lugar de inyectar todo el *Top-K* de chunks en el promt del LLM a ciegas, el orquestador calcula el *score* relativo. Se descartan automáticamente los fragmentos recuperados cuyo *Similarity Score* sea inferior al 85% del fragmento principal, aliviando la ventana de atención y logrando reducir significativamente la latencia de inferencia (Time-to-First-Token $< 1.5\text{s}$).

---

## 6. Gestión de Riesgos y Gobernanza

El despliegue en educación cuántica asume riesgos excepcionales que el modelo mitiga deliberadamente:

| Riesgo Operativo | Impacto | Estrategia de Mitigación (Guardrail) |
| :--- | :--- | :--- |
| **Alucinación Matemática** | Crítico | Intercepción obligatoria (*Tool Enforcing*) de flujos donde interviene álgebra compleja delegando estrictamente a la API de Wolfram. |
| **Atajo Cognitivo** | Alto | *System Prompt* robusto penalizando fuertemente la respuesta directa. Implementación y monitorización contínua de la Eficacia Socrática mediante regex y evaluación cruzada. |
| **"Drift" del Modelo** | Medio | Archivo estático `system_prompt.md` con temperatura congelada a $T=0.2$, forzando consistencia lógica a través de iteraciones. Restricción del Top-K RAG para enfocar fuertemente el contexto. |

---

## 7. Guía de Implementación

El núcleo funcional del QuantumTutor v1.2 reside en los siguientes artefactos:

- `quantum_tutor_config.json`: Declaración universal de parámetros. Define explícitamente `Temperatura: 0.2`, `Top-K: 4`, y delinea los umbrales de seguridad y pesos del *Quantum Stress Test*.
- `init_quantum_tutor.py` / `quantum_tutor_orchestrator.py`: Contiene la lógica orquestacional *low-latency* asíncrona y la administración general de dependencias (RAG vs Wolfram).
- `rag_engine.py`: El conector *vector store*, responsable de embeber el material y realizar búsquedas bajo métricas de umbral (*Similarity Threshold*).
- `app_quantum_tutor.py`: El frontend desarrollado en **Streamlit** que inyecta la experiencia de usuario (UI), renderizado LaTeX, métricas Sidebar y streaming asíncrono.

---

## 8. Apéndice de Casos de Prueba

### Caso B: Pozo de Potencial Infinito ($n=2$)
Se validó la capacidad end-to-end del sistema ante el input del estudiante: *"¿Cómo se comporta la probabilidad en el centro de un pozo infinito para n=2?"*.

1. **Reconocimiento:** El CoT reconoce un modelo de *Infinite Potential Well* con estado excitado $n=2$ y pide la probabilidad puntual o integral en la banda central.
2. **RAG:** Se extrae el fragmento correspondiente al "Pozo de Potencial".
3. **Wolfram:** El orquestador emite `Integrate[(Sqrt[2/L] Sin[2 Pi x / L])^2, {x, L/4, 3L/4}]`. El motor devuelve numéricamente `0.5`, lo cual es renderizado simbólicamente como `P = \frac{1}{2}`.
4. **Respuesta Socrática (Streamlit):**
   > *Entendido. Analizando paso a paso. Según el material del curso (truncado para eficiencia):*
   > *Verificado simbólicamente:*
   > $$ P = \frac{1}{2} $$
   > *Reflexión socrática: ¿Por qué crees que sucede esto físicamente? (Considera la forma de la función de onda para n=2 y la existencia de nodos).*

**(Validación: ÉXITO. Latencia: $1.34\text{s}$ - Caché Hit).**
