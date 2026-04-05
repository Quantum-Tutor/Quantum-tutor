import logging
from rag_engine import RAGConnector

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TriggerRAG")

def main():
    logger.info("Iniciando RAGConnector para reconstruir el índice de embeddings...")
    logger.info("Esto puede tardar unos segundos porque ahora procesa Galindo y Cohen-Tannoudji.")
    rag = RAGConnector()
    logger.info(f"Índice reconstruido satisfactoriamente. Total de chunks en el vector store: {len(rag.vector_store)}")

if __name__ == "__main__":
    main()
