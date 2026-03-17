import json
import logging
import numpy as np
from sentence_transformers import SentenceTransformer
from scipy.spatial.distance import cosine

class SemanticCache:
    """
    Caché Semántica Dinámica v2.0
    Almacena consultas de Wolfram ya resueltas y utiliza embeddings para recuperar resultados
    ante variaciones de fraseo (ej. "probabilidad centro pozo" vs "integral pozo medio").
    """
    def __init__(self, cache_file='semantic_cache.json', threshold=0.70):
        self.cache_file = cache_file
        self.threshold = threshold
        self.entries = []
        
        # Usar un modelo muy ligero y rápido para embeddings en memoria
        logging.info("[CACHE] Cargando modelo de embeddings semánticos (all-MiniLM)...")
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')
        self.load_cache()

    def load_cache(self):
        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                self.entries = data.get("entries", [])
            logging.info(f"[CACHE] Cargadas {len(self.entries)} entradas semánticas.")
        except FileNotFoundError:
            self.entries = []
            
    def save_cache(self):
        with open(self.cache_file, 'w', encoding='utf-8') as f:
            # Los embeddings no son serializables directamente por JSON, los guardamos como listas
            json.dump({"entries": self.entries}, f, indent=4)

    def check(self, query: str):
        if not self.entries:
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
