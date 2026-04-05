import json
import logging
import numpy as np
from pathlib import Path
from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import cosine

from quantum_tutor_paths import SEMANTIC_CACHE_PATH, resolve_runtime_path, write_json_atomic

class SemanticCache:
    """
    Caché Semántica Dinámica v2.1
    Almacena consultas de Wolfram ya resueltas y utiliza embeddings para recuperar resultados
    ante variaciones de fraseo (ej. "probabilidad centro pozo" vs "integral pozo medio").
    BUG-10 FIX: SentenceTransformer ahora se carga de forma perezosa (lazy loading)
    para no bloquear el startup de Streamlit.
    """
    def __init__(self, cache_file=SEMANTIC_CACHE_PATH, threshold=0.70):
        if isinstance(cache_file, Path):
            self.cache_file = cache_file
        else:
            self.cache_file = Path(cache_file)
        if self.cache_file == SEMANTIC_CACHE_PATH:
            self.cache_file = resolve_runtime_path(SEMANTIC_CACHE_PATH, "semantic_cache.json")
        self.threshold = threshold
        self.entries = []
        self._encoder = None  # BUG-10 FIX: lazy loading
        self.load_cache()

    @property
    def encoder(self):
        """Carga el modelo de embeddings de forma perezosa."""
        if self._encoder is None:
            logging.info("[CACHE] Cargando modelo SentenceTransformer (all-MiniLM-L6-v2)...")
            try:
                self._encoder = SentenceTransformer('all-MiniLM-L6-v2')
                logging.info("[CACHE] Modelo cargado.")
            except Exception as e:
                logging.error(f"[CACHE] Error cargando SentenceTransformer: {e}")
                self._encoder = None
        return self._encoder

    def load_cache(self):
        try:
            with self.cache_file.open('r', encoding='utf-8') as f:
                data = json.load(f)
                self.entries = data.get("entries", [])
            logging.info(f"[CACHE] Cargadas {len(self.entries)} entradas semánticas.")
        except FileNotFoundError:
            self.entries = []
            
    def save_cache(self):
        # Los embeddings no son serializables directamente por JSON, los guardamos como listas
        write_json_atomic(self.cache_file, {"entries": self.entries}, indent=4)

    def check(self, query: str):
        if not self.entries or not self.encoder:
            return None
            
        # Calcular embedding de la consulta entrante
        query_embedding = self.encoder.encode(query)
        
        best_score = 0
        best_match = None
        
        for entry in self.entries:
            # Reconstituir embedding almacenado
            cached_emb = np.array(entry['embedding'])
            # Similitud de coseno (1 - distancia)
            similarity = 1 - cosine(query_embedding, cached_emb)
            
            if similarity > best_score:
                best_score = similarity
                best_match = entry
                
        if best_score >= self.threshold:
            logging.info(f"[CACHE] Hit semántico! Similitud: {best_score:.3f}")
            return best_match['result']
            
        logging.info(f"[CACHE] Miss semántico. Mejor score: {best_score:.3f} < {self.threshold}")
        return None

    def store(self, query: str, result: dict):
        if not self.encoder:
            logging.warning("[CACHE] Encoder no disponible, omitiendo almacenamiento.")
            return
        embedding = self.encoder.encode(query).tolist()
        
        self.entries.append({
            "query": query,
            "embedding": embedding,
            "result": result
        })
        # Guardar en disco asíncronamente en un proxy real, aquí bloqueante ligero
        self.save_cache()
        logging.info(f"[CACHE] Nueva entrada almacenada: '{query[:30]}...'")

if __name__ == "__main__":
    cache = SemanticCache()
    # Sembrar la caché con un resultado real
    dummy_result = {"result": "0.5", "latex": "\\frac{1}{2}", "source": "Wolfram Alpha"}
    
    # query original exacta
    q1 = "Calcula la probabilidad de encontrar la particula en el centro del pozo para n=2"
    if not cache.check(q1):
        print("Guardando semilla...")
        cache.store(q1, dummy_result)
        
    # query variante semántica
    q2 = "¿Cual es la probabilidad de ubicar la particula a la mitad de un pozo infinito en su primer estado excitado n=2?"
    print(f"Probando variante: {q2}")
    
    match = cache.check(q2)
    if match:
        print(f"ÉXITO: Recuperado de caché ({match['latex']})")
    else:
        print("FALLO: La variante no alcanzó el umbral.")
