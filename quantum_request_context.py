import time
from typing import Optional, List, Dict, Any

class QuantumRequestContext:
    """
    Unidad de ejecución aislada por request.
    NO debe compartir estado mutable entre usuarios.
    """

    def __init__(
        self,
        user_id: str,
        session_id: str,
        user_input: str,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        rate_limit_mode: str = "soft",

        # Dependencias inyectadas (desde session store o factory)
        relational=None,
        analytics=None,
        semantic_cache=None,
    ):
        # --- Identidad ---
        self.user_id = user_id
        self.session_id = session_id

        # --- Input ---
        self.user_input = user_input
        self.history = conversation_history or []
        self.rate_limit_mode = rate_limit_mode

        # --- Estado aislado (CRÍTICO) ---
        self.relational = relational
        self.analytics = analytics
        self.cache = semantic_cache

        # --- Derivados (routing) ---
        self.topic: Optional[str] = None
        self.intent: Optional[str] = None
        self.needs_wolfram: bool = False

        # --- Datos intermedios ---
        self.rag_data: Optional[Dict[str, Any]] = None
        self.wolfram_result: Optional[Dict[str, Any]] = None
        self.reasoning_trace: Optional[Dict[str, Any]] = None
        self.model_route: Optional[Dict[str, Any]] = None

        # --- Control runtime ---
        self.start_time = time.perf_counter()
        self.cancelled: bool = False

        # --- Extensibilidad (v6+) ---
        self.pending_tasks: List[Any] = []   # late fusion hooks
        self.metadata: Dict[str, Any] = {}

        # --- Late fusion ---
        self.wolfram_task = None
        self.wolfram_ready = False
        self.wolfram_emitted = False

    def mark_cancelled(self):
        self.cancelled = True

    def latency(self) -> float:
        return time.perf_counter() - self.start_time
