import fitz  # PyMuPDF
import os
import logging
from pathlib import Path

from galindo_page_map import resolve_galindo_reference

class ReferenceVisualizer:
    """
    Componente para extraer y gestionar imágenes de páginas del libro de texto (Galindo & Pascual).
    Permite una experiencia inmersiva al mostrar la referencia real citada.
    
    BUG FIX v5.4: output_dir ahora se resuelve siempre como ruta absoluta relativa
    a base_dir (o al directorio del PDF), apuntando a static_web/references.
    Esto asegura que RAGConnector y ReferenceVisualizer usen el mismo directorio.
    """
    def __init__(self, pdf_path: str, output_dir: str = None, max_cache_files: int = 50, base_dir: str = None):
        self.pdf_path = pdf_path
        self.max_cache_files = max_cache_files
        
        # Resolver ruta absoluta del directorio base
        if base_dir:
            _base = Path(base_dir)
        else:
            _base = Path(pdf_path).parent.absolute()
        
        # BUG FIX: Usar static_web/references como directorio canónico
        # (coincide con donde RAGConnector escanea las imágenes disponibles)
        if output_dir:
            self.output_dir = Path(output_dir) if Path(output_dir).is_absolute() else _base / output_dir
        else:
            self.output_dir = _base / "static_web" / "references"
        
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        if not os.path.exists(self.pdf_path):
            logging.error(f"[REF] PDF no encontrado en: {self.pdf_path}")
            self.pdf_exists = False
        else:
            self.pdf_exists = True
            logging.info(f"[REF] Visualizer vinculado a {os.path.basename(pdf_path)}, output_dir={self.output_dir} (Max cache: {max_cache_files})")

    def _cleanup_cache(self):
        """Mantiene el directorio de caché bajo el límite de archivos."""
        try:
            files = sorted(self.output_dir.glob("*.png"), key=lambda x: x.stat().st_mtime)
            if len(files) > self.max_cache_files:
                to_delete = files[:len(files) - self.max_cache_files]
                for f in to_delete:
                    f.unlink()
                    logging.info(f"[REF] Cache cleanup: {f.name} eliminado.")
        except Exception as e:
            logging.error(f"[REF] Error en cleanup de caché: {e}")

    def get_page_image(self, page_id: str | int, dpi: int = 150) -> str:
        """
        Extrae o resuelve una página/imagen y devuelve su ruta.
        Para el sistema RAG actual, resuelve la ruta en base a los identificadores string.
        """
        page_number = None

        if isinstance(page_id, int) or str(page_id).isdigit():
            resolved_ref = resolve_galindo_reference(display_page=page_id)
            page_number = resolved_ref["asset_page"]
            output_filename = resolved_ref["image_filename"]
        else:
            page_id_str = str(page_id)
            if not page_id_str.endswith(".png"):
                if page_id_str.startswith("cohen_") and not page_id_str.startswith("cohen_page_"):
                    output_filename = page_id_str.replace("cohen_", "cohen_page_") + ".png"
                elif page_id_str.startswith("sakurai_") and not page_id_str.startswith("sakurai_page_"):
                    output_filename = page_id_str.replace("sakurai_", "sakurai_page_") + ".png"
                elif page_id_str.startswith("page_"):
                    output_filename = f"{page_id_str}.png"
                    asset_token = page_id_str.replace("page_", "")
                    page_number = int(asset_token) if asset_token.isdigit() else None
                else:
                    output_filename = f"{page_id_str}.png"
            else:
                output_filename = page_id_str
                if page_id_str.startswith("page_"):
                    asset_token = page_id_str.replace("page_", "").replace(".png", "")
                    page_number = int(asset_token) if asset_token.isdigit() else None

        if not output_filename:
            return None

        output_path = self.output_dir / output_filename
        
        # Verificar caché / disco
        if output_path.exists():
            # Actualizar mtime para el algoritmo LRU/FIFO de cleanup
            output_path.touch()
            return str(output_path)
        
        if page_number is None:
            return None

        if not self.pdf_exists:
            return None

        if page_number <= 0:
            logging.warning(f"[REF] Número de página inválido: {page_number}")
            return None
        
        try:
            # Ejecutar limpieza antes de crear uno nuevo
            self._cleanup_cache()

            with fitz.open(self.pdf_path) as doc:
                pdf_index = page_number - 1 
                if pdf_index >= len(doc):
                    logging.warning(f"[REF] Pagina {page_number} fuera de rango (Total: {len(doc)})")
                    return None
                
                page = doc.load_page(pdf_index)
                zoom = dpi / 72
                mat = fitz.Matrix(zoom, zoom)
                pix = page.get_pixmap(matrix=mat)
                pix.save(str(output_path))
            
            logging.info(f"[REF] Pagina {page_number} extraida.")
            return str(output_path)
            
        except Exception as e:
            logging.error(f"[REF] Error extrayendo pagina {page_number}: {e}")
            return None

if __name__ == "__main__":
    # Test simple
    logging.basicConfig(level=logging.INFO)
    base = Path(__file__).parent.absolute()
    pdf = base / "wuolah-premium-Galindo-Pascual-Quantum-Mechanics-Vol-I.pdf"
    viz = ReferenceVisualizer(str(pdf))
    path = viz.get_page_image(47) # Inicio de Postulados
    if path:
        print(f"Página de prueba generada en: {path}")
    else:
        print("Fallo en la generación de prueba.")
