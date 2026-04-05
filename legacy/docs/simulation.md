# 🚀 Simulación de Interacción: El Caso del Pozo Infinito
Escenario: Un estudiante intenta resolver un problema sobre la probabilidad en el primer estado excitado de un pozo de potencial infinito de ancho L.

## 1. Entrada del Usuario (Estudiante)
"Hola, estoy intentando calcular la probabilidad de encontrar al electrón en el centro del pozo (entre L/4 y 3L/4) para el nivel n=2, pero me sale que es 0.5 y mi libro dice que es diferente. ¿Me ayudas?"

## 2. Ejecución del Sistema (Proceso Interno)
| Fase | Acción Técnica | Resultado del Sistema |
| :--- | :--- | :--- |
| RAG Retrieval | Busca en "Semana 2 - Mecánica Ondulatoria.pdf" | Recupera: $\psi_n(x) = \sqrt{\frac{2}{L}} \sin(\frac{n\pi x}{L})$ |
| Razonamiento (CoT) | Identifica que el alumno aplicó la lógica de n=1 o una intuición clásica. | Detecta que para n=2, hay un nodo en L/2. |
| Wolfram Call | `Integrate[(Sqrt[2/L] Sin[2 Pi x / L])^2, {x, L/4, 3L/4}]` | Resultado: 0.5 (El alumno en realidad tenía razón matemáticamente, pero duda de su intuición física). |
| Estrategia | Socrática / Verificación. | Confirmar el cálculo y explicar la física detrás del "0.5". |

## 3. Respuesta del QuantumTutor (Output)
"Hola. Es una excelente observación. Vamos a analizar por qué tu resultado de 0.5 es, de hecho, matemáticamente correcto, aunque te genere dudas.

Según tus apuntes del curso [Doc: Semana 2, Pág. 8], la función de onda para n=2 es:

$$\psi_2(x) = \sqrt{\frac{2}{L}} \sin(\frac{2\pi x}{L})$$

He verificado la integral de la densidad de probabilidad $P = \int_{L/4}^{3L/4} |\psi_2(x)|^2 dx$ y, efectivamente, el valor es 0.5.

Para que lo comprendas visualmente:
En el nivel n=2, tenemos un nodo (probabilidad cero) justo en x=L/2.

¿Qué crees que pasaría con esa probabilidad si el estado fuera el fundamental (n=1)?

¿Esperarías que la probabilidad de estar en el centro aumentara o disminuyera respecto a tu 0.5?

Comparemos esto con la gráfica de $|\psi|^2$ que acabo de procesar..."
