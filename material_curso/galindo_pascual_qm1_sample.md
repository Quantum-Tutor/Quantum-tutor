# Quantum Mechanics I — Galindo & Pascual (Springer, 1990)
# Contenido representativo para prueba de ingesta RAG
# Basado en la estructura del texto clásico de mecánica cuántica

## Capítulo 1: Fundamentos de la Mecánica Cuántica

### 1.1 Origen Histórico

La mecánica cuántica surge de la imposibilidad de explicar ciertos fenómenos experimentales dentro del marco de la física clásica. Los experimentos clave incluyen:

- **Radiación del cuerpo negro** (Planck, 1900): La energía se intercambia en cuantos $E = h\nu$
- **Efecto fotoeléctrico** (Einstein, 1905): La luz se comporta como partículas con energía $E = h\nu$
- **Espectro del hidrógeno** (Bohr, 1913): Los niveles de energía están cuantizados según $E_n = -\frac{13.6 \text{ eV}}{n^2}$

### 1.2 Postulados de la Mecánica Cuántica

**Postulado 1 (Estado):** El estado de un sistema cuántico se describe completamente por un vector de estado $|\psi\rangle$ perteneciente a un espacio de Hilbert $\mathcal{H}$.

**Postulado 2 (Observables):** Toda magnitud física observable se representa por un operador hermítico $\hat{A}$ actuando sobre $\mathcal{H}$.

**Postulado 3 (Medida):** El resultado de una medición del observable $\hat{A}$ solo puede ser uno de sus autovalores $a_n$, donde:

$$\hat{A}|a_n\rangle = a_n|a_n\rangle$$

**Postulado 4 (Probabilidad de Born):** La probabilidad de obtener el autovalor $a_n$ al medir $\hat{A}$ en el estado $|\psi\rangle$ es:

$$P(a_n) = |\langle a_n|\psi\rangle|^2$$

**Postulado 5 (Evolución temporal):** La evolución temporal del estado viene dada por la ecuación de Schrödinger:

$$i\hbar\frac{\partial}{\partial t}|\psi(t)\rangle = \hat{H}|\psi(t)\rangle$$

### 1.3 Espacios de Hilbert

Un espacio de Hilbert $\mathcal{H}$ es un espacio vectorial completo con producto interno $\langle\phi|\psi\rangle$ que satisface:

1. **Linealidad:** $\langle\phi|\alpha\psi_1 + \beta\psi_2\rangle = \alpha\langle\phi|\psi_1\rangle + \beta\langle\phi|\psi_2\rangle$
2. **Hermiticidad:** $\langle\phi|\psi\rangle = \overline{\langle\psi|\phi\rangle}$
3. **Positividad:** $\langle\psi|\psi\rangle \geq 0$, con igualdad sii $|\psi\rangle = 0$

La norma se define como $\|\psi\| = \sqrt{\langle\psi|\psi\rangle}$.

## Capítulo 2: La Ecuación de Schrödinger

### 2.1 Ecuación de Schrödinger Independiente del Tiempo

Para estados estacionarios $\psi(x,t) = \phi(x)e^{-iEt/\hbar}$, la ecuación de Schrödinger se reduce a:

$$-\frac{\hbar^2}{2m}\frac{d^2\phi}{dx^2} + V(x)\phi(x) = E\phi(x)$$

o equivalentemente:

$$\hat{H}\phi = E\phi$$

donde el hamiltoniano es $\hat{H} = \frac{\hat{p}^2}{2m} + V(\hat{x})$.

### 2.2 El Pozo de Potencial Infinito

Consideremos una partícula confinada en una caja unidimensional de longitud $L$:

$$V(x) = \begin{cases} 0 & \text{si } 0 < x < L \\ \infty & \text{en otro caso} \end{cases}$$

**Condiciones de frontera:** $\psi(0) = \psi(L) = 0$

La solución general dentro del pozo es $\psi(x) = A\sin(kx) + B\cos(kx)$.

Aplicando $\psi(0) = 0$: $B = 0$.
Aplicando $\psi(L) = 0$: $\sin(kL) = 0 \Rightarrow k_n = \frac{n\pi}{L}$, con $n = 1, 2, 3, ...$

#### Funciones de onda normalizadas

$$\psi_n(x) = \sqrt{\frac{2}{L}}\sin\left(\frac{n\pi x}{L}\right)$$

#### Niveles de energía cuantizados

$$E_n = \frac{n^2\pi^2\hbar^2}{2mL^2} = n^2 E_1$$

donde $E_1 = \frac{\pi^2\hbar^2}{2mL^2}$ es la energía del estado fundamental.

#### Propiedades importantes

- **Energía de punto cero:** $E_1 > 0$ (la partícula nunca está en reposo)
- **Nodos:** La función $\psi_n$ tiene $n-1$ nodos interiores
- **Ortogonalidad:** $\int_0^L \psi_m(x)\psi_n(x)\,dx = \delta_{mn}$
- **Completitud:** $\sum_{n=1}^{\infty} \psi_n(x)\psi_n(x') = \delta(x-x')$

### 2.3 Valores Esperados y Probabilidades

El valor esperado de un observable $\hat{A}$ en el estado $\psi_n$ es:

$$\langle\hat{A}\rangle_n = \int_0^L \psi_n^*(x)\hat{A}\psi_n(x)\,dx$$

Para la posición: $\langle x\rangle_n = \frac{L}{2}$ (por simetría, para todo $n$).

Para $x^2$:

$$\langle x^2\rangle_n = \frac{L^2}{3} - \frac{L^2}{2n^2\pi^2}$$

La probabilidad de encontrar la partícula en la región $[a,b]$ es:

$$P(a \leq x \leq b) = \int_a^b |\psi_n(x)|^2\,dx = \frac{2}{L}\int_a^b \sin^2\left(\frac{n\pi x}{L}\right)dx$$

**Ejemplo resuelto:** Para $n=2$, probabilidad en $[L/4, 3L/4]$:

$$P = \frac{2}{L}\int_{L/4}^{3L/4} \sin^2\left(\frac{2\pi x}{L}\right)dx = \frac{1}{2}$$

Este resultado se explica por la existencia de un nodo en $x = L/2$ para el estado $n=2$.

## Capítulo 3: Operadores y Conmutadores

### 3.1 Operadores en Mecánica Cuántica

Los operadores fundamentales de posición y momento son:

$$\hat{x}\psi(x) = x\psi(x), \quad \hat{p}\psi(x) = -i\hbar\frac{d\psi}{dx}$$

### 3.2 Relaciones de Conmutación Canónicas

El conmutador canónico es:

$$[\hat{x}, \hat{p}] \equiv \hat{x}\hat{p} - \hat{p}\hat{x} = i\hbar$$

**Demostración:** Actuando sobre una función de prueba $f(x)$:

$$[\hat{x}, \hat{p}]f = x\left(-i\hbar\frac{df}{dx}\right) - \left(-i\hbar\frac{d(xf)}{dx}\right) = -i\hbar x\frac{df}{dx} + i\hbar f + i\hbar x\frac{df}{dx} = i\hbar f$$

### 3.3 Identidades de Conmutadores

Para operadores arbitrarios $\hat{A}$, $\hat{B}$, $\hat{C}$:

$$[\hat{A}\hat{B}, \hat{C}] = \hat{A}[\hat{B}, \hat{C}] + [\hat{A}, \hat{C}]\hat{B}$$

**Aplicación:** Cálculo de $[\hat{x}^2, \hat{p}]$:

$$[\hat{x}^2, \hat{p}] = \hat{x}[\hat{x}, \hat{p}] + [\hat{x}, \hat{p}]\hat{x} = \hat{x}(i\hbar) + (i\hbar)\hat{x} = 2i\hbar\hat{x}$$

### 3.4 Principio de Incertidumbre Generalizado

Para dos observables $\hat{A}$ y $\hat{B}$:

$$\Delta A \cdot \Delta B \geq \frac{1}{2}|\langle[\hat{A}, \hat{B}]\rangle|$$

Aplicando a posición y momento:

$$\Delta x \cdot \Delta p \geq \frac{\hbar}{2}$$

Esta es la **relación de incertidumbre de Heisenberg**. No se trata de una limitación instrumental, sino de una propiedad fundamental de la naturaleza cuántica de la materia.

## Capítulo 4: El Oscilador Armónico Cuántico

### 4.1 Hamiltoniano del Oscilador

$$\hat{H} = \frac{\hat{p}^2}{2m} + \frac{1}{2}m\omega^2\hat{x}^2$$

### 4.2 Método de Operadores de Creación y Aniquilación

Definimos los operadores escalera:

$$\hat{a} = \sqrt{\frac{m\omega}{2\hbar}}\left(\hat{x} + \frac{i\hat{p}}{m\omega}\right), \quad \hat{a}^\dagger = \sqrt{\frac{m\omega}{2\hbar}}\left(\hat{x} - \frac{i\hat{p}}{m\omega}\right)$$

con $[\hat{a}, \hat{a}^\dagger] = 1$.

El hamiltoniano se reescribe como:

$$\hat{H} = \hbar\omega\left(\hat{a}^\dagger\hat{a} + \frac{1}{2}\right) = \hbar\omega\left(\hat{N} + \frac{1}{2}\right)$$

### 4.3 Niveles de Energía

$$E_n = \left(n + \frac{1}{2}\right)\hbar\omega, \quad n = 0, 1, 2, ...$$

La energía de punto cero es $E_0 = \frac{1}{2}\hbar\omega$.

### 4.4 Funciones de Onda del Oscilador

$$\psi_n(x) = \left(\frac{m\omega}{\pi\hbar}\right)^{1/4}\frac{1}{\sqrt{2^n n!}}H_n(\xi)e^{-\xi^2/2}$$

donde $\xi = \sqrt{m\omega/\hbar}\,x$ y $H_n(\xi)$ son los polinomios de Hermite:

$$H_0(\xi) = 1, \quad H_1(\xi) = 2\xi, \quad H_2(\xi) = 4\xi^2 - 2$$

### 4.5 Valores Esperados e Incertidumbres

Para el estado $|n\rangle$:

$$\langle x\rangle_n = 0, \quad \langle p\rangle_n = 0$$

$$\langle x^2\rangle_n = \frac{\hbar}{2m\omega}(2n+1), \quad \langle p^2\rangle_n = \frac{m\hbar\omega}{2}(2n+1)$$

Por tanto:

$$\Delta x = \sqrt{\frac{\hbar}{2m\omega}(2n+1)}, \quad \Delta p = \sqrt{\frac{m\hbar\omega}{2}(2n+1)}$$

$$\Delta x \cdot \Delta p = \left(n + \frac{1}{2}\right)\hbar$$

Para el estado fundamental ($n=0$): $\Delta x \cdot \Delta p = \frac{\hbar}{2}$ (mínimo de Heisenberg).

Para el primer estado excitado ($n=1$): $\Delta x \cdot \Delta p = \frac{3\hbar}{2}$.

## Capítulo 5: Efecto Túnel

### 5.1 Barrera de Potencial Rectangular

Consideremos una barrera de potencial:

$$V(x) = \begin{cases} V_0 & \text{si } 0 < x < a \\ 0 & \text{en otro caso} \end{cases}$$

Para una partícula con energía $E < V_0$, la solución en la región de la barrera es exponencialmente decreciente:

$$\psi_{II}(x) = Ce^{\kappa x} + De^{-\kappa x}$$

donde $\kappa = \frac{\sqrt{2m(V_0 - E)}}{\hbar}$.

### 5.2 Coeficiente de Transmisión

El coeficiente de transmisión exacto es:

$$T = \frac{1}{1 + \frac{V_0^2\sinh^2(\kappa a)}{4E(V_0 - E)}}$$

Para barreras gruesas ($\kappa a \gg 1$), la aproximación WKB da:

$$T \approx \frac{16E(V_0 - E)}{V_0^2}e^{-2\kappa a}$$

**Ejemplo numérico:** Para un electrón con $E = 8$ eV, barrera $V_0 = 10$ eV, ancho $a = 1$ nm:

$$\kappa = \frac{\sqrt{2(9.109 \times 10^{-31})(2 \times 1.602 \times 10^{-19})}}{\hbar} \approx 7.25 \times 10^9 \text{ m}^{-1}$$

$$T \approx 2.47 \times 10^{-14}$$

### 5.3 Interpretación Física

El efecto túnel es un fenómeno puramente cuántico que no tiene análogo clásico. La partícula **no** gana energía para superar la barrera; en cambio, la amplitud de probabilidad se atenúa exponencialmente pero no se anula, permitiendo una probabilidad finita de encontrar la partícula al otro lado.

> **Nota importante:** El efecto túnel NO viola la conservación de la energía. La energía total de la partícula es la misma antes y después de la barrera.

## Capítulo 6: Problemas Resueltos

### Problema 6.1: Normalización de Función de Onda Exponencial

**Enunciado:** Dada $\Psi(x) = Ae^{-|x|/b}$, determinar la constante de normalización $A$.

**Solución:**

La condición de normalización exige:

$$\int_{-\infty}^{\infty} |A|^2 e^{-2|x|/b}\,dx = 1$$

Usando la simetría de la función:

$$2|A|^2\int_0^{\infty} e^{-2x/b}\,dx = 2|A|^2\left[-\frac{b}{2}e^{-2x/b}\right]_0^{\infty} = 2|A|^2\frac{b}{2} = |A|^2 b = 1$$

$$\boxed{A = \frac{1}{\sqrt{b}}}$$
