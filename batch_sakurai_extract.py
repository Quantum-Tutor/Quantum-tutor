import os
import fitz
import time

PDF_PATH = "J.J. Sakurai (Modern Quantum Mechanics).pdf"
OUT_DIR = "static_web/references"
TXT_OUT = "sakurai_full_ocr.txt"

os.makedirs(OUT_DIR, exist_ok=True)

print(f"Abriendo PDF: {PDF_PATH}")
if not os.path.exists(PDF_PATH):
    print(f"Error: No se encontro el archivo {PDF_PATH}")
    exit(1)

doc = fitz.open(PDF_PATH)
total = len(doc)

full_text = ""

print("Iniciando escaneo de texto e imagenes para Sakurai...")
start_time = time.time()

for i in range(total):
    page = doc[i]
    text = page.get_text("text")
    # Usa S_ para Sakurai
    full_text += f"\n\n## Pagina S_{i}\n\n{text}"
    
    # Extraer imagen y guardarla con prefijo sakurai_
    pix = page.get_pixmap(dpi=150)
    img_path = os.path.join(OUT_DIR, f"sakurai_page_{i}.png")
    pix.save(img_path)
    
    if i % 50 == 0 and i > 0:
        print(f"  -> Procesadas {i}/{total} paginas...")

with open(TXT_OUT, 'w', encoding='utf-8') as f:
    f.write(full_text)

elapsed = time.time() - start_time
print("\n" + "="*60)
print(f"[OK] PROCESAMIENTO COMPLETADO en {elapsed:.1f} segundos.")
print(f"Texto guardado en: {TXT_OUT}")
print(f"Imagenes guardadas en: {OUT_DIR}/sakurai_page_*.png")
print("="*60)

# Inject into vector store si el modulo RAGConnector esta disponible
try:
    from rag_engine import RAGConnector
    print("\n[+] Re-indexando el RAG de Sakurai...")
    rag = RAGConnector()
    # Limpiamos el cache para forzar la reingesta
    if os.path.exists(rag.index_cache_path):
        os.remove(rag.index_cache_path)
    rag._initialize_store()
    stats = rag.get_stats()
    print(f"  -> Total indexado de todos los libros: {stats['total_chunks']} chunks. Listo!")
except Exception as e:
    print(f"[WARN] No se pudo re-indexar automaticamente: {e}")
