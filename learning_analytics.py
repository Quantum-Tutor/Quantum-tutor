import json
import os
import logging
from pathlib import Path

from quantum_tutor_paths import STUDENT_PROFILE_PATH, resolve_runtime_path, write_json_atomic

class LearningAnalytics:
    """
    Analítica de Aprendizaje del runtime actual
    Rastrea el desempeño y los errores del estudiante para generar un perfil cognitivo.
    Se usa para el andamiaje dinámico y el ajuste del nivel socrático.
    """
    def __init__(self, db_path=STUDENT_PROFILE_PATH):
        _base_dir = Path(os.path.abspath(__file__)).parent
        if isinstance(db_path, Path):
            self.db_path = db_path
        elif os.path.isabs(db_path):
            self.db_path = Path(db_path)
        else:
            # Resolución robusta de rutas
            self.db_path = _base_dir / db_path
        if self.db_path == STUDENT_PROFILE_PATH:
            self.db_path = resolve_runtime_path(STUDENT_PROFILE_PATH, "student_profile.json")
        self.profile = self._load_profile()
        self.plateau_threshold = 2  # Turnos consecutivos de bloqueo alto
        
    def _load_profile(self) -> dict:
        if self.db_path.exists():
            try:
                with self.db_path.open('r', encoding='utf-8') as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        return data
            except Exception as e:
                logging.error(f"Error cargando perfil: {e}")
        return {"topics": {}, "global_score": 0.0, "total_queries": 0}
        
    def _save_profile(self):
        write_json_atomic(self.db_path, self.profile, indent=4)
            
    def log_interaction(self, topic: str, wolfram_invoked: bool, passed_socratic: bool):
        """ Registra una interacción en el perfil cognitivo del estudiante. """
        self.profile["total_queries"] = self.profile.get("total_queries", 0) + 1
        
        topics = self.profile.get("topics", {})
        if topic not in topics:
            topics[topic] = {
                "queries": 0,
                "struggle_index": 0.0,  # 0.0 = dominio, 1.0 = bloqueo alto
                "wolfram_reliance": 0,
                "consecutive_struggle": 0  # Seguimiento de plateaus
            }
        self.profile["topics"] = topics
            
        t_data = topics[topic]
        t_data["queries"] = t_data.get("queries", 0) + 1
        if wolfram_invoked: 
            t_data["wolfram_reliance"] = t_data.get("wolfram_reliance", 0) + 1
        
        # Heurística de bloqueo optimizada
        struggle_delta = 0.15 if not passed_socratic else -0.08
        t_data["struggle_index"] = max(0.0, min(1.0, t_data["struggle_index"] + struggle_delta))
        
        # Actualización de plateau cognitivo
        if t_data["struggle_index"] > 0.6:
            t_data["consecutive_struggle"] += 1
        else:
            t_data["consecutive_struggle"] = 0
        
        self._recalculate_global()
        self._save_profile()
        logging.info(f"[ANALYTICS] Progreso actualizado. {topic} struggle: {t_data['struggle_index']:.2f}")

    def _recalculate_global(self):
        if not self.profile["topics"]: return
        avg_struggle = sum(t["struggle_index"] for t in self.profile["topics"].values()) / len(self.profile["topics"])
        self.profile["global_mastery"] = 1.0 - avg_struggle

    def get_summary(self):
        return self.profile

    def get_scaffolding_level(self, topic: str = None) -> dict:
        """
        Calcula el nivel de dificultad socrática
        basado en el perfil cognitivo del estudiante.
        
        Retorna:
            Un dict con `level`, `label` y `modifier`.
        """
        # Determinar el struggle relevante
        if topic and topic in self.profile["topics"]:
            struggle = self.profile["topics"][topic]["struggle_index"]
        else:
            # Usar el promedio global
            topics = self.profile.get("topics", {})
            if not topics:
                return {"level": 2, "label": "Intermedio", "modifier": ""}
            struggle = sum(t["struggle_index"] for t in topics.values()) / len(topics)

        is_plateau = self.is_on_plateau(topic) if topic else False

        if struggle >= 0.5 or is_plateau:
            label = "Plateau Cognitivo" if is_plateau else "Guiado"
            plateau_instruction = (
                "¡ALERTA DE PLATEAU! El estudiante está bloqueado. "
                "Cambia radicalmente el ángulo pedagógico: usa una analogía del mundo real "
                "o sugiere pasar a un tema relacionado antes de volver a este."
            ) if is_plateau else ""

            return {
                "level": 1,
                "label": label,
                "modifier": (
                    f"{plateau_instruction} "
                    "El estudiante presenta dificultades significativas. "
                    "Aplica el modo guiado de nivel 1: Proporciona el razonamiento integral "
                    "y la derivación paso a paso de forma directa. No hagas preguntas "
                    "durante la explicación. Solo al final, propone una reflexión "
                    "sobre el punto más crítico del concepto."
                )
            }
        elif struggle >= 0.2:
            return {
                "level": 2,
                "label": "Razonamiento Guiado",
                "modifier": (
                    "El estudiante tiene una base razonable. "
                    "Aplica el modo guiado de nivel 2: Expón la teoría y el cálculo "
                    "con rigor absoluto y fluidez. Evita el método socrático durante "
                    "el análisis. Concluye con una pregunta de reflexión lateral "
                    "para verificar el anclaje del conocimiento."
                )
            }
        else:
            return {
                "level": 3,
                "label": "Maestría Integral",
                "modifier": (
                    "El estudiante domina este tema. "
                    "Aplica el modo avanzado de nivel 3: Profundiza en implicaciones "
                    "avanzadas y conexiones interdisciplinarias de forma directa. "
                    "Desafía su comprensión solo en la reflexión final con un "
                    "experimento mental o un caso límite extremo."
                )
            }

    def get_misconception_clusters(self):
        """
        Agrupa los tópicos en clusters de malentendidos basados en las métricas.
        """
        clusters = {
            "Error_Calculo": [],       # Alta dependencia de Wolfram, bajo esfuerzo socrático
            "Error_Conceptual": [],    # Baja dependencia de Wolfram, alto esfuerzo socrático
            "Falla_Base": [],          # Alta dependencia y alto esfuerzo
            "Dominado": []             # Baja dependencia y bajo esfuerzo
        }
        
        for topic, data in self.profile["topics"].items():
            if data["queries"] < 1:
                continue
                
            high_struggle = data["struggle_index"] > 0.3
            high_wolfram = (data["wolfram_reliance"] / data["queries"]) >= 0.5
            
            if high_struggle and high_wolfram:
                clusters["Falla_Base"].append(topic)
            elif high_struggle and not high_wolfram:
                clusters["Error_Conceptual"].append(topic)
            elif not high_struggle and high_wolfram:
                clusters["Error_Calculo"].append(topic)
            else:
                clusters["Dominado"].append(topic)
                
        return clusters

    def is_on_plateau(self, topic: str) -> bool:
        """Retorna True si el tópico está en un plateau de estancamiento."""
        if topic not in self.profile["topics"]: return False
        return self.profile["topics"][topic].get("consecutive_struggle", 0) >= self.plateau_threshold

    def get_content_heatmap(self):
        """
        Genera un mapa de calor ordenado de los temas de mayor fricción cognitiva.
        """
        if not self.profile["topics"]: return []
        
        heatmap = [
            {"topic": topic, "struggle_index": round(data["struggle_index"], 2), "queries": data["queries"]}
            for topic, data in self.profile["topics"].items()
        ]
        return sorted(heatmap, key=lambda x: x["struggle_index"], reverse=True)

if __name__ == "__main__":
    analytics = LearningAnalytics('test_profile.json')
    # Simulando Dominado (Pozo Infinito n=2, resuelve tras fallo leve o nulo)
    analytics.log_interaction("Pozo Infinito", wolfram_invoked=True, passed_socratic=True)
    analytics.log_interaction("Pozo Infinito", wolfram_invoked=False, passed_socratic=True)
    
    # Simulando Falla Base (Efecto Túnel, usa Wolfram siempre y falla siempre lo conceptual)
    analytics.log_interaction("Efecto Túnel", wolfram_invoked=True, passed_socratic=False)
    analytics.log_interaction("Efecto Túnel", wolfram_invoked=True, passed_socratic=False)
    
    # Simulando Error Conceptual (Espín, no usa Wolfram pero falla el Socrático)
    analytics.log_interaction("Espín", wolfram_invoked=False, passed_socratic=False)
    analytics.log_interaction("Espín", wolfram_invoked=False, passed_socratic=False)
    
    print("\n--- Cognitive Profile Summary ---")
    print(json.dumps(analytics.get_summary(), indent=2))
    
    print("\n--- Misconception Clusters ---")
    print(json.dumps(analytics.get_misconception_clusters(), indent=2))
    
    print("\n--- Content Heatmap ---")
    print(json.dumps(analytics.get_content_heatmap(), indent=2))
    
    if os.path.exists('test_profile.json'): os.remove('test_profile.json')
