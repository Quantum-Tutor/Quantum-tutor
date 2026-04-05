import os
import fitz  # PyMuPDF
import sys
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CohenIngest")

def extract_pdf_to_txt(pdf_path, output_txt_path):
    if not os.path.exists(pdf_path):
        logger.error(f"Archivo no encontrado: {pdf_path}")
        sys.exit(1)

    logger.info(f"Iniciando extracción de: {pdf_path}")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    logger.info(f"Total de páginas a procesar: {total_pages}")

    with open(output_txt_path, 'w', encoding='utf-8') as f:
        for i in range(total_pages):
            page = doc[i]
            text = page.get_text("text")

            # Marcador estructurado para el chunking de RAG
            f.write(f"\n\n## Pagina C_{i}\n")
            f.write(text)

            if i % 100 == 0 and i > 0:
                logger.info(f"  Procesado {i}/{total_pages} páginas...")

    logger.info(f"Extracción completada. Guardado en: {output_txt_path}")

if __name__ == "__main__":
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # El archivo está en la raíz de quantum_tutor
    pdf_path = os.path.join(base_dir, "Claude Cohen-Tannoudji.pdf")
    output_txt_path = os.path.join(base_dir, "cohen_tannoudji_full_ocr.txt")
    
    extract_pdf_to_txt(pdf_path, output_txt_path)
