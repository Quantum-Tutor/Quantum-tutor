import logging
import time
import os
import json
import google.genai as genai
from google.genai import types
from dotenv import load_dotenv
from quantum_tutor_runtime import DEFAULT_VISION_MODEL

load_dotenv()

class MultimodalVisionParser:
    """
    Parser multimodal del runtime actual
    Utiliza el modelo de visión configurado para razonamiento visual sobre derivaciones.
    Detecta pasos matemáticos y errores conceptuales directamente desde la imagen.
    """
    def __init__(self, model_name=DEFAULT_VISION_MODEL):
        self.supported_formats = ['.png', '.jpg', '.jpeg']
        raw_keys = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
        self.api_key = next((key.strip() for key in raw_keys.split(",") if key.strip()), "")
        self.model_name = model_name
        self.client = None
        
        if self.api_key:
            try:
                self.client = genai.Client(api_key=self.api_key)
                logging.info(f"[VISION] Gemini Vision API inicializada ({self.model_name}).")
            except Exception as e:
                logging.error(f"[VISION] Error inicializando Gemini Client: {e}")
        else:
            logging.warning("[VISION] No se encontraron claves Gemini. El parser funcionará en modo Mock.")

    def parse_derivation_image(self, image_path: str) -> list[dict]:
        """
        Pipeline: Imagen -> Gemini Vision -> Estructura de Pasos (JSON).
        """
        abs_path = os.path.abspath(image_path)
        logging.info(f"[VISION] Analizando imagen multimodal: {abs_path}...")

        if self.client and os.path.isfile(abs_path):
            return self._gemini_vision_analysis(abs_path)

        # SECURITY/INTEGRITY: no fabricar feedback visual cuando el servicio no está disponible.
        logging.warning(f"[VISION] Degraded: sin cliente API o imagen no encontrada para '{abs_path}'.")
        return self._degraded_response(abs_path)

    def _gemini_vision_analysis(self, image_path: str) -> list[dict]:
        """Análisis de visión optimizado con detección de MIME y reintentos."""
        start = time.perf_counter()
        ext = os.path.splitext(image_path)[1].lower()
        mime_type = "image/png" if ext == ".png" else "image/jpeg"

        prompt = """
        Analiza la imagen de física cuántica.
        Si es irrelevante, devuelve []. 
        Si es una derivación, devuelve una lista JSON con: step, latex, description, confidence, error_flag, error_reason.
        """

        try:
            with open(image_path, "rb") as f:
                image_bytes = f.read()
            
            response_text = ""
            for attempt in range(2):
                try:
                    res = self.client.models.generate_content(
                        model=self.model_name,
                        contents=[prompt, types.Part.from_bytes(data=image_bytes, mime_type=mime_type)],
                        config=types.GenerateContentConfig(response_mime_type="application/json", temperature=0.1)
                    )
                    response_text = res.text
                    break
                except Exception as api_err:
                    if attempt == 1: raise api_err
                    time.sleep(1)

            steps = json.loads(response_text)
            logging.info(f"[VISION] Análisis completado en {time.perf_counter()-start:.2f}s.")
            return steps

        except Exception as e:
            logging.error(f"[VISION] Error en Gemini Vision: {e}")
            # INTEGRITY: degradar honestamente en lugar de servir datos fabricados.
            return self._degraded_response(image_path)

    def _degraded_response(self, image_path: str) -> list[dict]:
        """Respuesta honesta de degradación: no fabrica datos de análisis."""
        logging.warning(f"[VISION] Modo degradado activado para '{image_path}'. Devolviendo señal de indisponibilidad.")
        return [{
            "step": 0,
            "latex": "",
            "description": "Análisis visual no disponible.",
            "confidence": 0.0,
            "error_flag": True,
            "error_reason": (
                "El servicio de visión Gemini no está disponible en este momento. "
                "Por favor, describe tu derivación manualmente en el chat para recibir "
                "asistencia socática sin necesidad de imagen."
            )
        }]


if __name__ == "__main__":
    # Prueba rápida de integración
    logging.basicConfig(level=logging.INFO)
    parser = MultimodalVisionParser()
    
    print("\n--- Test Multimodal Vision (Modo Mock/Real) ---")
    # Intentar con una ruta inexistente para ver el fallback
    result = parser.parse_derivation_image("no_existe.jpg")
    for step in result:
        err = f" [ERROR: {step.get('error_reason', 'N/A')}]" if step.get("error_flag") else ""
        print(f"Paso {step['step']}: {step['latex']}{err}")
