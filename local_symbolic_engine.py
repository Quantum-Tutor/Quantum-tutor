import sympy as sp
import re
import logging

class LocalSymbolicEngine:
    """
    Motor simbólico híbrido del runtime actual
    Procesa álgebra básica e integrales definidas sencillas de forma local, sin latencia de red.
    Si detecta operaciones de Wolfram Language complejas (ej. 'TunnelTransmission', 'Commutator'), retorna None.
    """
    def __init__(self):
        # Variables cuánticas comunes
        self.x, self.p, self.t, self.hbar, self.m, self.L = sp.symbols('x p t hbar m L', real=True)
        self.sigma = sp.Symbol('sigma', positive=True)
        self.H = sp.Symbol('H', commutative=False)
        self.psi = sp.Symbol('psi')
        self.phi = sp.Symbol('phi')
        self.E = sp.Symbol('E', real=True)
        
        # Diccionario de funciones seguras
        self.safe_dict = {
            'x': self.x, 'p': self.p, 't': self.t, 'hbar': self.hbar, 'm': self.m, 'L': self.L,
            'H': self.H, 'psi': self.psi, 'phi': self.phi, 'E': self.E, 'sigma': self.sigma,
            'Sin': sp.sin, 'Cos': sp.cos, 'Exp': sp.exp, 'Sqrt': sp.sqrt, 'Pi': sp.pi,
            # `Integrate` se quitó de safe_dict porque se maneja explícitamente
            # en _parse_and_integrate() antes de llamar a sympify. Mantenerlo aquí
            # podría producir un TypeError silencioso si sympify llegara a usarlo.
            'VirialTheorem': self._evaluate_virial
        }

    def evaluate_local(self, expression: str):
        try:
            # 1. Filtro Heurístico Rápido
            if any(kw in expression for kw in ['Eigenvalues', 'Hydrogen']):
                logging.info("[SYMPY] Excedida capacidad local. Enrutando a Wolfram Cloud.")
                return None
            
            # 2. Análisis de conmutadores: Commutator[A, B]
            if "Commutator[" in expression:
                match = re.match(r"Commutator\[(.*),\s*(.*)\]", expression)
                if match:
                    op_a_str = match.group(1).strip()
                    op_b_str = match.group(2).strip()
                    return self._evaluate_commutator(op_a_str, op_b_str)

            # 3. Análisis de integrales estilo Wolfram: Integrate[expr, {x, a, b}]
            if expression.startswith("Integrate["):
                return self._parse_and_integrate(expression)

            # 4. Teorema del virial: VirialTheorem[V(x)]
            if expression.startswith("VirialTheorem["):
                v_expr = expression.replace("VirialTheorem[", "").rstrip("]")
                return self._evaluate_virial(v_expr)
                
            # 5. Álgebra rutinaria
            clean_expr = expression.replace('[', '(').replace(']', ')')
            result = sp.sympify(clean_expr, locals=self.safe_dict)
            return {"result": str(result), "latex": sp.latex(result), "source": "SymPy (Local)"}
            
        except Exception as e:
            logging.debug(f"[SYMPY] Fallo en evaluación local: {e}")
            return None

    def _evaluate_commutator(self, op_a_str, op_b_str):
        """Implementa identidades de conmutadores cuánticos [x, p] = i*hbar."""
        import re as regex
        
        # Caso base [x, p] = i*hbar
        if op_a_str == 'x' and op_b_str == 'p':
            return {"result": "I*hbar", "latex": "i\\hbar", "source": "SymPy (Local) [Canonical]"}
        
        # Regla de potencia [x^n, p] = n * i*hbar * x^(n-1)
        match_xn = regex.match(r"x\^?(\d*)", op_a_str)
        if match_xn and op_b_str == 'p':
            n = int(match_xn.group(1)) if match_xn.group(1) else 1
            res_val = f"{n}*I*hbar*x**({n-1})" if n > 1 else "I*hbar"
            res_latex = f"{n}i\\hbar x^{{{n-1}}}" if n > 1 else "i\\hbar"
            return {"result": res_val, "latex": res_latex, "source": "SymPy (Local) [Propiedad]"}

        # Regla de potencia [x, p^n] = n * i*hbar * p^(n-1)
        match_pn = regex.match(r"p\^?(\d*)", op_b_str)
        if op_a_str == 'x' and match_pn:
            n = int(match_pn.group(1)) if match_pn.group(1) else 1
            res_val = f"{n}*I*hbar*p**({n-1})" if n > 1 else "I*hbar"
            res_latex = f"{n}i\\hbar p^{{{n-1}}}" if n > 1 else "i\\hbar"
            return {"result": res_val, "latex": res_latex, "source": "SymPy (Local) [Propiedad]"}

        # Caso [p, x] = -i*hbar
        if op_a_str == 'p' and op_b_str == 'x':
            return {"result": "-I*hbar", "latex": "-i\\hbar", "source": "SymPy (Local) [Canonical]"}
            
        # Caso [H, A] = 0 (Si A es H o constante)
        if op_a_str == 'H' and (op_b_str == 'H' or op_b_str.isdigit()):
            return {"result": "0", "latex": "0", "source": "SymPy (Local) [Identity]"}

        # Fallback al conmutador genérico de SymPy para expansión algebraica básica
        try:
            from sympy.physics.quantum import Commutator
            from sympy.physics.quantum.operator import Operator
            A = Operator(op_a_str) if op_a_str in ['x', 'p', 'H'] else sp.sympify(op_a_str.replace('[','(').replace(']',')'), locals=self.safe_dict)
            B = Operator(op_b_str) if op_b_str in ['x', 'p', 'H'] else sp.sympify(op_b_str.replace('[','(').replace(']',')'), locals=self.safe_dict)
            comm = Commutator(A, B)
            result = comm.doit().expand()
            return {"result": str(result), "latex": sp.latex(result), "source": "SymPy (Local) [Algebraic]"}
        # Usamos `except Exception` en lugar de un `except:` desnudo
        # para no ocultar SystemExit ni KeyboardInterrupt.
        except Exception:
            return None

    def _parse_and_integrate(self, expr_str):
        # Extraer Integrate[ expr , {var, a, b}]
        match = re.match(r"Integrate\[(.*),\s*\{(.*),\s*(.*),\s*(.*)\}\]", expr_str)
        if not match: return None
        
        integrand_str = match.group(1).replace('[', '(').replace(']', ')')
        var_str = match.group(2).strip()
        lim_a_str = match.group(3).strip()
        lim_b_str = match.group(4).strip()
        
        try:
            integrand = sp.sympify(integrand_str, locals=self.safe_dict)
            var = sp.Symbol(var_str, real=True)
            a = sp.sympify(lim_a_str, locals=self.safe_dict)
            b = sp.sympify(lim_b_str, locals=self.safe_dict)
            
            # Resolver localmente
            result = sp.integrate(integrand, (var, a, b))
            
            # Simplificar
            result = sp.simplify(result)
            
            return {
                "result": str(result),
                "latex": sp.latex(result),
                "source": "SymPy (Local)"
            }
        except Exception:
            return None
            
    def _evaluate_virial(self, potential_str):
        """Implementa el Teorema del Virial: 2<T> = <x dV/dx>."""
        try:
            V = sp.sympify(potential_str.replace('[', '(').replace(']', ')'), locals=self.safe_dict)
            force_term = self.x * sp.diff(V, self.x)
            result_latex = f"2\\langle T \\rangle = \\langle x \\frac{{dV}}{{dx}} \\rangle = \\langle {sp.latex(force_term)} \\rangle"
            return {
                "result": f"2*T_avg = {force_term}",
                "latex": result_latex,
                "source": "SymPy (Local) [Virial Theorem]"
            }
        except Exception:
            return None

    def _local_integrate(self, *args):
        # Este stub ya no se registra en safe_dict.
        # Se conserva por compatibilidad en caso de invocación directa.
        raise NotImplementedError("Use _parse_and_integrate() for Wolfram-style Integrate[] expressions.")

if __name__ == "__main__":
    engine = LocalSymbolicEngine()
    print("Test 1 (Álgebra local):", engine.evaluate_local("x^2 + 2*x + 1"))
    print("Test 2 (Integral definida Pozo n=2):", engine.evaluate_local("Integrate[(Sqrt[2/L] * Sin[2 * Pi * x / L])^2, {x, L/4, 3*L/4}]"))
    print("Test 3 (Conmutador [x, p]):", engine.evaluate_local("Commutator[x, p]"))
    print("Test 4 (Virial HO):", engine.evaluate_local("VirialTheorem[1/2 * m * omega^2 * x^2]"))
    print("Test 5 (Integral Gaussiana):", engine.evaluate_local("Integrate[Exp[-x^2 / (2*sigma^2)], {x, -Infinity, Infinity}]"))
    print("Test 6 (Fallo intencional -> Wolfram):", engine.evaluate_local("TunnelTransmission[V0=10eV, E=8eV, a=1nm, m=m_e]"))
