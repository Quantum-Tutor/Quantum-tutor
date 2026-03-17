# ⚛️ QuantumTutor v1.0
**Arquitectura Neuro-Simbólica para la Educación en Física Cuántica**

![Version](https://img.shields.io/badge/version-1.0-blue)
![Architecture](https://img.shields.io/badge/architecture-Neuro--Symbolic_RAG-orange)
![LLM](https://img.shields.io/badge/LLM-Claude_3.5_Sonnet-green)
![Math Engine](https://img.shields.io/badge/Math_Engine-Wolfram_Alpha-red)

## 📋 Tabla de Contenidos
1. [Introducción y Visión General](#1-introducción-y-visión-general)
2. [Arquitectura del Sistema](#2-arquitectura-del-sistema)
3. [Metodología de Evaluación](#3-metodología-de-evaluación-protocolo-científico)
4. [Guía de Configuración e Implementación](#4-guía-de-configuración-e-implementación)
5. [Gestión de Riesgos y Gobernanza](#5-gestión-de-riesgos-y-gobernanza)
6. [Escalabilidad (v2.0)](#6-escalabilidad-hacia-el-tutor-de-próxima-generación-v20)
7. [Apéndice: Casos de Prueba Estándar](#7-apéndice-casos-de-prueba-estándar)

---

## 1. Introducción y Visión General
El **QuantumTutor** no es un chatbot conversacional estándar. Es un sistema de Inteligencia Artificial híbrido y avanzado, diseñado específicamente para la enseñanza de física a nivel universitario. Para superar las limitaciones inherentes de los Modelos de Lenguaje Grande (LLMs) en matemáticas complejas, este sistema combina:

* **Capacidad Lingüística:** Para ejecutar un diálogo socrático, empatizar con la frustración del estudiante y adaptar la pedagogía.
* **Recuperación de Información (RAG):** Para garantizar el anclaje (*grounding*) estricto en el material oficial del curso (apuntes, libros de texto, papers).
* **Razonamiento Simbólico (Wolfram Alpha):** Para garantizar una precisión matemática absoluta, delegando la resolución de integrales, derivadas y álgebra de operadores a un motor computacional determinista, erradicando así las alucinaciones numéricas.

## 2. Arquitectura del Sistema
El sistema opera bajo un flujo de **Generación Aumentada por Recuperación (RAG) con Capa de Herramientas (Tool Calling)**.

### Componentes Core:
* **Capa de Ingesta (`ingest.py`):** Procesa los documentos PDF de la universidad utilizando *Recursive Character Splitting* adaptado a Markdown. Esto asegura que los bloques semánticos y las fórmulas en LaTeX no se fragmenten durante la vectorización en la base de datos (Pinecone/Milvus).
* **Orquestador de Diálogo:** El "cerebro" lingüístico impulsado por un LLM de razonamiento avanzado (como Claude 3.5 Sonnet o GPT-4o), parametrizado a través del archivo `quantum_tutor_config.json`.
* **Motor Simbólico (`wolfram_emulator.py`):** Una integración directa vía API con Wolfram Alpha. El LLM traduce la física a Wolfram Language para resolver operaciones críticas como la normalización de funciones de onda o la evaluación de valores esperados.

## 3. Metodología de Evaluación (Protocolo Científico)
Para validar el sistema antes de su despliegue frente a estudiantes reales, implementamos un protocolo de evaluación riguroso denominado **"The Quantum Stress Test"**.

### Dimensiones de Calidad:
* **Fidelidad (Faithfulness):** Medida por la métrica de Hechos Verificados sobre Hechos Totales, asegurando que el LLM no invente conceptos fuera del material de estudio.
* **Precisión Simbólica:** Evaluación del *Code Success Rate* (CSR); la capacidad del LLM para generar código de Wolfram válido y comparar sus resultados con el *Ground Truth* algebraico.
* **Eficacia Socrática:** Medición del ratio de retención del estudiante en la conversación. El modelo se evalúa positivamente si logra que el alumno deduzca la respuesta en lugar de entregarle la solución terminada.

## 4. Guía de Configuración e Implementación

### Estructura de Archivos en el Entorno (`/scratch`)
* `system_prompt.md`: Define la personalidad socrática, las reglas de interacción, el uso obligatorio de LaTeX para matemáticas y las restricciones operativas.
* `quantum_tutor_config.json`: Archivo de orquestación que define parámetros como la temperatura (fijada en 0.2 para mayor determinismo), los modelos de embeddings y los umbrales de similitud del RAG.
* `wolfram_emulator.py`: Simulador local para realizar pruebas de integración y validar las llamadas a funciones matemáticas (*Tool Calling*).
* `init_quantum_tutor.py`: El script principal de arranque que inicializa los agentes y conecta la base de datos vectorial con el LLM.
* `ingest.py`: Script para cargar los contenidos del curso a la Vector DB.

### Ingeniería de Prompts
El sistema utiliza técnicas de **Few-Shot Prompting** y **Chain-of-Thought (CoT)**. Ante cada consulta, el flujo interno de razonamiento exige:
1. Identificar las variables conocidas e incógnitas del problema.
2. Recuperar la teoría aplicable desde el RAG.
3. Traducir la operación a código de Wolfram (si requiere cálculo).
4. Formular una pregunta guía socrática para el estudiante.

## 5. Gestión de Riesgos y Gobernanza

| Riesgo Detectado | Mecanismo de Mitigación Implementado |
| :--- | :--- |
| **Alucinación Matemática** | Desvío obligatorio de cálculos complejos a Wolfram Alpha mediante *Tool Enforcing*. |
| **Atajo Cognitivo** | Protocolo Socrático: El sistema tiene prohibido algorítmicamente dar la respuesta final numérica o algebraica en el primer turno de interacción. |
| **Privacidad de Datos** | Rutinas de anonimización (eliminación de PII) antes de enviar las consultas a APIs externas (LLM y Wolfram). |
| **Sesgo Interpretativo** | Configuración de neutralidad teórica estricta (explicar diferentes modelos sin favorecer ninguno a menos que aplique al currículo). |

## 6. Escalabilidad: Hacia el Tutor de Próxima Generación (v2.0)
Diseñado con una arquitectura modular, el sistema está preparado para integrar futuras capacidades:
* **Multimodalidad Avanzada:** Capacidad de procesar imágenes de los cuadernos de los alumnos mediante visión computacional y OCR especializado en fórmulas matemáticas, para detectar errores exactos en derivaciones manuales.
* **Razonamiento Simbólico Local:** Sustitución de la API en la nube por librerías locales de Python como SymPy en un entorno *sandbox*, reduciendo la latencia y la dependencia de servicios externos.
* **Analítica del Aprendizaje (Dashboard):** Un panel de control para el profesorado que, mediante *clustering* temático, identifique qué conceptos específicos (ej. espín, efecto túnel) están generando la mayor tasa de error o consultas en el grupo.

## 7. Apéndice: Casos de Prueba Estándar

### Caso A: Normalización de Función de Onda
* **Input del Alumno:** "¿Cómo normalizo una función de onda?"
* **Acción del Sistema:**
  1. Recupera del RAG la definición: la integral de la densidad de probabilidad debe ser la unidad.
  2. Explica el concepto físico detrás de la constante de normalización.
  3. **Salida Socrática:** "Para aplicar esto, ¿qué función de onda específica tienes en tu problema para que planteemos juntos los límites de integración?"

### Caso B: El Pozo de Potencial Infinito (Error de Intuición)
* **Input del Alumno:** "Calculé la probabilidad para n=2 en el centro del pozo y me da 0.5, pero creo que está mal."
* **Acción del Sistema:**
  1. El LLM deduce internamente la función correspondiente al nivel cuántico indicado.
  2. Llama a Wolfram Alpha para calcular la integral exacta en el intervalo central.
  3. Confirma que el resultado matemático del alumno (0.5) es correcto.
  4. **Salida Socrática:** Explica la existencia de un nodo en el centro para el primer estado excitado y guía al alumno a entender por qué su cálculo es correcto a pesar de contradecir su intuición clásica.
