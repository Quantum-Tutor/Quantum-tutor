import logging
import time
import os

class MultimodalVisionParser:
    """
    Parser Multimodal v2.0 (Real OCR + Fallback Mock)
    Utiliza EasyOCR para extraer texto de imagenes reales de derivaciones manuscritas.
    Si no hay imagen real o EasyOCR falla, retorna datos de prueba para demo.
    """
    def __init__(self):
        self.supported_formats = ['.png', '.jpg', '.jpeg']
        self.reader = None
        self._load_ocr_engine()

    def _load_ocr_engine(self):
        try:
            import easyocr
            self.reader = easyocr.Reader(['en'], gpu=False, verbose=False)
            logging.info("[VISION] EasyOCR cargado exitosamente (CPU mode).")
        except ImportError:
            logging.warning("[VISION] EasyOCR no disponible. Usando mock data.")
        except Exception as e:
            logging.warning(f"[VISION] Error cargando EasyOCR: {e}. Usando mock data.")

    def parse_derivation_image(self, image_path: str) -> list[dict]:
        """
        Pipeline: Imagen -> OCR -> Matriz Estructurada de Pasos
        Si la imagen existe, usa EasyOCR real.
        Si no, retorna datos mock para demo.
        """
        logging.info(f"[VISION] Analizando imagen: {image_path}...")

        # Si la imagen real existe Y tenemos EasyOCR, usamos OCR real
        if self.reader and os.path.isfile(image_path):
            return self._real_ocr(image_path)

        # Fallback: mock data para demo y PoC
        return self._mock_ocr(image_path)

    def _real_ocr(self, image_path: str) -> list[dict]:
        """Extrae texto real de una imagen usando EasyOCR."""
        start = time.perf_counter()
        try:
            results = self.reader.readtext(image_path, detail=1)
            latency = time.perf_counter() - start
            logging.info(f"[VISION] OCR real completado en {latency:.2f}s. {len(results)} bloques detectados.")

            steps = []
            for i, (bbox, text, confidence) in enumerate(results):
                # Heuristicas simples para detectar posibles errores
                error_flag = False
                text_clean = text.strip()

                # Detectar signos sospechosos (error comun en MQ: signo invertido)
                if any(s in text_clean for s in ['-i', '- i', '-2i']) and confidence < 0.96:
                    error_flag = True

                steps.append({
                    "step": i + 1,
                    "latex": text_clean,
                    "confidence": round(confidence, 2),
                    "bbox": bbox,
                    "error_flag": error_flag
                })

            return steps if steps else self._mock_ocr(image_path)

        except Exception as e:
            logging.error(f"[VISION] Error en OCR real: {e}. Usando fallback.")
            return self._mock_ocr(image_path)

    def _mock_ocr(self, image_path: str) -> list[dict]:
        """Retorna datos simulados para demo."""
        time.sleep(0.5)  # Simular latencia reducida

        mock_ocr_extraction = [
            {"step": 1, "latex": "[x^2, p] = x[x, p] + [x, p]x", "confidence": 0.98},
            {"step": 2, "latex": "[x, p] = i\\hbar", "confidence": 0.99},
            {"step": 3, "latex": "x(i\\hbar) + (i\\hbar)x", "confidence": 0.97},
            {"step": 4, "latex": "-2i\\hbar x", "confidence": 0.95, "error_flag": True}
        ]

        logging.info(f"[VISION] Mock OCR para '{image_path}'. 4 pasos generados.")
        return mock_ocr_extraction


if __name__ == "__main__":
    parser = MultimodalVisionParser()

    # Test con mock (no hay imagen real)
    print("--- Test Mock OCR ---")
    result = parser.parse_derivation_image("student_upload_1.jpg")
    for step in result:
        flag = " [ERROR]" if step.get("error_flag") else ""
        print(f"  Paso {step['step']}: {step['latex']} (Conf: {step['confidence']}){flag}")

    print(f"\n[INFO] EasyOCR disponible: {'Si' if parser.reader else 'No'}")
    print("[INFO] Para test real, coloca una imagen .jpg/.png en esta carpeta y cambia el path.")
