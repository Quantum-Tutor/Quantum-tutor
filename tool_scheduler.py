import re
import random
from calibrator import AdaptiveCalibrator

class ToolSpec:
    def __init__(self, name, handler, cost, latency_estimate):
        self.name = name
        self.handler = handler
        self.cost = cost
        self.latency_estimate = latency_estimate


class ToolRegistry:
    def __init__(self):
        self.tools = {}

    def register(self, tool: ToolSpec):
        self.tools[tool.name] = tool

    def get(self, name):
        return self.tools.get(name)

    def all(self):
        return list(self.tools.values())


def extract_features(ctx):
    text = ctx.user_input.lower()
    
    math_pattern = r"(∫|\\int|d/dx|=|\^|\[.*?,.*?\]|[\+\-\*/])"

    return {
        "length": len(text),
        
        # Matemática explícita
        "has_math": bool(re.search(math_pattern, text)),
        
        # Computación explícita
        "is_computation": any(w in text for w in [
            "calcula", "resolver", "derivar", "evalúa", "normaliza", "halla", "encuentra", "íntegra"
        ]),
        
        # Física teórica
        "has_physics_terms": any(w in text for w in [
            "energía", "función de onda", "oscilador", "hamiltoniano", "momentum", "estado", "probabilidad"
        ]),
        
        # Operadores algebraicos cuánticos (CRÍTICO)
        "has_operator": any(w in text for w in [
            "conmutador", "commutator", "operador"
        ]),
        
        # Estructura matemática implícita
        "has_symbolic_structure": bool(re.search(r"\[.*?,.*?\]", text))
    }


def score_tools(features):
    scores = {}

    # --- Wolfram ---
    score = 0
    if features["has_math"]:
        score += 2
    if features["is_computation"]:
        score += 3
    if features["has_operator"]:
        score += 2
    if features["has_symbolic_structure"]:
        score += 2
    
    scores["wolfram"] = score

    # --- RAG ---
    score = 0
    if features["has_physics_terms"]:
        score += 2
    if not features["is_computation"] and not features["has_operator"]:
        score += 1

    scores["rag"] = score

    return scores


def seeded_random(session_id):
    import hashlib
    seed = int(hashlib.sha256(session_id.encode('utf-8')).hexdigest(), 16) % (10 ** 8)
    return random.Random(seed).random()


def select_tools(scores, ctx):
    selected = []

    # Threshold determinista base
    if scores.get("wolfram", 0) >= 2:
        selected.append("wolfram")

    if scores.get("rag", 0) >= 1:
        selected.append("rag")

    # Exploración probabilística determinista por sesión
    if "wolfram" not in selected and seeded_random(ctx.session_id) < 0.1:
        selected.append("wolfram")

    return list(set(selected))


class ExecutionPlan:
    def __init__(self):
        self.run_rag = False
        self.run_wolfram = False
        self.wolfram_mode = "late"  # o "blocking"


def build_plan(selected_tools):
    plan = ExecutionPlan()

    if "rag" in selected_tools:
        plan.run_rag = True

    if "wolfram" in selected_tools:
        plan.run_wolfram = True
        plan.wolfram_mode = "late"

    return plan


class ToolScheduler:
    """
    Interfaz plug-and-play para el scheduler, ahora V7.1 Adaptive.
    """
    def __init__(self, registry: ToolRegistry):
        self.registry = registry
        self.calibrator = AdaptiveCalibrator()

    def plan(self, ctx) -> ExecutionPlan:
        features = extract_features(ctx)
        scores = score_tools(features)
        
        # Inferencia Adaptativa
        selected = []
        if scores.get("rag", 0) >= 1:
            selected.append("rag")
            
        run_wolfram = False
        if scores:
            run_wolfram = self.calibrator.should_use_wolfram(scores)
            
        if run_wolfram:
            selected.append("wolfram")
            
        # Exploración probabilística (Shadow mode de descubrimiento)
        if "wolfram" not in selected and seeded_random(ctx.session_id) < 0.1:
            selected.append("wolfram")

        plan = build_plan(selected)

        # Telemetría embebida
        scheduler_meta = ctx.metadata.setdefault("scheduler", {})
        scheduler_meta.update({
            "features": features,
            "scores": scores,
            "selected": selected,
            "calibrator": {
                "threshold": self.calibrator.threshold,
                "decision": run_wolfram,
                "delta": scores.get("wolfram", 0) - scores.get("rag", 0)
            }
        })

        return plan

