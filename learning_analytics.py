import json
import os
import logging

class LearningAnalytics:
    """
    Analítica de Aprendizaje v2.0 (Skeleton)
    Rastrea el desempeño y los errores del estudiante para generar un Cognitive Profile.
    Usado para el Dynamic Scaffolding (ajuste del nivel socrático).
    """
    def __init__(self, db_path='student_profile.json'):
        self.db_path = db_path
        self.profile = self._load_profile()
        
    def _load_profile(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {"topics": {}, "global_score": 0.0, "total_queries": 0}
        
    def _save_profile(self):
        with open(self.db_path, 'w', encoding='utf-8') as f:
            json.dump(self.profile, f, indent=4)
            
    def log_interaction(self, topic: str, wolfram_invoked: bool, passed_socratic: bool):
        """ Registra una interacción en el perfil cognitivo del estudiante. """
        self.profile["total_queries"] += 1
        
        if topic not in self.profile["topics"]:
            self.profile["topics"][topic] = {
                "queries": 0,
                "struggle_index": 0.0, # 0.0 = Master, 1.0 = High Struggle
                "wolfram_reliance": 0
            }
            
        t_data = self.profile["topics"][topic]
        t_data["queries"] += 1
        if wolfram_invoked: t_data["wolfram_reliance"] += 1
        
        # Heurística simple de Struggle (mayor si necesita Wolfram constante o falla heurística socrática)
        struggle_delta = 0.1 if not passed_socratic else -0.05
        t_data["struggle_index"] = max(0.0, min(1.0, t_data["struggle_index"] + struggle_delta))
        
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
        Dynamic Scaffolding: Calcula el nivel de dificultad socratica
        basado en el perfil cognitivo del estudiante.
        
        Returns:
            dict con level (1-3), label, y system_prompt_modifier
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

        if struggle >= 0.5:
            return {
                "level": 1,
                "label": "Guiado",
                "modifier": (
                    "El estudiante esta luchando con este concepto. "
                    "Usa un enfoque MUY guiado: da pistas directas, "
                    "descompone el problema en pasos pequenos, y valida "
                    "cada micro-avance antes de continuar. "
                    "Evita preguntas demasiado abiertas."
                )
            }
        elif struggle >= 0.2:
            return {
                "level": 2,
                "label": "Intermedio",
                "modifier": (
                    "El estudiante tiene una base razonable. "
                    "Usa el metodo socratico clasico: haz preguntas "
                    "que lo guien a descubrir la respuesta por si mismo, "
                    "pero ofrece pistas si se atasca mas de 2 turnos."
                )
            }
        else:
            return {
                "level": 3,
                "label": "Autonomo",
                "modifier": (
                    "El estudiante domina este tema. "
                    "Desafia su comprension con contraejemplos, "
                    "casos limite y conexiones con otros fenomenos cuanticos. "
                    "No des pistas a menos que las pida explicitamente."
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

