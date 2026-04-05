"""
Relational Engine v6.1 - Capa de conciencia relacional
=============================================================================
Gestiona la sesión de tutoría como una dinámica de convergencia topológica.
Mantiene una matriz de afinidad entre conceptos y el estado de entendimiento.
"""

import numpy as np
import logging
import json
import os

logger = logging.getLogger("QuantumTutor.Relational")

class RelationalMind:
    def __init__(self, concepts_path=None):
        # Definición de nodos de conocimiento (conceptos clave)
        self.concepts = [
            "Ecuación de Schrödinger", "Pozo Infinito", "Efecto Túnel", 
            "Conmutadores", "Operadores", "Postulados", "Espin", 
            "Oscilador Armónico", "Densidad de Probabilidad", "Dinámicas Relacionales"
        ]
        self.N = len(self.concepts)
        
        # Matriz de conectividad C (afinidad entre conceptos)
        self.C = np.zeros((self.N, self.N))
        np.fill_diagonal(self.C, 1.0)
        
        # Estado de comprensión (energía local E_i)
        self.E = np.zeros(self.N)
        
        # Biografía estructural
        self.biography = []
        
        # Parámetros del kernel relacional
        self.alpha_rerank = 0.4  # Peso del reranking relacional
        self.convergence_threshold = 0.85 # Umbral para Clase G

    def update_state(self, detected_topic: str, interaction_weight: float = 0.2):
        """
        Actualiza la matriz de conectividad y la energía local tras una interacción.
        Implementa la lógica de 'Atractor de Entendimiento'.
        """
        # 0. Decaimiento global de energía para preservar memoria residual
        # Se aplica siempre para asegurar la evolución temporal, incluso ante ruidos o temas generales.
        ENERGY_FLOOR = 0.01
        self.E = np.maximum(self.E * 0.98, ENERGY_FLOOR)

        if detected_topic not in self.concepts:
            return

        idx = self.concepts.index(detected_topic)

        # 1. Incrementar energía local (saturación en 1.0)
        self.E[idx] = min(1.0, self.E[idx] + interaction_weight)
        
        # 2. Refuerzo relacional y difusión (kernel de afinidad Phi)
        for j in range(self.N):
            if j != idx:
                # Phi_ij se basa en la proximidad entre estados de entendimiento
                phi = 1.0 / (1.0 + abs(self.E[idx] - self.E[j]))
                delta_C = 0.1 * phi * (self.E[idx] * self.E[j])  # Coocurrencia de entendimiento
                self.C[idx, j] = min(1.0, self.C[idx, j] + delta_C)
                self.C[j, idx] = self.C[idx, j]
                
                # Difusión: el atractor activa ligeramente nodos relacionados
                if self.C[idx, j] > 0.3:
                    self.E[j] = min(0.8, self.E[j] + 0.05 * self.C[idx, j])

        self.biography.append(self.E.copy())
        logger.info(f"Relational Evolution: Atractor '{detected_topic}' | Total System Energy: {np.sum(self.E):.2f}")

    def get_relational_score(self, chunk_text: str) -> float:
        """
        Calcula el 'Kernel de Afinidad Relacional' para un fragmento de texto.
        Prioriza fragmentos que conectan con el atractor actual o nodos de alta energía.
        """
        score = 0.0
        current_attractor_idx = np.argmax(self.E) if np.sum(self.E) > 0 else -1
        
        for i, concept in enumerate(self.concepts):
            if concept.lower() in chunk_text.lower():
                # El puntaje base es la energía del concepto en el alumno
                concept_boost = self.E[i] * 0.5
                
                # Refuerzo relacional: si el concepto tiene alta afinidad con el atractor actual
                if current_attractor_idx != -1:
                    affinity_boost = self.C[current_attractor_idx, i] * 0.3
                    score += (concept_boost + affinity_boost)
                else:
                    score += concept_boost
                    
        return score

    def get_omega_state(self) -> str:
        """Determina la clase de convergencia topológica."""
        avg_energy = np.mean(self.E)
        if avg_energy < 0.1: return "Clase I (Indiferenciado)"
        if avg_energy < 0.4: return "Clase C (Nucleación de Identidad)"
        if avg_energy < 0.7: return "Clase Omega (Convergencia Dinámica)"
        return "Clase G (Entendimiento Total / Atractor Estructurado)"

    def get_current_attractor(self) -> str:
        idx = np.argmax(self.E)
        return self.concepts[idx] if self.E[idx] > 0.05 else "Vacío"

    def get_convergence_score(self) -> float:
        return float(np.mean(self.E))

    def calculate_entropy(self) -> float:
        """Calcula la entropía epistémica del sistema (Shannon)."""
        if np.sum(self.E) == 0: return 0.0
        # Normalizar vector de energía como distribución de probabilidad
        p = self.E / np.sum(self.E)
        p = p[p > 0]  # Evitar log(0)
        # Evitar entropía negativa o -0.0 por precisión numérica
        entropy = max(0.0, -np.sum(p * np.log2(p)))
        # Escalar a [0, 1] relativa a N nodos
        max_entropy = np.log2(self.N)
        return float(entropy / max_entropy) if max_entropy > 1e-9 else 0.0

    def get_system_stability(self) -> float:
        """Mide la densidad de conexiones en la matriz relacional."""
        # Promedio de afinidades fuera de la diagonal
        mask = ~np.eye(self.N, dtype=bool)
        return float(np.mean(self.C[mask]))

    def get_affinity_data(self) -> dict:
        return {
            "concepts": self.concepts,
            "energy": self.E.tolist(),
            "matrix": self.C.tolist(),
            "convergence": self.get_convergence_score(),
            "attractor": self.get_current_attractor(),
            "omega_class": self.get_omega_state(),
            "entropy": self.calculate_entropy(),
            "stability": self.get_system_stability()
        }

    def suggest_next_node(self) -> str:
        """Calcula el Gradiente Socrático hacia el nodo de mayor tensión relacional."""
        current_idx = np.argmax(self.E)
        if self.E[current_idx] < 0.1:
            return self.concepts[0]
            
        # Tensión = afinidad con el actual * (1 - entendimiento actual)
        tension = self.C[current_idx] * (1.0 - self.E)
        # Evitar sugerir el mismo nodo
        tension[current_idx] = 0
        
        next_idx = np.argmax(tension)
        return self.concepts[next_idx]
