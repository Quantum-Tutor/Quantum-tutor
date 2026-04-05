"""
Batch Ingestion Pipeline (OCR CPU Mode)
Procesa libros escaneados completos utilizando PyMuPDF + EasyOCR.
Dado el tiempo de procesamiento en CPU (~1-2 minutos por página),
este script incluye checkpointing para guardar el progreso y
permitir pausar/reanudar el proceso.
"""
import fitz
import easyocr
import json
import time
from datetime import datetime
from pathlib import Path

from quantum_tutor_paths import OCR_BATCH_CHECKPOINT_PATH, ensure_output_dirs

# Archivos y rutas
BASE_DIR = Path(__file__).resolve().parent
PDF_PATH = BASE_DIR / "books" / "wuolah-premium-Galindo-Pascual-Quantum-Mechanics-Vol-I.pdf"
CHECKPOINT_FILE = OCR_BATCH_CHECKPOINT_PATH
OCR_OUTPUT_PATH = BASE_DIR / "galindo_pascual_full_ocr.txt"

def load_checkpoint():
    ensure_output_dirs()
    if CHECKPOINT_FILE.exists():
        with CHECKPOINT_FILE.open('r', encoding='utf-8') as f:
            return json.load(f)
    return {
        "last_page_processed": -1,
        "extracted_text": "",
        "start_time": datetime.now().isoformat()
    }

def save_checkpoint(last_page, current_text):
    ensure_output_dirs()
    data = {
        "last_page_processed": last_page,
        "extracted_text": current_text,
        "last_updated": datetime.now().isoformat()
    }
    with CHECKPOINT_FILE.open('w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def run_batch_ocr():
    ensure_output_dirs()
    print("="*60)
    print("  BATCH OCR PIPELINE — Galindo & Pascual Vol I")
    print("="*60)
    
    import torch
    is_cuda = torch.cuda.is_available()
    print(f"[INFO] CUDA Disponible: {is_cuda}")
    if not is_cuda:
        print("[WARN] Ejecutando en CPU. Esto tomará aproximadamente 7 horas.")
        print("[INFO] El progreso se guardará cada 5 páginas.")

    reader = easyocr.Reader(['en', 'es'], gpu=is_cuda, verbose=False)
    pdf = fitz.open(str(PDF_PATH))
    total_pages = len(pdf)
    
    checkpoint = load_checkpoint()
    start_page = checkpoint["last_page_processed"] + 1
    full_text = checkpoint["extracted_text"]
    
    if start_page >= total_pages:
        print("[OK] El documento ya fue procesado completamente.")
        return

    print(f"[+] Reanudando desde la página {start_page} de {total_pages}...")
    last_completed_page = start_page - 1
    
    try:
        for i in range(start_page, total_pages):
            start_time = time.perf_counter()
            page = pdf[i]
            pix = page.get_pixmap(dpi=150)  # Resolución optimizada para OCR
            img_path = BASE_DIR / f"tmp_batch_page_{i}.png"
            pix.save(str(img_path))
            
            results = reader.readtext(str(img_path), detail=0)
            page_text = " ".join(results)
            if img_path.exists():
                img_path.unlink()
            
            if len(page_text.strip()) > 50:
                full_text += f"\n\n## Pagina {i}\n\n{page_text}"
                
            elapsed = time.perf_counter() - start_time
            last_completed_page = i
            print(f"  -> Página {i}/{total_pages} completada en {elapsed:.1f}s")
            
            # Guardar checkpoint cada 5 páginas
            if i % 5 == 0:
                save_checkpoint(i, full_text)
                print(f"     [+] Checkpoint guardado (Página {i})")
                
    except KeyboardInterrupt:
        print("\n[!] Proceso interrumpido por el usuario.")
        save_checkpoint(last_completed_page, full_text)
        print(f"[+] Progreso guardado hasta la página {last_completed_page}. Puedes reanudar luego.")
        return
        
    save_checkpoint(total_pages - 1, full_text)
    
    # Al finalizar, guardar todo en un TXT final
    with OCR_OUTPUT_PATH.open('w', encoding='utf-8') as f:
        f.write(full_text)
        
    print("\n" + "="*60)
    print(f"  [OK] PROCESAMIENTO COMPLETADO")
    print(f"  Texto final guardado en: {OCR_OUTPUT_PATH}")
    print("="*60)
    
    # Automáticamente disparar la indexación al RAG
    print("\n[+] Indexando el texto completo en el Vector Store...")
    from rag_engine import RAGConnector
    rag = RAGConnector()
    rag._ingest_content(full_text)
    stats = rag.get_stats()
    print(f"  -> Indexados {stats['total_chunks']} chunks. Listo para el tutor.")

if __name__ == "__main__":
    run_batch_ocr()
