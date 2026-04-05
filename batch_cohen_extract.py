import os
import fitz
import time

PDF_PATH = "Claude Cohen-Tannoudji.pdf"
OUT_DIR = "static_web/references"
TXT_OUT = "cohen_tannoudji_full_ocr.txt"

os.makedirs(OUT_DIR, exist_ok=True)

print(f"Abriendo PDF: {PDF_PATH}")
doc = fitz.open(PDF_PATH)
total = len(doc)

full_text = ""

print("Iniciando escaneo de texto e imagenes (PyMuPDF Nativo). Esto sera rapido...")
start_time = time.time()

for i in range(total):
    page = doc[i]
    text = page.get_text("text")
    full_text += f"\n\n## Pagina C_{i}\n\n{text}"
    
    # Extraer imagen y guardarla con prefijo cohen_
    pix = page.get_pixmap(dpi=150)
    img_path = os.path.join(OUT_DIR, f"cohen_page_{i}.png")
    pix.save(img_path)
    
    if i % 50 == 0 and i > 0:
        print(f"  -> Procesadas {i}/{total} paginas...")

with open(TXT_OUT, 'w', encoding='utf-8') as f:
    f.write(full_text)

elapsed = time.time() - start_time
print("\n" + "="*60)
print(f"[OK] PROCESAMIENTO COMPLETADO en {elapsed:.1f} segundos.")
print(f"Texto guardado en: {TXT_OUT}")
print(f"Imagenes guardadas en: {OUT_DIR}/cohen_page_*.png")
print("="*60)

# Inject into vector store if possible
try:
    from rag_engine import RAGConnector
    print("\n[+] Re-indexando el RAG con los nuevos contenidos...")
    rag = RAGConnector()
    stats = rag.get_stats()
    print(f"  -> Indexados {stats['total_chunks']} chunks. Listo!")
except Exception as e:
    print(f"[WARN] No se pudo re-indexar automaticamente: {e}")
