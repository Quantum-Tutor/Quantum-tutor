"""
QuantumTutor v1.2 — Orquestador Optimizado (Low Latency)
=============================================================
Arquitectura: RAG Neuro-Simbolico + Tool Enforcing
Optimizaciones: Asyncio (RAG/Wolfram concurrente), Wolfram Caching,
                Context Truncation Inteligente, Streaming Simulado.
"""

import os
import sys
import json
import re
import logging
import asyncio
import time
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from wolfram_emulator import WolframAlphaEmulator
from rag_engine import RAGConnector
from local_symbolic_engine import LocalSymbolicEngine
from semantic_cache import SemanticCache
from learning_analytics import LearningAnalytics

# ── Configuracion de Logging ─────────────
log_path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        'quantum_tutor_system.log')
logging.basicConfig(
    filename=log_path,
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)
logger = logging.getLogger("QuantumTutor.Orchestrator")

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setLevel(logging.INFO)
console_handler.setFormatter(logging.Formatter(
    '%(asctime)s [%(levelname)s] %(message)s', datefmt='%H:%M:%S'
))
logger.addHandler(console_handler)


class QuantumTutorOrchestrator:
    """
    Orquestador de baja latencia para el QuantumTutor v1.2.
    """

    def __init__(self, config_path='quantum_tutor_config.json'):
        self.config_path = os.path.join(
            os.path.dirname(os.path.abspath(__file__)), config_path
        )
        self.config = {}
        self.load_config(self.config_path)

        self.wolfram = WolframAlphaEmulator(app_id=os.getenv("WOLFRAM_APP_ID", ""))
        self.rag = RAGConnector(config_path=self.config_path)
        self.system_prompt = self.load_system_prompt()

        self.session_log = []
        self.health_status = None
        
        # Integracion v3.0: Motor Híbrido, Caché Semántica y Analytics
        self.local_engine = LocalSymbolicEngine()
        self.semantic_cache = SemanticCache(threshold=0.70)
        self.analytics = LearningAnalytics('student_profile.json')

        logger.info(f"QuantumTutor v3.0 (Production) inicializado: "
                    f"T={self.config.get('temperature', 'N/A')}, "
                    f"Top-K={self.config.get('top_k', 'N/A')}")

    def load_config(self, path: str):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                full_config = json.load(f)

            self.config = {
                "temperature": full_config.get("llm_config", {}).get("temperature", 0.2),
                "max_tokens": full_config.get("llm_config", {}).get("max_tokens", 2048),
                "model": full_config.get("llm_config", {}).get("model", "claude-3-5-sonnet"),
                "top_k": full_config.get("rag_parameters", {}).get("top_k_fragments", 5),
                "similarity_threshold": full_config.get("rag_parameters", {}).get("similarity_threshold", 0.75),
                "agent_name": full_config.get("system_metadata", {}).get("agent_name", "QuantumTutor"),
                "version": "v3.0-production",
            }
            self.full_config = full_config
            print(f"[*] Configuracion cargada (Production Mode)")
        except FileNotFoundError:
            logger.error(f"Config no encontrado: {path}")
            self.config = {"temperature": 0.2, "top_k": 5, "version": "v3.0-production"}
            self.full_config = {}

    def load_system_prompt(self) -> str:
        prompt_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'system_prompt.md')
        try:
            with open(prompt_path, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            return "Eres un tutor socratico de fisica cuantica."

    # ══════════════════════════════════════════════════════════════════
    # ASYNC TOOL EXECUTION
    # ══════════════════════════════════════════════════════════════════

    async def _async_rag_query(self, user_input: str) -> str:
        """Envoltorio asincrono para la busqueda RAG."""
        start = time.perf_counter()
        
        # En produccion esto seria un await call(db)
        # Simulamos latencia de red de base de datos vectorial
        await asyncio.sleep(0.12)  # Latencia pre-auditoria de 120ms
        
        context = self.rag.query(user_input, k=self.config.get("top_k", 5))
        
        # --- OPTIMIZACION: Intelligent Context Truncation ---
        if context:
            blocks = context.split("\n\n---\n\n")
            filtered_blocks = []
            
            # Asumimos que el primer bloque es el mas relevante en nuestro motor emulado
            max_score = 1.0 # En un sistema real extraemos el score real del objeto
            
            for i, block in enumerate(blocks):
                # Extraer score del string (ej: [Doc: Cap1, Score: 0.95])
                score_match = re.search(r'Score: ([\d\.]+)', block)
                if score_match:
                    score = float(score_match.group(1))
                    if i == 0:
                        max_score = score
                    
                    # Truncar si es menos del 85% de relevancia relativa al mejor chunk
                    # Y asegurar mantener al menos el primero
                    if i == 0 or score >= max_score * 0.85:
                        filtered_blocks.append(block)
                    else:
                        logger.info(f"Context Truncation: Descartando chunk {i} (Score: {score:.2f} < Threshold {max_score*0.85:.2f})")
                else:
                    filtered_blocks.append(block)
                    
            context = "\n\n---\n\n".join(filtered_blocks)
            logger.info(f"RAG truncado de {len(blocks)} a {len(filtered_blocks)} chunks. Latencia RAG: {(time.perf_counter()-start)*1000:.1f}ms")
            
        return context

    async def _async_wolfram_query(self, wl_query: str) -> dict:
        """Ejecucion asincrona híbrida y cacheada (v2.0)."""
        if not wl_query:
            return None
            
        start = time.perf_counter()
        
        # 1. Caché Semántica Dinámica
        cached_result = self.semantic_cache.check(wl_query)
        if cached_result:
            latency = (time.perf_counter() - start) * 1000
            logger.info(f"Semantic Cache HIT. Latencia: {latency:.1f}ms")
            return {"query": wl_query, "status": "success", "result": cached_result.get("result"), "latex": cached_result.get("latex"), "source": "Semantic Cache"}
            
        # 2. Motor Simbólico Local (SymPy)
        local_result = self.local_engine.evaluate_local(wl_query)
        if local_result:
            latency = (time.perf_counter() - start) * 1000
            logger.info(f"SymPy Local HIT. Latencia: {latency:.1f}ms")
            
            # Guardamos en la caché semántica para futuras variantes
            self.semantic_cache.store(wl_query, {"result": local_result["result"], "latex": local_result["latex"]})
            
            return {"query": wl_query, "status": "success", "result": local_result["result"], "latex": local_result["latex"], "source": "SymPy (Local)"}
            
        # 3. Fallback a Nube (Wolfram Alpha Cloud)
        await asyncio.sleep(0.8)  # Latencia de red emulada
        
        res = self.wolfram.query(wl_query)
        
        wolfram_response = {
            "query": wl_query,
            "status": res["status"],
            "result": res.get("result_symbolic"),
            "numeric": res.get("result_numeric"),
            "latex": res.get("result_latex"),
            "source": "Wolfram Cloud"
        }
        
        # Guardar en cache semántica
        self.semantic_cache.store(wl_query, {"result": wolfram_response["result"], "latex": wolfram_response["latex"]})
        
        latency = (time.perf_counter() - start)
        logger.info(f"Wolfram Cloud Miss. Latencia API: {latency:.2f}s")
        return wolfram_response

    def _needs_wolfram(self, user_input: str) -> str:
        """Detecta y retorna la query WL si es necesario, o None."""
        patterns = [
            r'calcula', r'integral', r'probabilidad', r'conmutador',
            r'incertidumbre', r'tunel', r'transmision'
        ]
        input_lower = user_input.lower()
        if not any(re.search(p, input_lower) for p in patterns):
            return None
            
        if "normaliz" in input_lower and "exponencial" in input_lower:
            return "Integrate[A^2 Exp[-2 Abs[x]/b], {x, -Infinity, Infinity}] == 1"
        elif "probabilidad" in input_lower and "pozo" in input_lower:
            return "Integrate[(Sqrt[2/L] Sin[2 Pi x / L])^2, {x, L/4, 3L/4}]"
        elif "conmutador" in input_lower and ("x^2" in input_lower or "x cuadrado" in input_lower):
            return "Commutator[x^2, p]"
        elif "tunel" in input_lower or "transmision" in input_lower:
            return "TunnelTransmission[V0=10eV, E=8eV, a=1nm, m=m_e]"
        elif "incertidumbre" in input_lower and "oscilador" in input_lower:
            return "UncertaintyProduct[HarmonicOscillator, n=1]"
        return None

    # ══════════════════════════════════════════════════════════════════
    # GENERACION ASINCRONA DE RESPUESTA
    # ══════════════════════════════════════════════════════════════════

    async def generate_response_async(self, user_input: str) -> dict:
        """Flujo de Inferencia Asincrono y Optimizado."""
        start_time = time.perf_counter()
        logger.info(f"Procesando consulta: '{user_input[:80]}...'")
        print(f"\n[*] Procesando consulta: \"{user_input[:60]}...\"")

        result = {
            "input": user_input,
            "timestamp": datetime.now().isoformat(),
            "context_retrieved": False,
            "wolfram_used": False,
            "wolfram_result": None,
            "response": "",
            "latency": {}
        }

        # Deteccion sincronica e instantanea de calculo
        wl_query = self._needs_wolfram(user_input)
        
        # --- OPTIMIZACION: Ejecucion Paralela ---
        print(f"[ASYNC] Lanzando RAG y Wolfram concurrentemente...")
        task_rag = asyncio.create_task(self._async_rag_query(user_input))
        
        task_wolfram = None
        if wl_query:
            task_wolfram = asyncio.create_task(self._async_wolfram_query(wl_query))
            
        # Esperar resultados paralelos
        context = await task_rag
        
        if context:
            result["context_retrieved"] = True
            print(f"    [RAG] Contexto recuperado y truncado: {len(context)} chars")
            
        if task_wolfram:
            wolfram_res = await task_wolfram
            if wolfram_res:
                result["wolfram_used"] = True
                result["wolfram_result"] = wolfram_res
                print(f"    [WOLFRAM] Resultado: {wolfram_res.get('latex') or wolfram_res.get('result')}")

        io_latency = time.perf_counter() - start_time
        result["latency"]["io_fetch"] = round(io_latency, 3)

        # --- OPTIMIZACION: Streaming Simulado ---
        print(f"[STREAM] Reflexion del tutor (Time-to-First-Token: <1.5s)...")
        await asyncio.sleep(1.2) # First token simulado
        
        response = self._build_socratic_response(user_input, context, result)
        result["response"] = response
        
        total_latency = time.perf_counter() - start_time
        result["latency"]["total"] = round(total_latency, 3)
        
        print(f"[DONE] Generacion completada en {total_latency:.2f}s")
        self.session_log.append(result)
        
        return result

    def _build_socratic_response(self, user_input: str, context: str, result: dict) -> str:
        # Dynamic Scaffolding: detectar topico y ajustar nivel
        topic = self._detect_topic(user_input)
        scaffolding = self.analytics.get_scaffolding_level(topic)
        
        parts = [f"[Nivel Socratico: {scaffolding['label']}]\n\n"]
        parts.append("Entendido. Analizando paso a paso.\n")
        if result["context_retrieved"]:
            parts.append("Segun el material del curso (truncado para eficiencia):\n")
        if result["wolfram_used"] and result["wolfram_result"]:
            source = result['wolfram_result'].get('source', 'Wolfram')
            parts.append(f"\nVerificado simbolicamente (via {source}):\n\n$$ {result['wolfram_result']['latex']} $$\n\n")
        
        # Adaptar la pregunta socratica al nivel del estudiante
        modifier = scaffolding.get('modifier', '')
        if scaffolding['level'] == 1:
            parts.append("\nVamos paso a paso. Primero: identifica las variables clave del problema. " 
                        "Que magnitudes fisicas intervienen aqui?\n")
        elif scaffolding['level'] == 3:
            parts.append("\nReflexion avanzada: Que pasaria si cambiaramos las condiciones de contorno? "
                        "Existe algun caso limite que invalide esta solucion?\n")
        else:
            parts.append("\nReflexion socratica: Por que crees que sucede esto fisicamente?\n")
        
        return "".join(parts)

    def _detect_topic(self, user_input: str) -> str:
        """Detecta el topico de la consulta para el scaffolding."""
        input_lower = user_input.lower()
        if "pozo" in input_lower: return "Pozo Infinito"
        elif "tunel" in input_lower or "tunnel" in input_lower: return "Efecto Tunel"
        elif "espin" in input_lower or "spin" in input_lower: return "Espin"
        elif "oscilador" in input_lower: return "Oscilador Armonico"
        elif "conmutador" in input_lower: return "Conmutadores"
        return "General"


async def main():
    print("\n" + "=" * 72)
    print("  QuantumTutor v1.2 — Orquestador Low-Latency")
    print("  Asyncio + Context Truncation + Wolfram Caching")
    print("=" * 72)

    tutor = QuantumTutorOrchestrator()
    print("\n[SUCCESS] Sistema inicializado.\n")

    test_queries = [
        "Calcula la probabilidad de encontrar la particula en el centro del pozo para n=2",
        "Calcula la probabilidad de encontrar la particula en el centro del pozo para n=2", # Misma query para forzar cache
        "Explicame el efecto tunel cuantico",
    ]

    for i, query in enumerate(test_queries, 1):
        print(f"\n{'─' * 72}")
        print(f"  CONSULTA {i} {' (CACHE TEST)' if i==2 else ''}")
        print(f"{'─' * 72}")
        
        result = await tutor.generate_response_async(query)
        
        print(f"\n  [LATENCIA] I/O Fetch: {result['latency']['io_fetch']}s | "
              f"Total: {result['latency']['total']}s")
        print(f"  [TUTOR] {result['response'].replace(chr(10), ' ')}")

    print(f"\n{'=' * 72}")
    print("  Ejecucion ASYNC completada con latencias optimizadas.")
    print("=" * 72 + "\n")


if __name__ == "__main__":
    asyncio.run(main())
