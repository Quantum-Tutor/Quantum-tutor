import sympy as sp
import re
import logging

class LocalSymbolicEngine:
    """
    Motor Simbólico Híbrido v2.0
    Procesa álgebra básica e integrales definidas sencillas de forma local (0ms latencia de red).
    Si detecta operaciones de Wolfram Language complejas (ej. 'TunnelTransmission', 'Commutator'), retorna None.
    """
    def __init__(self):
        # Variables cuánticas comunes
        self.x, self.p, self.t, self.hbar, self.m, self.L = sp.symbols('x p t hbar m L', real=True)
        # Diccionario de funciones seguras
        self.safe_dict = {'x': self.x, 'p': self.p, 't': self.t, 'hbar': self.hbar, 'm': self.m, 'L': self.L,
                          'Sin': sp.sin, 'Cos': sp.cos, 'Exp': sp.exp, 'Sqrt': sp.sqrt, 'Pi': sp.pi, 'Integrate': self._local_integrate}

    def evaluate_local(self, expression: str):
        try:
            # 1. Filtro Heurístico Rápido: Operaciones prohibidas para SymPy local
            if any(kw in expression for kw in ['TunnelTransmission', 'Commutator', 'Eigenvalues', 'Hydrogen']):
                logging.info("[SYMPY] Excedida capacidad local. Enrutando a Wolfram Cloud.")
                return None
            
            # 2. Parsing de Integrales estilo Wolfram: Integrate[expr, {x, a, b}]
            if expression.startswith("Integrate["):
                return self._parse_and_integrate(expression)
                
            # 3. Álgebra rutinaria
            # Reemplazar sintaxis básica de Mathematica a SymPy
            clean_expr = expression.replace('[', '(').replace(']', ')')
            result = sp.sympify(clean_expr, locals=self.safe_dict)
            return {"result": str(result), "latex": sp.latex(result), "source": "SymPy (Local)"}
            
        except Exception as e:
            logging.debug(f"[SYMPY] Fallo en evaluación local: {e}. Enrutando a Wolfram Cloud.")
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
            
    def _local_integrate(self, *args):
        # Fallback interno
        pass

if __name__ == "__main__":
    engine = LocalSymbolicEngine()
    print("Test 1 (Álgebra local):", engine.evaluate_local("x^2 + 2*x + 1"))
    print("Test 2 (Integral definida Pozo n=2):", engine.evaluate_local("Integrate[(Sqrt[2/L] * Sin[2 * Pi * x / L])^2, {x, L/4, 3*L/4}]"))
    print("Test 3 (Fallo intencional -> Wolfram):", engine.evaluate_local("TunnelTransmission[V0=10eV, E=8eV, a=1nm, m=m_e]"))
