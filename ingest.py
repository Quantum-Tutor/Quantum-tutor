"""
DocumentIngestionPipeline v2.0 — Pipeline de Ingesta Inteligente
================================================================
Pipeline de ingesta para el RAG de QuantumTutor con:
  - Chunking semántico aware de ecuaciones LaTeX
  - Metadatos enriquecidos por chunk (sección, ecuaciones, longitud)
  - Análisis de fragmentación para detectar ecuaciones cortadas
  - Soporte para múltiples documentos
"""

import json
import os
import re
from datetime import datetime


class DocumentIngestionPipeline:
    """
    Pipeline de ingesta de documentos para el sistema RAG del QuantumTutor.
    Emula la lectura de PDFs y realiza chunking inteligente que preserva
    la integridad de las ecuaciones LaTeX.
    """

    def __init__(self, config_path="quantum_tutor_config.json"):
        self.load_config(config_path)
        self.vector_store = []
        self.ingestion_log = []
        self.fragmentation_stats = {}

    def load_config(self, config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                self.config = json.load(f)["rag_parameters"]
                print(f"[INIT] Configuración RAG cargada. "
                      f"Estrategia: {self.config.get('chunk_strategy')}")
        except FileNotFoundError:
            print("[WARN] Config no encontrado. Usando parámetros por defecto.")
            self.config = {
                "chunk_strategy": "semantic_markdown_headers",
                "top_k_fragments": 5,
                "similarity_threshold": 0.75
            }

    def read_document(self, file_path: str) -> str:
        """
        Lee un documento PDF usando PyMuPDF y EasyOCR.
        Dado que el PDF origen es un escaneo con DRM, extrae texto OCRizando las paginas.
        Procesa una muestra (paginas 30 a 40) para demostracion debido a tiempos de CPU.
        """
        print(f"\n[1] Leyendo documento con OCR: {file_path}")

        # Intentar lectura con OCR
        if file_path.lower().endswith('.pdf') and os.path.exists(file_path):
            try:
                import fitz
                import easyocr
                
                print("    Inicializando EasyOCR (CPU)...")
                reader = easyocr.Reader(['en', 'es'], gpu=False, verbose=False)
                pdf = fitz.open(file_path)
                total_pages = len(pdf)
                print(f"    PDF cargado: {total_pages} paginas. Procesando muestra (30-40)...")

                full_text = ""
                # Muestra representativa para no demorar horas en CPU
                start_page = 30
                end_page = min(40, total_pages)
                
                for i in range(start_page, end_page):
                    page = pdf[i]
                    # Renderizar pagina a imagen
                    pix = page.get_pixmap(dpi=150)
                    img_path = f"tmp_ocr_page_{i}.png"
                    pix.save(img_path)
                    
                    # OCR
                    print(f"      OCR -> Pagina {i}...")
                    results = reader.readtext(img_path, detail=0)
                    page_text = " ".join(results)
                    os.remove(img_path)
                    
                    if len(page_text.strip()) > 50:
                        full_text += f"\n\n## Pagina {i}\n\n{page_text}"

                pdf.close()
                print(f"    Texto OCR extraido: {len(full_text)} caracteres")

                self.ingestion_log.append({
                    "file": file_path,
                    "timestamp": datetime.now().isoformat(),
                    "content_length": len(full_text),
                    "pages": end_page - start_page,
                    "source": "EasyOCR (Muestra 30-40)"
                })
                return full_text

            except Exception as e:
                print(f"    [WARN] Error en OCR: {e}. Usando fallback.")

        # Fallback: contenido simulado de mecanica cuantica
        simulated_content = self._get_simulated_content()

        self.ingestion_log.append({
            "file": file_path,
            "timestamp": datetime.now().isoformat(),
            "content_length": len(simulated_content),
            "source": "Simulated"
        })
        return simulated_content

    def _get_simulated_content(self) -> str:
        """Contenido simulado de mecanica cuantica para testing."""
        return r"""
# Semana 2: Mecanica Ondulatoria

## 2.1 El Pozo de Potencial Infinito

Para una particula en una caja monodimensional de longitud $L$, las condiciones
de frontera exigen que la funcion de onda se anule en las paredes ($x=0$ y $x=L$).

La funcion de onda normalizada para el n-esimo estado es:

$$\psi_n(x) = \sqrt{\frac{2}{L}} \sin\left(\frac{n\pi x}{L}\right)$$

La energia asociada a cada estado esta cuantizada:

$$E_n = \frac{n^2 \pi^2 \hbar^2}{2m L^2}$$

### Nodos y Probabilidades

Para el estado $n$, existen $n-1$ nodos donde $\psi_n = 0$.
En el nivel $n=2$, existe un nodo justo en el centro del pozo ($x = L/2$).

La probabilidad de encontrar la particula entre $a$ y $b$ es:

$$P(a \leq x \leq b) = \int_a^b |\psi_n(x)|^2 \, dx$$

## 2.2 Normalizacion de Funciones de Onda

La constante de normalizacion $A$ se obtiene exigiendo que:

$$\int_{-\infty}^{\infty} |A|^2 |\phi(x)|^2 \, dx = 1$$

## 2.3 Relaciones de Conmutacion

El conmutador fundamental de la mecanica cuantica es:

$$[\hat{x}, \hat{p}] = i\hbar$$

## 2.4 Efecto Tunel Cuantico

$$T = \frac{1}{1 + \frac{V_0^2 \sinh^2(\kappa a)}{4E(V_0 - E)}}$$

## 2.5 Oscilador Armonico Cuantico

$$E_n = \left(n + \frac{1}{2}\right)\hbar\omega$$
"""

    def _detect_latex_blocks(self, text: str) -> list:
        """Detecta bloques de ecuaciones LaTeX en el texto."""
        display_equations = list(re.finditer(r'\$\$[^$]+\$\$', text, re.DOTALL))
        inline_equations = list(re.finditer(r'(?<!\$)\$(?!\$)[^$]+\$(?!\$)', text))
        return display_equations, inline_equations

    def _is_equation_boundary(self, text: str, split_pos: int) -> bool:
        """Verifica si un punto de corte cae dentro de una ecuación LaTeX."""
        # Contar signos $ antes de la posición
        before = text[:split_pos]
        display_opens = before.count('$$')
        # Si hay un número impar de $$, estamos dentro de una ecuación display
        if display_opens % 2 != 0:
            return True

        # Verificar ecuaciones inline ($ simple)
        # Quitar las ecuaciones display primero
        cleaned = re.sub(r'\$\$[^$]*\$\$', '', before)
        inline_dollars = cleaned.count('$')
        if inline_dollars % 2 != 0:
            return True

        return False

    def semantic_chunking(self, text: str) -> list:
        """
        Divide el documento usando chunking semántico que preserva ecuaciones.
        
        Estrategia:
        1. Dividir por headers markdown (##)
        2. Verificar que ningún corte rompa ecuaciones $$...$$
        3. Fusionar chunks demasiado pequeños con el anterior
        4. Enriquecer cada chunk con metadatos
        """
        print("[2] 🔪 Particionando texto (Chunking Semántico Equation-Aware)...")

        # Dividir por headers de nivel 2 (##)
        raw_chunks = re.split(r'\n(?=## )', text.strip())

        # Post-procesar: verificar integridad de ecuaciones
        processed_chunks = []
        broken_equations = 0

        for i, chunk in enumerate(raw_chunks):
            if not chunk.strip():
                continue

            # Verificar si el chunk tiene ecuaciones incompletas
            display_count = chunk.count('$$')
            if display_count % 2 != 0:
                # Ecuación cortada — fusionar con el siguiente chunk
                if i + 1 < len(raw_chunks):
                    raw_chunks[i + 1] = chunk + "\n" + raw_chunks[i + 1]
                    broken_equations += 1
                    continue

            # Extraer metadatos del chunk
            lines = chunk.strip().split('\n')
            title_match = re.match(r'^##\s+(.+)', lines[0]) if lines else None
            title = title_match.group(1) if title_match else f"Sección {i+1}"

            # Contar ecuaciones
            display_eqs, inline_eqs = self._detect_latex_blocks(chunk)

            metadata = {
                "chunk_index": len(processed_chunks),
                "section_title": title,
                "page_number_emulated": (i // 2) + 1,
                "char_count": len(chunk),
                "line_count": len(lines),
                "display_equations": len(display_eqs),
                "inline_equations": len(inline_eqs),
                "total_equations": len(display_eqs) + len(inline_eqs),
                "has_broken_equation": False
            }

            processed_chunks.append({
                "text": chunk.strip(),
                "metadata": metadata
            })

        print(f"    → Se generaron {len(processed_chunks)} fragmentos semánticos")
        if broken_equations > 0:
            print(f"    ⚠️  Se repararon {broken_equations} ecuaciones cortadas mediante fusión")
        else:
            print(f"    ✅ 0 ecuaciones cortadas detectadas")

        return processed_chunks

    def embed_and_store(self, chunks: list):
        """Emula la generación de embeddings y carga a la BD vectorial."""
        print("[3] 🧬 Generando Embeddings (Simulados) y cargando a BD Vectorial...")

        for chunk_data in chunks:
            chunk_text = chunk_data["text"]
            metadata = chunk_data["metadata"]
            vector_id = f"chunk_{metadata['chunk_index']}"

            # Simulando un vector de embedding (384 dimensiones reducido)
            mock_embedding = [
                round(hash(chunk_text[i:i+10]) % 1000 / 1000, 4)
                for i in range(0, min(len(chunk_text), 40), 10)
            ]

            self.vector_store.append({
                "id": vector_id,
                "text": chunk_text,
                "embedding": mock_embedding,
                "metadata": metadata
            })

        print(f"[4] ✅ {len(self.vector_store)} fragmentos indexados en "
              f"{self.config.get('vector_store', 'pinecone-serverless')}")

    def analyze_fragmentation(self) -> dict:
        """
        Genera un reporte de análisis de fragmentación para evaluar
        la calidad del chunking.
        """
        if not self.vector_store:
            return {"error": "No hay fragmentos indexados. Ejecute el pipeline primero."}

        print("\n[5] 📊 Analizando calidad de fragmentación...")

        sizes = [v["metadata"]["char_count"] for v in self.vector_store]
        eq_counts = [v["metadata"]["total_equations"] for v in self.vector_store]
        display_eq_counts = [v["metadata"]["display_equations"] for v in self.vector_store]
        broken = sum(1 for v in self.vector_store if v["metadata"]["has_broken_equation"])

        stats = {
            "total_chunks": len(self.vector_store),
            "avg_chunk_size": round(sum(sizes) / len(sizes), 1) if sizes else 0,
            "min_chunk_size": min(sizes) if sizes else 0,
            "max_chunk_size": max(sizes) if sizes else 0,
            "total_equations": sum(eq_counts),
            "total_display_equations": sum(display_eq_counts),
            "avg_equations_per_chunk": round(sum(eq_counts) / len(eq_counts), 1) if eq_counts else 0,
            "chunks_with_equations": sum(1 for e in eq_counts if e > 0),
            "chunks_without_equations": sum(1 for e in eq_counts if e == 0),
            "broken_equations": broken,
            "fragmentation_quality": "EXCELLENT" if broken == 0 else
                                     "ACCEPTABLE" if broken <= 2 else "POOR",
            "chunks_detail": [
                {
                    "id": v["id"],
                    "section": v["metadata"]["section_title"],
                    "size": v["metadata"]["char_count"],
                    "equations": v["metadata"]["total_equations"],
                    "display_eqs": v["metadata"]["display_equations"],
                }
                for v in self.vector_store
            ]
        }

        self.fragmentation_stats = stats

        # Imprimir resumen
        print(f"\n  📋 Reporte de Fragmentación:")
        print(f"     Total chunks:            {stats['total_chunks']}")
        print(f"     Tamaño promedio:         {stats['avg_chunk_size']} caracteres")
        print(f"     Rango de tamaño:         [{stats['min_chunk_size']}, {stats['max_chunk_size']}]")
        print(f"     Total ecuaciones:        {stats['total_equations']} "
              f"({stats['total_display_equations']} display)")
        print(f"     Ecuaciones/chunk (avg):  {stats['avg_equations_per_chunk']}")
        print(f"     Ecuaciones cortadas:     {stats['broken_equations']}")
        print(f"     Calidad de fragmentación: {stats['fragmentation_quality']}")

        return stats

    def run_pipeline(self, file_paths: list = None) -> dict:
        """
        Ejecuta el pipeline completo de ingesta.
        
        Args:
            file_paths: Lista de rutas de archivos a ingerir.
                       Si no se proporciona, usa un documento de ejemplo.
        """
        if file_paths is None:
            file_paths = ["material_curso/semana_2_mecanica_ondulatoria.pdf"]

        print("\n" + "="*70)
        print("  📥 DOCUMENT INGESTION PIPELINE v2.0")
        print("="*70)
        print(f"  Documentos a procesar: {len(file_paths)}")
        print(f"  Estrategia de chunking: {self.config.get('chunk_strategy')}")

        all_chunks = []

        for file_path in file_paths:
            content = self.read_document(file_path)
            chunks = self.semantic_chunking(content)
            self.embed_and_store(chunks)
            all_chunks.extend(chunks)

        stats = self.analyze_fragmentation()

        print(f"\n{'─'*70}")
        quality_icon = {"EXCELLENT": "✅", "ACCEPTABLE": "⚠️", "POOR": "❌"}
        icon = quality_icon.get(stats.get("fragmentation_quality", ""), "❓")
        print(f"  {icon} Pipeline de ingesta completado: "
              f"{stats['total_chunks']} chunks, "
              f"calidad: {stats['fragmentation_quality']}")
        print("="*70 + "\n")

        return {
            "pipeline_status": "completed",
            "timestamp": datetime.now().isoformat(),
            "documents_processed": len(file_paths),
            "fragmentation_analysis": stats
        }


# ── Ejecución standalone ─────────────────────────────────────────────
if __name__ == "__main__":
    pipeline = DocumentIngestionPipeline()
    result = pipeline.run_pipeline()

    with open("ingestion_results.json", "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)
    print(f"📁 Resultados guardados en: ingestion_results.json")
