"""
RAGConnector v1.0 — Motor de Recuperacion para QuantumTutor
============================================================
Conecta con la base de datos vectorial (Pinecone/Milvus emulado)
para realizar busquedas semanticas sobre el material del curso.

En produccion, este modulo usaria:
  - pinecone-client o pymilvus para la BD vectorial
  - openai o sentence-transformers para embeddings reales
"""

import json
import re
import os
import logging
from datetime import datetime

logger = logging.getLogger("QuantumTutor.RAG")


class RAGConnector:
    """
    Motor de Recuperacion Aumentada para el QuantumTutor.
    Gestiona la base de datos vectorial y las busquedas semanticas
    sobre el material del curso de fisica cuantica.
    """

    def __init__(self, config_path="quantum_tutor_config.json"):
        self.config = self._load_config(config_path)
        self.vector_store = []
        self.query_log = []
        self._initialize_store()

    def _load_config(self, config_path: str) -> dict:
        """Carga la configuracion RAG desde el JSON y variables de entorno."""
        defaults = {
            "vector_store": os.getenv("VECTOR_STORE", "pinecone-serverless"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
            "top_k_fragments": int(os.getenv("TOP_K_FRAGMENTS", 5)),
            "similarity_threshold": float(os.getenv("SIMILARITY_THRESHOLD", 0.75)),
            "chunk_strategy": "semantic_markdown_headers",
            "equation_aware_chunking": True,
            "pinecone_api_key": os.getenv("PINECONE_API_KEY", ""),
            "pinecone_env": os.getenv("PINECONE_ENV", "us-east-1")
        }
        try:
            if os.path.exists(config_path):
                with open(config_path, 'r', encoding='utf-8') as f:
                    cfg = json.load(f).get("rag_parameters", {})
                    defaults.update(cfg)
        except Exception as e:
            logger.warning(f"Error cargando config {config_path}: {e}")
        return defaults

    def _initialize_store(self):
        """
        Inicializa el vector store con el material del curso.
        En produccion, se conectaria a Pinecone/Milvus.
        """
        base_dir = os.path.dirname(os.path.abspath(__file__))
        full_ocr_path = os.path.join(base_dir, "galindo_pascual_full_ocr.txt")
        sample_path = os.path.join(base_dir, "material_curso", "galindo_pascual_qm1_sample.md")

        if os.path.exists(full_ocr_path):
            with open(full_ocr_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._ingest_content(content)
            logger.info(f"Vector store inicializado: {len(self.vector_store)} chunks "
                       f"desde {os.path.basename(full_ocr_path)} (Libro Completo)")
        elif os.path.exists(sample_path):
            with open(sample_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._ingest_content(content)
            logger.info(f"Vector store inicializado: {len(self.vector_store)} chunks "
                       f"desde {os.path.basename(sample_path)}")
        else:
            # Fallback: contenido minimo embebido
            self._ingest_fallback()
            logger.info(f"Vector store inicializado con contenido fallback: "
                       f"{len(self.vector_store)} chunks")

    def _ingest_content(self, content: str):
        """Ingesta contenido Markdown con chunking semantico."""
        raw_chunks = re.split(r'\n(?=## )', content.strip())

        for i, chunk in enumerate(raw_chunks):
            if not chunk.strip() or len(chunk.strip()) < 50:
                continue

            # Extraer titulo de seccion
            title_match = re.match(r'^##\s+(.+)', chunk.strip().split('\n')[0])
            title = title_match.group(1) if title_match else f"Seccion {i}"

            # Extraer palabras clave para busqueda
            keywords = self._extract_keywords(chunk)

            self.vector_store.append({
                "id": f"chunk_{i}",
                "text": chunk.strip(),
                "title": title,
                "keywords": keywords,
                "char_count": len(chunk),
                "has_equations": "$$" in chunk or "$" in chunk,
            })

    def _ingest_fallback(self):
        """Contenido minimo de fallback si no hay documento real."""
        fallback_chunks = [
            {
                "id": "fb_0",
                "title": "Ecuacion de Schrodinger",
                "text": (
                    "La ecuacion de Schrodinger dependiente del tiempo es:\n"
                    "$$i\\hbar\\frac{\\partial}{\\partial t}|\\psi(t)\\rangle = "
                    "\\hat{H}|\\psi(t)\\rangle$$\n"
                    "donde $\\hat{H}$ es el hamiltoniano del sistema."
                ),
                "keywords": ["schrodinger", "hbar", "hamiltoniano", "evolucion", "temporal",
                            "i", "psi"],
                "char_count": 200,
                "has_equations": True,
            },
            {
                "id": "fb_1",
                "title": "Pozo de Potencial Infinito",
                "text": (
                    "Para una particula en una caja de longitud L, la funcion de onda es:\n"
                    "$$\\psi_n(x) = \\sqrt{\\frac{2}{L}}\\sin\\left(\\frac{n\\pi x}{L}\\right)$$\n"
                    "con niveles de energia $E_n = \\frac{n^2\\pi^2\\hbar^2}{2mL^2}$.\n"
                    "La energia del estado fundamental $E_1 > 0$ (energia de punto cero)."
                ),
                "keywords": ["pozo", "potencial", "infinito", "sin", "caja", "psi",
                            "energia", "cuantizada", "nodo", "hbar"],
                "char_count": 350,
                "has_equations": True,
            },
            {
                "id": "fb_2",
                "title": "Conmutadores",
                "text": (
                    "El conmutador canonico es $[\\hat{x}, \\hat{p}] = i\\hbar$.\n"
                    "Para operadores compuestos: $[\\hat{A}\\hat{B}, \\hat{C}] = "
                    "\\hat{A}[\\hat{B}, \\hat{C}] + [\\hat{A}, \\hat{C}]\\hat{B}$.\n"
                    "Aplicacion: $[\\hat{x}^2, \\hat{p}] = 2i\\hbar\\hat{x}$."
                ),
                "keywords": ["conmutador", "operador", "posicion", "momento",
                            "hbar", "algebra"],
                "char_count": 280,
                "has_equations": True,
            },
        ]
        self.vector_store.extend(fallback_chunks)

    def _extract_keywords(self, text: str) -> list:
        """Extrae palabras clave relevantes de un texto de fisica."""
        physics_terms = [
            "schrodinger", "hbar", "hamiltoniano", "pozo", "potencial",
            "infinito", "funcion de onda", "psi", "energia", "cuantizada",
            "nodo", "probabilidad", "integral", "normalizacion", "conmutador",
            "operador", "momento", "posicion", "incertidumbre", "heisenberg",
            "oscilador", "armonico", "hermite", "tunel", "barrera",
            "transmision", "born", "hilbert", "autovalor", "autovector",
            "espectro", "hermitico", "unitario", "spin", "orbital",
        ]
        text_lower = text.lower()
        return [t for t in physics_terms if t in text_lower]

    def _compute_similarity(self, query_keywords: list, chunk_keywords: list) -> float:
        """
        Calcula similitud basada en keywords (emulando cosine similarity).
        En produccion, usaria embeddings reales + cosine similarity.
        """
        if not query_keywords or not chunk_keywords:
            return 0.0
        intersection = set(query_keywords) & set(chunk_keywords)
        union = set(query_keywords) | set(chunk_keywords)
        return len(intersection) / len(union) if union else 0.0

    def query(self, user_query: str, k: int = None) -> str:
        """
        Busqueda semantica sobre el material del curso.

        Args:
            user_query: Consulta del estudiante
            k: Numero de fragmentos a recuperar (default: config top_k)

        Returns:
            str: Fragmentos concatenados del material relevante
        """
        if k is None:
            k = self.config.get("top_k_fragments", 3)

        query_keywords = self._extract_keywords(user_query.lower())

        # Tambien buscar terminos directos en la query
        query_words = set(re.findall(r'\b\w+\b', user_query.lower()))
        extra_terms = [w for w in query_words if len(w) > 3]
        query_keywords.extend(extra_terms)

        # Calcular similitud con cada chunk
        scored = []
        for chunk in self.vector_store:
            # Similitud por keywords
            kw_sim = self._compute_similarity(query_keywords, chunk["keywords"])

            # Similitud directa por texto (busqueda de subcadenas)
            text_lower = chunk["text"].lower()
            text_hits = sum(1 for w in query_words if w in text_lower and len(w) > 3)
            text_sim = text_hits / max(len(query_words), 1)

            # Score combinado
            combined = 0.6 * kw_sim + 0.4 * text_sim
            scored.append((chunk, combined))

        # Ordenar por relevancia y filtrar por threshold
        scored.sort(key=lambda x: x[1], reverse=True)
        threshold = self.config.get("similarity_threshold", 0.0)
        top_results = [(c, s) for c, s in scored[:k] if s >= threshold * 0.3]

        # Si no hay resultados por threshold, devolver los top k de todas formas
        if not top_results and scored:
            top_results = scored[:k]

        # Log de la consulta
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": user_query[:100],
            "results_count": len(top_results),
            "top_score": round(top_results[0][1], 4) if top_results else 0,
            "sections": [r[0]["title"] for r in top_results]
        }
        self.query_log.append(log_entry)
        logger.info(f"RAG Query: '{user_query[:50]}...' -> {len(top_results)} results, "
                    f"top_score={log_entry['top_score']}")

        # Concatenar fragmentos con metadata
        context_parts = []
        for chunk, score in top_results:
            context_parts.append(
                f"[Doc: {chunk['title']}, Score: {score:.2f}]\n"
                f"{chunk['text']}"
            )

        return "\n\n---\n\n".join(context_parts) if context_parts else ""

    def get_stats(self) -> dict:
        """Retorna estadisticas del vector store."""
        return {
            "total_chunks": len(self.vector_store),
            "total_chars": sum(c["char_count"] for c in self.vector_store),
            "chunks_with_equations": sum(1 for c in self.vector_store if c["has_equations"]),
            "total_queries": len(self.query_log),
            "sections": [c["title"] for c in self.vector_store],
        }


# ── Ejecucion standalone ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 72)
    print("  RAG ENGINE — Prueba de Conectividad")
    print("=" * 72)

    rag = RAGConnector()
    stats = rag.get_stats()
    print(f"\n  Vector Store: {stats['total_chunks']} chunks, "
          f"{stats['total_chars']} chars")
    print(f"  Chunks con ecuaciones: {stats['chunks_with_equations']}")
    print(f"  Secciones:")
    for s in stats["sections"]:
        print(f"    - {s}")

    # Test queries
    test_queries = [
        "Ecuacion de Schrodinger dependiente del tiempo",
        "Probabilidad en el pozo de potencial infinito para n=2",
        "Conmutador de x cuadrado con p",
        "Efecto tunel cuantico",
        "Principio de incertidumbre de Heisenberg",
    ]

    print(f"\n  Ejecutando {len(test_queries)} consultas de prueba:")
    for q in test_queries:
        result = rag.query(q, k=1)
        preview = result[:120].replace('\n', ' ') if result else "(sin resultados)"
        print(f"\n  Q: \"{q}\"")
        print(f"  R: {preview}...")

    print(f"\n{'=' * 72}")
    print(f"  [OK] RAG Engine funcional: {stats['total_chunks']} chunks indexados")
    print(f"{'=' * 72}\n")
