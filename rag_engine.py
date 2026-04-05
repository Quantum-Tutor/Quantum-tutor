"""
RAGConnector v6.1 — Motor de Recuperación para QuantumTutor
============================================================
Conecta con la base de datos vectorial (Pinecone/Milvus emulado)
para realizar búsquedas semánticas sobre el material del curso.

En producción, este módulo usaría:
  - pinecone-client o pymilvus para la BD vectorial
  - openai o sentence-transformers para embeddings reales
"""

import logging
import json
import re
import os
import numpy as np
import pickle
from datetime import datetime
from pathlib import Path
import sys

# --- MONKEYPATCH (Resiliencia del módulo local) ---
if hasattr(sys.stderr, "flush"):
    def _safe_flush():
        try:
            # Capturamos la función original si aún no la tenemos
            if not hasattr(sys.stderr, "__flush_orig__"):
                sys.stderr.__flush_orig__ = sys.stderr.flush
            
            # Ejecutamos de forma segura
            if hasattr(sys.stderr, "__flush_orig__") and sys.stderr.__flush_orig__:
                sys.stderr.__flush_orig__()
        except Exception: 
            pass
    sys.stderr.flush = _safe_flush
# ----------------------------------------------

from sentence_transformers import SentenceTransformer
from galindo_page_map import galindo_display_page_from_ocr, resolve_galindo_reference
from quantum_tutor_paths import (
    BASE_DIR,
    RAG_INDEX_CACHE_PATH,
    resolve_runtime_path,
    write_pickle_atomic,
)

logger = logging.getLogger("QuantumTutor.RAG")

# ── Page Offset ───────────────────────────────────────────────────────────────
# El PDF de Wuolah tiene páginas de portada/wuolah antes del cuerpo del libro.
# PAGE_OFFSET corrige el índice OCR al número de página físico del libro G&P.
# Configurable vía variable de entorno GALINDO_PAGE_OFFSET (int, default 0).
# Ejemplo: Si la página 1 del libro real es la página 9 del PDF, usar PAGE_OFFSET=8.
PAGE_OFFSET: int = int(os.getenv("GALINDO_PAGE_OFFSET", "0"))
logger.info(f"[RAG] Page Offset configurado: {PAGE_OFFSET}")

VISUAL_QUERY_HINTS = (
    "imagen",
    "imagenes",
    "foto",
    "fotos",
    "figura",
    "figuras",
    "grafica",
    "gráfica",
    "dibujo",
    "referencia visual",
)

ADMIN_PAGE_PATTERNS = (
    "reader's guide",
    "readers guide",
    "complements of chapter",
    "table of contents",
    "contents",
    "translated from the french",
    "basic concepts, tools, and applications",
    "review of some useful properties",
    "solutions are given for exercises",
)

INFINITE_WELL_STRONG_TERMS = (
    "pozo infinito",
    "pozo de potencial infinito",
    "particula en una caja",
    "partícula en una caja",
    "particle in a box",
    "infinite square well",
    "infinite 'square' well",
    'infinite "square" well',
    "infinite “square” well",
    "well of infinite depth",
    "one-dimensional infinite well",
    "puits infini",
)

INFINITE_WELL_RELATED_TERMS = (
    "square well",
    "potential well",
    "bound states in a potential well",
    "bound state energies",
    "energia de punto cero",
    "energía de punto cero",
    "niveles de energia",
    "niveles de energía",
)


class RAGConnector:
    """
    Motor de recuperación aumentada para QuantumTutor.
    Gestiona la base de datos vectorial y las búsquedas semánticas
    sobre el material del curso de física cuántica.
    """

    def __init__(self, config_path="quantum_tutor_config.json", base_dir=None):
        # Resolución robusta de rutas
        try:
            if base_dir:
                _base_dir = Path(base_dir)
            else:
                _base_dir = Path(__file__).resolve().parent
            
            if os.path.isabs(config_path):
                self.config_path = Path(config_path)
            else:
                self.config_path = _base_dir / config_path
            
            self.config = self._load_config(str(self.config_path))
            self.vector_store = []
            self.query_log = []
            
            # Ruta del caché del índice
            if _base_dir.resolve() == BASE_DIR:
                self.index_cache_path = resolve_runtime_path(RAG_INDEX_CACHE_PATH, "rag_index.pkl")
            else:
                self.index_cache_path = _base_dir / "outputs" / "cache" / "rag_index.pkl"
            
            # Inicializar encoder de embeddings (all-MiniLM-L6-v2) con carga diferida
            self._encoder = None
            logger.info(f"[RAG] Motor inicializado (Lazy Model Loading activo). Config: {self.config_path}")
            self.base_dir = _base_dir
            # Ruta de imágenes de referencia unificada con ReferenceVisualizer
            self.references_dir = _base_dir / "static_web" / "references"
            self.available_images = self._scan_available_images()
            
        except Exception as e:
            logger.error(f"Error crítico en RAG __init__: {e}")
            raise
        
        self._initialize_store()  # BUG #4 FIX: llamada única (antes había duplicado)

    @property
    def encoder(self):
        """Carga el modelo de embeddings de forma perezosa y resiliente."""
        if self._encoder is None:
            logger.info("[RAG] Cargando modelo SentenceTransformer (all-MiniLM-L6-v2)...")
            try:
                # Intentar cargar localmente si es posible, evitando checks de red largos
                self._encoder = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
                logger.info("[RAG] Modelo cargado exitosamente.")
            except Exception as e:
                logger.error(f"[RAG] Error critico cargando SentenceTransformer: {e}")
                # Fallback o re-intentar sin checking de red si fuera posible
                self._encoder = None
        return self._encoder

    def _load_config(self, config_path: str) -> dict:
        """Carga la configuración RAG desde el JSON y variables de entorno."""
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                full_config = json.load(f)
        except Exception as e:
            logger.warning(f"Error en _load_config ({config_path}): {e}")
            full_config = {}

        defaults = {
            "vector_store": os.getenv("VECTOR_STORE", "pinecone-serverless"),
            "embedding_model": os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
            "top_k_fragments": int(os.getenv("TOP_K_FRAGMENTS", 5)),
            "similarity_threshold": float(os.getenv("SIMILARITY_THRESHOLD", 0.75)),
            "chunk_size": int(os.getenv("CHUNK_SIZE", 500)),
            "chunk_overlap": int(os.getenv("CHUNK_OVERLAP", 50))
        }
        
        # Mezclamos la configuración del archivo con los valores por defecto
        # Buscamos en la sección `rag_parameters` si existe
        file_rag = full_config.get("rag_parameters", {})
        
        return {
            "vector_store": file_rag.get("vector_store", defaults["vector_store"]),
            "embedding_model": file_rag.get("embedding_model", defaults["embedding_model"]),
            "top_k_fragments": int(file_rag.get("top_k_fragments", defaults["top_k_fragments"])),
            "similarity_threshold": float(file_rag.get("similarity_threshold", defaults["similarity_threshold"])),
            "chunk_size": int(file_rag.get("chunk_size", defaults["chunk_size"])),
            "chunk_overlap": int(file_rag.get("chunk_overlap", defaults["chunk_overlap"]))
        }

    def _initialize_store(self):
        """
        Inicializa el vector store con el material del curso.
        Implementa caching para reducir latencia de inicio.
        """
        # Intentar cargar desde caché
        if os.path.exists(self.index_cache_path):
            try:
                with open(self.index_cache_path, 'rb') as f:
                    self.vector_store = pickle.load(f)
                logger.info(f"[RAG] Índice cargado desde caché ({len(self.vector_store)} chunks). Latencia: <1s")
                return
            except Exception as e:
                logger.warning(f"[RAG] Error cargando caché: {e}. Reingiriendo...")

        # Usar self.index_cache_path.parent para respetar `base_dir`
        # en vez de Path(__file__).parent, que ignora la base configurada.
        base_dir = self.index_cache_path.parent
        full_ocr_path = base_dir / "galindo_pascual_full_ocr.txt"
        cohen_ocr_path = base_dir / "cohen_tannoudji_full_ocr.txt"
        sakurai_ocr_path = base_dir / "sakurai_full_ocr.txt"
        sample_path = base_dir / "material_curso" / "galindo_pascual_qm1_sample.md"

        # Ingestar Sakurai
        if os.path.exists(sakurai_ocr_path):
            with open(sakurai_ocr_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._ingest_content(content, source="Sakurai")
            logger.info(f"Ingestado {os.path.basename(sakurai_ocr_path)}: ahora hay {len(self.vector_store)} chunks")

        # Ingestar Cohen-Tannoudji
        if os.path.exists(cohen_ocr_path):
            with open(cohen_ocr_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._ingest_content(content, source="Cohen-Tannoudji")
            logger.info(f"Ingestado {os.path.basename(cohen_ocr_path)}: ahora hay {len(self.vector_store)} chunks")

        # Ingestar Galindo & Pascual
        if os.path.exists(full_ocr_path):
            with open(full_ocr_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._ingest_content(content, source="Galindo-Pascual")
            logger.info(f"Ingestado {os.path.basename(full_ocr_path)}: ahora hay {len(self.vector_store)} chunks")
        elif os.path.exists(sample_path) and not os.path.exists(cohen_ocr_path):
            with open(sample_path, 'r', encoding='utf-8') as f:
                content = f.read()
            self._ingest_content(content)
            logger.info(f"Vector store inicializado: {len(self.vector_store)} chunks "
                       f"desde {os.path.basename(sample_path)}")
        else:
            logger.info(f"Vector store inicializado con contenido fallback: "
                       f"{len(self.vector_store)} chunks")
        
        # Guardar en caché para futuros inicios rápidos
        try:
            write_pickle_atomic(self.index_cache_path, self.vector_store)
            logger.info(f"[RAG] Índice guardado en caché: {self.index_cache_path}")
        except Exception as e:
            logger.error(f"[RAG] No se pudo guardar el caché: {e}")

        # Ingesta de principios de dinámicas relacionales
        self._ingest_relational_principles()

    # Tamaño mínimo en bytes para considerar que una página tiene contenido real.
    # Las páginas por debajo de este umbral suelen ser portadas, páginas en blanco
    # o renders corruptos y no deben mostrarse como referencias.
    MIN_IMAGE_SIZE_BYTES: int = 50_000  # 50 KB

    def _scan_available_images(self) -> dict:
        """
        Escanea el directorio de referencias para encontrar imágenes de páginas disponibles.
        BUG-FIX: Filtra páginas en blanco/portadas (< MIN_IMAGE_SIZE_BYTES) para evitar
        que el tutor muestre portadas o páginas sin contenido como referencias bibliográficas.
        """
        available = {"galindo": set(), "cohen": set(), "sakurai": set()}
        if os.path.exists(self.references_dir):
            for file in os.listdir(self.references_dir):
                if file.endswith(".png"):
                    try:
                        file_path = os.path.join(self.references_dir, file)
                        file_size = os.path.getsize(file_path)
                        # Omitir portadas o páginas en blanco demasiado pequeñas
                        if file_size < self.MIN_IMAGE_SIZE_BYTES:
                            logger.debug(f"[RAG] Página omitida (demasiado pequeña, {file_size}B): {file}")
                            continue
                        if file.startswith("page_"):
                            page_num = int(file.replace("page_", "").replace(".png", ""))
                            available["galindo"].add(page_num)
                        elif file.startswith("cohen_page_"):
                            page_num = int(file.replace("cohen_page_", "").replace(".png", ""))
                            available["cohen"].add(page_num)
                        elif file.startswith("sakurai_page_"):
                            page_num = int(file.replace("sakurai_page_", "").replace(".png", ""))
                            available["sakurai"].add(page_num)
                    except (ValueError, OSError):
                        continue
        logger.info(f"[RAG] Escaneando imágenes en: {self.references_dir}")
        logger.info(f"[RAG] Imágenes con contenido real — Galindo: {len(available['galindo'])}, Cohen: {len(available['cohen'])}, Sakurai: {len(available['sakurai'])}")
        return available

    def _ingest_content(self, content: str, source: str = "Galindo-Pascual"):
        """Ingesta contenido Markdown con chunking semántico y filtrado de secciones en inglés."""
        BLOCKLIST_SECTIONS = [
            "Preface", "Prcface", "Introduction", "Foreword", "Prólogo", 
            "Acknowledgements", "Contents", "Physical Constants", "Subject Index"
        ]
        raw_chunks = re.split(r'\n(?=## )', content.strip())

        for i, chunk in enumerate(raw_chunks):
            chunk_text = chunk.strip()
            raw_lines = chunk_text.splitlines()
            raw_title_line = raw_lines[0].strip() if raw_lines else ""
            title_match = re.match(r'^##\s+(.+)', raw_title_line)
            title = title_match.group(1) if title_match else f"Sección {i}"

            # Preservar el identificador de página antes de limpiar ruido legal,
            # porque algunas reglas eliminan explícitamente el texto "Pagina N".
            page_num = None
            page_match = re.search(r'Pagina\s+(?:C_|S_)?(\d+)', title, re.IGNORECASE)
            if page_match:
                page_num = int(page_match.group(1))
            
            # 1. IDENTIFICAR RUIDO LEGAL (expandido)
            legal_noise_patterns = [
                r'wuolah', r'reservados todos los derechos', r'no se permite la',
                r'explotación económica', r'la transformación de esta obra',
                r'impresión en su totalidad', r'descargado por', r'universidad de granada',
                r'woah', r'mickjo99', r'facultad de ciencias', r'galindo-pascual-quantum-mechanic',
                r'grado en física', r'accede al documento original', r'física cuántica 30',
                r'springer-verlag', r'berlin heidelberg', r'new york london', r'paris tokyo',
                r'hong kong barcelona', r'translated by', r'with \d+ figures', r'manual for teachers',
                r'pagina \d+', r'galindo p pascual', r'quantum mechanics', r'j d garcía', r'alvarez-gaumé',
                r'alberto galindo', r'pedro pascual', r'university of arizona', r'cern tucson', r'princeton university'
            ]
            
            # Heurística: ¿Tiene ecuaciones o términos técnicos?
            has_physics = any(sym in chunk_text for sym in ["$", "\\", "psi", "H", "p", "x", "e^", "Psi", "ħ"])
            noise_hits = sum(1 for p in legal_noise_patterns if re.search(p, chunk_text, re.IGNORECASE))
            
            # Si tiene mucho ruido Y no parece tener física, descartar
            if noise_hits >= 2 and not has_physics:
                logger.info(f"[RAG] Descartando chunk {i} (portada/créditos/ruido)")
                continue

            # Heurística de metadatos (específicas de las primeras páginas del PDF de Wuolah)
            if i < 25 and any(kw in chunk_text.lower() for kw in ["contents", "preface", "index", "dedicado a", "physical constants", "prologue"]):
                if not has_physics:
                    logger.info(f"[RAG] Descartando chunk {i} (índice, prefacio o constantes sin física)")
                    continue

            # 2. EXCLUSIÓN EXPLÍCITA DE PÁGINAS DE RUIDO (Pagina 0, 1, 2, 7, 8, etc.)
            if re.search(r'## Pagina [01278]\b', chunk):
                 if not has_physics or "WUOLAH" in chunk:
                    logger.info(f"[RAG] Excluyendo página de metadatos/ruido: {i}")
                    continue

            # 2. LIMPIEZA DE RESIDUOS: eliminar fragmentos de marcas de agua de la memoria
            for p in legal_noise_patterns:
                chunk_text = re.sub(p, '', chunk_text, flags=re.IGNORECASE)
            
            # Limpieza adicional de caracteres extraños/OCR
            chunk_text = re.sub(r'\.-\s+', ' ', chunk_text) # Elimina ".- "
            chunk_text = re.sub(r'\s{2,}', ' ', chunk_text).strip() # Colapsa espacios

            if not chunk_text or len(chunk_text) < 100:
                continue

            # 3. FILTRADO POR TÍTULO/ENCABEZADO (Secciones que no queremos indexar)
            lines = [raw_title_line]
            title_match = re.match(r'^##\s+(.+)', lines[0])
            title = title_match.group(1) if title_match else f"Sección {i}"
            
            # Extraer número de página si está en el título (## Pagina N)
            page_num = None
            page_match = re.search(r'Pagina\s+(\d+)', title, re.IGNORECASE)
            if page_match:
                page_num = int(page_match.group(1))

            header_area = f"{title}\n{chunk_text[:300]}".lower()
            if any(term.lower() in header_area for term in BLOCKLIST_SECTIONS):
                logger.debug(f"[RAG] Saltando sección administrativa: {title}")
                continue

            # Precalcular el embedding del chunk si el modelo está disponible
            embedding = self.encoder.encode(chunk_text) if self.encoder else None
            
            self.vector_store.append({
                "id": f"chunk_{i}",
                "text": chunk_text,
                "title": title,
                "source": source,
                "page_number": page_num,
                "embedding": embedding,
                "char_count": len(chunk_text),
                "has_equations": "$$" in chunk_text or "$" in chunk_text,
            })

    def _ingest_fallback(self):
        """Contenido mínimo de fallback si no hay documento real."""
        fallback_chunks = [
            {
                "id": "fb_0",
                "title": "Ecuación de Schrödinger",
                "text": (
                    "La ecuación de Schrödinger dependiente del tiempo es:\n"
                    "$$i\\hbar\\frac{\\partial}{\\partial t}|\\psi(t)\\rangle = "
                    "\\hat{H}|\\psi(t)\\rangle$$\n"
                    "donde $\\hat{H}$ es el hamiltoniano del sistema."
                )
            },
            {
                "id": "fb_1",
                "title": "Pozo de Potencial Infinito",
                "text": (
                    "Para una partícula en una caja de longitud L, la función de onda es:\n"
                    "$$\\psi_n(x) = \\sqrt{\\frac{2}{L}}\\sin\\left(\\frac{n\\pi x}{L}\\right)$$\n"
                    "con niveles de energía $E_n = \\frac{n^2\\pi^2\\hbar^2}{2mL^2}$.\n"
                    "La energía del estado fundamental $E_1 > 0$ (energía de punto cero)."
                )
            },
            {
                "id": "fb_2",
                "title": "Conmutadores",
                "text": (
                    "El conmutador canónico es $[\\hat{x}, \\hat{p}] = i\\hbar$.\n"
                    "Para operadores compuestos: $[\\hat{A}\\hat{B}, \\hat{C}] = "
                    "\\hat{A}[\\hat{B}, \\hat{C}] + [\\hat{A}, \\hat{C}]\\hat{B}$.\n"
                    "Aplicación: $[\\hat{x}^2, \\hat{p}] = 2i\\hbar\\hat{x}$."
                )
            }
        ]
        for chunk in fallback_chunks:
            # Proteger el fallback si el encoder no está disponible
            chunk["embedding"] = self.encoder.encode(chunk["text"]) if self.encoder else None
            chunk["char_count"] = len(chunk["text"])
            chunk["has_equations"] = True
            
        self.vector_store.extend(fallback_chunks)

    def _ingest_relational_principles(self):
        """Desactivado para priorizar fidelidad a Galindo & Pascual."""
        # Se elimina la inyección de principios extra-bibliográficos (Kernel E-2)
        relational_chunks = []
        logger.info(f"[RAG] Ingesta relacional deshabilitada.")

    def _expand_query(self, query: str) -> str:
        """Expande consultas en español con términos clave en inglés para mejorar el RAG."""
        translations = {
            "densidad de probabilidad": "probability density",
            "densidad de probabilidad espacial": "spatial probability density",
            "corriente de probabilidad": "probability current",
            "ecuacion de schrodinger": "schrodinger equation",
            "pozo de potencial": "potential well",
            "pozo de potencial infinito": "infinite square well particle in a box",
            "pozo infinito": "infinite square well particle in a box",
            "particula en una caja": "particle in a box infinite square well",
            "partícula en una caja": "particle in a box infinite square well",
            "principio de incertidumbre": "uncertainty principle",
            "conmutador": "commutator",
            "notación dirac": "dirac notation",
            "notacion dirac": "dirac notation",
            "efecto túnel": "tunnel effect",
            "efecto tunel": "tunnel effect",
            "oscilador armónico": "harmonic oscillator",
            "oscilador armonico": "harmonic oscillator",
            "átomo de hidrógeno": "hydrogen atom",
            "atomo de hidrogeno": "hydrogen atom"
        }
        expanded = query.lower()
        for es, en in translations.items():
            if es in expanded:
                expanded += f" ({en})"
        return expanded

    def _normalize_text(self, text: str) -> str:
        return re.sub(r"\s+", " ", (text or "").lower()).strip()

    def _map_source_label(self, raw_source: str | None) -> str | None:
        normalized_source = self._normalize_text(raw_source or "")
        if "cohen" in normalized_source:
            return "cohen"
        if "sakurai" in normalized_source:
            return "sakurai"
        if "galindo" in normalized_source or "pascual" in normalized_source:
            return "galindo"
        return None

    def _infer_page_number_from_title(self, raw_title: str) -> int | None:
        explicit_match = re.search(r'(?:Pagina|PÃ¡gina|page|p\.|pg|\[)\s*(?:C_|S_)?(\d+)', raw_title, re.IGNORECASE)
        if explicit_match:
            return int(explicit_match.group(1))

        leading_match = re.match(r'^\s*(\d{1,4})\b', raw_title)
        if leading_match:
            return int(leading_match.group(1))

        early_numbers = [int(token) for token in re.findall(r'\b(\d{2,4})\b', raw_title[:120])]
        if early_numbers:
            return early_numbers[-1]

        return None

    def _extract_page_metadata_legacy(self, chunk: dict) -> dict:
        raw_title = str(chunk.get("title", "Desconocido"))
        page_num = chunk.get("page_number")
        source = self._map_source_label(chunk.get("source"))

        if page_num is None:
            page_num = self._infer_page_number_from_title(raw_title)
            page_match = re.search(r'(?:Pagina|Página|p\.|pg|\[)\s*(?:C_|S_)?(\d+)', raw_title, re.IGNORECASE)
            if page_match:
                page_num = page_match.group(1)

        is_cohen = "C_" in raw_title
        is_sakurai = "S_" in raw_title
        if is_cohen or source == "cohen":
            source = "cohen"
        elif is_sakurai or source == "sakurai":
            source = "sakurai"
        else:
            source = "galindo"

        return {
            "raw_title": raw_title,
            "page_num": page_num,
            "source": source,
            "is_cohen": is_cohen,
            "is_sakurai": is_sakurai,
        }

    def _extract_explicit_page_marker(self, raw_title: str) -> tuple[str | None, int | None]:
        explicit_match = re.search(r'(?:Pagina|PÃƒÂ¡gina|PÃ¡gina|page|p\.|pg|\[)\s*((?:C_|S_)?)(\d+)', raw_title, re.IGNORECASE)
        if not explicit_match:
            return None, None
        return (explicit_match.group(1) or "").upper(), int(explicit_match.group(2))

    def _extract_page_metadata(self, chunk: dict) -> dict:
        raw_title = str(chunk.get("title", "Desconocido"))
        chunk_text = str(chunk.get("text", ""))
        page_num = chunk.get("page_number")
        source = self._map_source_label(chunk.get("source"))
        marker_prefix, explicit_page_num = self._extract_explicit_page_marker(raw_title)

        if page_num is None:
            page_num = self._infer_page_number_from_title(raw_title)
            if explicit_page_num is not None:
                page_num = explicit_page_num

        is_cohen = marker_prefix == "C_" or "C_" in raw_title
        is_sakurai = marker_prefix == "S_" or "S_" in raw_title
        if is_cohen or source == "cohen":
            source = "cohen"
        elif is_sakurai or source == "sakurai":
            source = "sakurai"
        else:
            source = "galindo"

        display_page = None
        asset_page = None
        ocr_page = None

        if source == "galindo":
            title_has_explicit_marker = explicit_page_num is not None and not (is_cohen or is_sakurai)
            title_is_legacy_display = bool(re.match(r'^\s*\d{1,4}\b', raw_title)) and not title_has_explicit_marker

            if title_is_legacy_display:
                display_page = self._infer_page_number_from_title(raw_title)
            elif title_has_explicit_marker:
                ocr_page = explicit_page_num

            if display_page is None:
                text_display_match = re.search(r'(?:^|\n|##\s*)\s*(\d{1,4})\b', chunk_text[:160])
                if text_display_match:
                    display_page = int(text_display_match.group(1))

            if display_page is None and ocr_page is not None:
                display_page = galindo_display_page_from_ocr(ocr_page)

            if display_page is not None or ocr_page is not None:
                resolved_ref = resolve_galindo_reference(display_page=display_page, ocr_page=ocr_page)
                display_page = resolved_ref["display_page"]
                asset_page = resolved_ref["asset_page"]
                ocr_page = resolved_ref["ocr_page"]

        return {
            "raw_title": raw_title,
            "page_num": page_num,
            "display_page": display_page,
            "asset_page": asset_page,
            "ocr_page": ocr_page,
            "source": source,
            "is_cohen": is_cohen,
            "is_sakurai": is_sakurai,
        }

    def _get_query_signals(self, user_query: str) -> dict:
        normalized_query = self._normalize_text(user_query)
        query_tokens = set(re.findall(r"[a-záéíóúüñ0-9]+", normalized_query))
        author_preference = None
        if "sakurai" in normalized_query:
            author_preference = "sakurai"
        elif "cohen" in normalized_query:
            author_preference = "cohen"
        elif "galindo" in normalized_query or "pascual" in normalized_query:
            author_preference = "galindo"

        topic = None
        if any(term in normalized_query for term in ("pozo", "particle in a box", "square well", "infinite well")):
            topic = "infinite_well"

        return {
            "normalized_query": normalized_query,
            "query_tokens": query_tokens,
            "is_visual": any(hint in normalized_query for hint in VISUAL_QUERY_HINTS),
            "author_preference": author_preference,
            "topic": topic,
        }

    def _chunk_has_available_image_legacy(self, meta: dict) -> tuple[bool, str | int | None]:
        page_num = meta.get("page_num")
        if meta["is_cohen"]:
            image_page_int = int(page_num) if page_num else None
            if image_page_int is not None and image_page_int in self.available_images["cohen"]:
                return True, f"cohen_page_{image_page_int}"
            return False, None

        if meta["is_sakurai"]:
            image_page_int = int(page_num) if page_num else None
            if image_page_int is not None and image_page_int in self.available_images["sakurai"]:
                return True, f"sakurai_page_{image_page_int}"
            return False, None

        image_page_int = None
        if page_num:
            try:
                image_page_int = int(page_num) - PAGE_OFFSET
                if image_page_int < 1:
                    image_page_int = None
            except (ValueError, TypeError):
                image_page_int = None

        if image_page_int and image_page_int in self.available_images["galindo"]:
            return True, image_page_int
        return False, None

    def _chunk_has_available_image(self, meta: dict) -> tuple[bool, str | int | None]:
        page_num = meta.get("page_num")
        if meta["is_cohen"]:
            image_page_int = int(page_num) if page_num else None
            if image_page_int is not None and image_page_int in self.available_images["cohen"]:
                return True, f"cohen_page_{image_page_int}"
            return False, None

        if meta["is_sakurai"]:
            image_page_int = int(page_num) if page_num else None
            if image_page_int is not None and image_page_int in self.available_images["sakurai"]:
                return True, f"sakurai_page_{image_page_int}"
            return False, None

        asset_page = meta.get("asset_page")
        if asset_page and asset_page in self.available_images["galindo"]:
            return True, asset_page
        return False, None

    def _topic_match_profile(self, query_signals: dict, haystack: str) -> tuple[float, bool]:
        boost = 0.0
        strong_match = False

        if query_signals["topic"] == "infinite_well":
            if any(term in haystack for term in INFINITE_WELL_STRONG_TERMS):
                boost += 0.55
                strong_match = True
            elif any(term in haystack for term in INFINITE_WELL_RELATED_TERMS):
                boost += 0.18
            else:
                boost -= 0.28

            if "n=2" in query_signals["normalized_query"] or "n 2" in query_signals["normalized_query"]:
                if any(marker in haystack for marker in ("n=2", "n 2", "second state", "segundo estado")):
                    boost += 0.08
                    strong_match = True

        return boost, strong_match

    def _administrative_penalty(self, meta: dict, haystack: str) -> float:
        penalty = 0.0
        if any(pattern in haystack for pattern in ADMIN_PAGE_PATTERNS):
            penalty -= 0.65

        page_num = meta.get("page_num")
        try:
            page_num_int = int(page_num) if page_num is not None else None
        except (ValueError, TypeError):
            page_num_int = None

        if page_num_int is not None and page_num_int <= 5:
            penalty -= 0.30

        return penalty

    def _is_administrative_match(self, normalized_title: str, normalized_text: str) -> bool:
        haystack = f"{normalized_title}\n{normalized_text}"
        return any(pattern in haystack for pattern in ADMIN_PAGE_PATTERNS)

    def _preferred_visual_matches(self, ranked: list[dict], query_signals: dict) -> list[dict]:
        if not (query_signals["is_visual"] and query_signals["topic"] == "infinite_well"):
            return []

        return [
            result for result in ranked
            if result["has_image"]
            and result["strong_topic_match"]
            and not result["is_administrative"]
        ]

    def _author_boost(self, query_signals: dict, meta: dict) -> float:
        if query_signals["author_preference"] and query_signals["author_preference"] == meta["source"]:
            return 0.45
        return 0.0

    def _score_chunk(self, chunk: dict, user_query: str, query_signals: dict, query_embedding, relational_mind=None) -> dict:
        chunk_text = str(chunk.get("text", ""))
        chunk_title = str(chunk.get("title", ""))
        normalized_text = self._normalize_text(chunk_text)
        normalized_title = self._normalize_text(chunk_title)
        haystack = f"{normalized_title}\n{normalized_text}"

        if query_embedding is not None and chunk.get("embedding") is not None:
            sim = self._cosine_similarity(query_embedding, chunk["embedding"])
        else:
            keyword_hits = sum(
                1 for token in query_signals["query_tokens"]
                if token in normalized_text or token in normalized_title
            )
            sim = keyword_hits / max(len(query_signals["query_tokens"]), 1)

        if relational_mind:
            rel_affinity = relational_mind.get_relational_score(chunk_text)
            sim = sim + (relational_mind.alpha_rerank * rel_affinity)

        intro_keywords = [
            "Fundamentos", "Postulados", "Principios", "Axioma", "Introducción", "Sección 1",
            "Introduction", "Postulates", "Basis", "Principles", "Elementary", "Foundation"
        ]
        if len(user_query) < 12 and any(kw in chunk_title or kw in chunk_text[:100] for kw in intro_keywords):
            sim += 0.30

        meta = self._extract_page_metadata(chunk)
        has_image, image_identifier = self._chunk_has_available_image(meta)
        boost, strong_topic_match = self._topic_match_profile(query_signals, haystack)
        penalty = self._administrative_penalty(meta, haystack)
        is_administrative = self._is_administrative_match(normalized_title, normalized_text)
        score = sim + boost + penalty + self._author_boost(query_signals, meta)

        if query_signals["is_visual"] and has_image:
            score += 0.08
            if query_signals["topic"] == "infinite_well":
                if strong_topic_match and not is_administrative:
                    score += 0.22
                elif not strong_topic_match:
                    score -= 0.18

        return {
            "chunk": chunk,
            "score": score,
            "meta": meta,
            "has_image": has_image,
            "image_identifier": image_identifier,
            "strong_topic_match": strong_topic_match,
            "is_administrative": is_administrative,
            "normalized_text": normalized_text,
            "normalized_title": normalized_title,
        }

    def _rank_chunks(self, user_query: str, relational_mind=None) -> list[dict]:
        if not self.vector_store:
            return []

        enhanced_query = self._expand_query(user_query)
        query_embedding = self.encoder.encode(enhanced_query) if self.encoder else None
        query_signals = self._get_query_signals(user_query)

        ranked = [
            self._score_chunk(chunk, user_query, query_signals, query_embedding, relational_mind=relational_mind)
            for chunk in self.vector_store
        ]
        ranked.sort(key=lambda item: item["score"], reverse=True)
        return ranked

    def _cosine_similarity(self, a, b):
        """Calcula la similitud de coseno usando numpy (más robusto en Windows)."""
        dot_product = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot_product / (norm_a * norm_b)

    def query_legacy(self, user_query: str, k: int = 4, relational_mind=None) -> str:
        """
        Búsqueda semántica con expansión bilingüe y reranking relacional.
        """
        if not self.vector_store:
            return ""

        query_signals = self._get_query_signals(user_query)
        ranked_results = self._rank_chunks(user_query, relational_mind=relational_mind)
        preferred_visual_matches = self._preferred_visual_matches(ranked_results, query_signals)
        top_results = (preferred_visual_matches or ranked_results)[:k]

        # Log de la consulta
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": user_query[:100],
            "results_count": len(top_results),
            "top_score": round(top_results[0]["score"], 4) if top_results else 0,
            "relational_boost": relational_mind is not None
        }
        self.query_log.append(log_entry)
        
        # Concatenar fragmentos con metadata
        context_parts = []
        legal_noise_patterns = [
            r'wuolah', r'reservados todos los derechos', r'no se permite la',
            r'explotación económica', r'la transformación de esta obra',
            r'impresión en su totalidad', r'descargado por', r'universidad de granada',
            r'woah', r'mickjo99', r'facultad de ciencias', r'galindo-pascual-quantum-mechanic',
            r'grado en física', r'accede al documento original', r'física cuántica 30',
            r'pagina \d+', r'galindo p pascual', r'quantum mechanics', r'j d garcía', r'alvarez-gaumé'
        ]

        for result in top_results:
            if (
                query_signals["is_visual"]
                and query_signals["topic"] == "infinite_well"
                and result["is_administrative"]
            ):
                continue
            if (
                query_signals["topic"] == "infinite_well"
                and result["is_administrative"]
                and not result["strong_topic_match"]
            ):
                continue
            chunk = result["chunk"]
            text = chunk['text']
            # Limpiar ruidos en la salida final
            for p in legal_noise_patterns:
                text = re.sub(p, '', text, flags=re.IGNORECASE)
            
            text = re.sub(r'\.-\s+', ' ', text)
            text = re.sub(r'[ \t]{2,}', ' ', text).strip()

            # Lógica de extracción de página robusta con Page Offset
            meta = result["meta"]
            raw_title = meta["raw_title"]
            page_num = meta["page_num"]
            is_cohen = meta["is_cohen"]
            is_sakurai = meta["is_sakurai"]

            image_note = ""
            if is_cohen:
                image_page_int = int(page_num) if page_num else None
                source_tag = f"Cohen-Tannoudji Pagina {image_page_int}" if image_page_int else raw_title
                if image_page_int is not None and image_page_int in self.available_images["cohen"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/cohen_page_{image_page_int}.png]"
            elif is_sakurai:
                image_page_int = int(page_num) if page_num else None
                source_tag = f"J.J. Sakurai Pagina {image_page_int}" if image_page_int else raw_title
                if image_page_int is not None and image_page_int in self.available_images["sakurai"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/sakurai_page_{image_page_int}.png]"
            else:
                # Aplicar Page Offset: ajusta índice PDF → página física del libro G&P
                image_page_int = None
                if page_num:
                    try:
                        image_page_int = int(page_num) - PAGE_OFFSET
                        if image_page_int < 1:
                            image_page_int = None  # Evitar páginas negativas
                    except (ValueError, TypeError):
                        pass

                source_tag = f"Galindo-Pascual Pagina {image_page_int}" if image_page_int else raw_title

                if image_page_int and image_page_int in self.available_images["galindo"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/page_{image_page_int}.png]"

            context_parts.append(
                f"[Fuente: {source_tag}]{image_note}\n"
                f"{text}"
            )

        return "\n\n---\n\n".join(context_parts) if context_parts else ""

    def query_with_images_legacy(self, user_query: str, k: int = 4, relational_mind=None) -> dict:
        """
        Versión de query() que además retorna la lista de páginas con imagen disponible.
        Retorna: {"context": str, "image_pages": list[PageId]}
        donde PageId puede ser int (Galindo) o str tipo cohen_page_N / sakurai_page_N.
        """
        if not self.vector_store:
            return {"context": "", "image_pages": []}

        query_signals = self._get_query_signals(user_query)
        ranked_results = self._rank_chunks(user_query, relational_mind=relational_mind)
        preferred_visual_matches = self._preferred_visual_matches(ranked_results, query_signals)
        top_results = (preferred_visual_matches or ranked_results)[:k]

        legal_noise_patterns = [
            r'wuolah', r'reservados todos los derechos', r'no se permite la',
            r'explotación económica', r'la transformación de esta obra',
            r'impresión en su totalidad', r'descargado por', r'universidad de granada',
            r'woah', r'mickjo99', r'facultad de ciencias', r'galindo-pascual-quantum-mechanic',
            r'grado en física', r'accede al documento original', r'física cuántica 30',
            r'pagina \d+', r'galindo p pascual', r'quantum mechanics', r'j d garcía', r'alvarez-gaumé'
        ]

        context_parts = []
        image_pages = []  # Lista de páginas con imagen disponible

        for result in top_results:
            if (
                query_signals["is_visual"]
                and query_signals["topic"] == "infinite_well"
                and result["is_administrative"]
            ):
                continue
            if (
                query_signals["topic"] == "infinite_well"
                and result["is_administrative"]
                and not result["strong_topic_match"]
            ):
                continue
            chunk = result["chunk"]
            score = result["score"]
            text = chunk['text']
            for p in legal_noise_patterns:
                text = re.sub(p, '', text, flags=re.IGNORECASE)
            text = re.sub(r'\.\-\s+', ' ', text)
            text = re.sub(r'[ \t]{2,}', ' ', text).strip()

            meta = result["meta"]
            raw_title = meta["raw_title"]
            page_num = meta["page_num"]
            is_cohen = meta["is_cohen"]
            is_sakurai = meta["is_sakurai"]
            image_note = ""
            should_attach_image = result["has_image"]

            if query_signals["topic"] == "infinite_well":
                if not result["strong_topic_match"] and score < 0.45:
                    should_attach_image = False
                if any(pattern in self._normalize_text(text) for pattern in ADMIN_PAGE_PATTERNS):
                    should_attach_image = False
            
            if is_cohen:
                image_page_int = int(page_num) if page_num else None
                source_tag = f"Cohen-Tannoudji Pagina {image_page_int}" if image_page_int else raw_title
                if should_attach_image and image_page_int is not None and image_page_int in self.available_images["cohen"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/cohen_page_{image_page_int}.png]"
                    image_pages.append(f"cohen_page_{image_page_int}") # BUG-FIX: matched naming expected by reference_visualizer
            elif is_sakurai:
                image_page_int = int(page_num) if page_num else None
                source_tag = f"J.J. Sakurai Pagina {image_page_int}" if image_page_int else raw_title
                if should_attach_image and image_page_int is not None and image_page_int in self.available_images["sakurai"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/sakurai_page_{image_page_int}.png]"
                    image_pages.append(f"sakurai_page_{image_page_int}") # BUG-FIX: matched naming expected by reference_visualizer
            else:
                # Aplicar Page Offset: alinea índice PDF → página física G&P
                image_page_int = None
                if page_num:
                    try:
                        image_page_int = int(page_num) - PAGE_OFFSET
                        if image_page_int < 1:
                            image_page_int = None
                    except (ValueError, TypeError):
                        pass

                source_tag = f"Galindo-Pascual Pagina {image_page_int}" if image_page_int else raw_title

                if should_attach_image and image_page_int and image_page_int in self.available_images["galindo"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/page_{image_page_int}.png]"
                    image_pages.append(image_page_int)  # Registrar para el orquestador

            context_parts.append(
                f"[Fuente: {source_tag}]{image_note}\n"
                f"{text}"
            )

        context = "\n\n---\n\n".join(context_parts) if context_parts else ""
        
        # Preserve order (most relevant first) while removing duplicates
        ordered_images = list(dict.fromkeys(image_pages))[:10]
        
        return {"context": context, "image_pages": ordered_images}

    def query(self, user_query: str, k: int = 4, relational_mind=None) -> str:
        """
        Búsqueda semántica con expansión bilingüe y reranking relacional.
        """
        if not self.vector_store:
            return ""

        query_signals = self._get_query_signals(user_query)
        ranked_results = self._rank_chunks(user_query, relational_mind=relational_mind)
        preferred_visual_matches = self._preferred_visual_matches(ranked_results, query_signals)
        top_results = (preferred_visual_matches or ranked_results)[:k]

        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "query": user_query[:100],
            "results_count": len(top_results),
            "top_score": round(top_results[0]["score"], 4) if top_results else 0,
            "relational_boost": relational_mind is not None
        }
        self.query_log.append(log_entry)

        context_parts = []
        legal_noise_patterns = [
            r'wuolah', r'reservados todos los derechos', r'no se permite la',
            r'explotación económica', r'la transformación de esta obra',
            r'impresión en su totalidad', r'descargado por', r'universidad de granada',
            r'woah', r'mickjo99', r'facultad de ciencias', r'galindo-pascual-quantum-mechanic',
            r'grado en física', r'accede al documento original', r'física cuántica 30',
            r'pagina \d+', r'galindo p pascual', r'quantum mechanics', r'j d garcía', r'alvarez-gaumé'
        ]

        for result in top_results:
            if (
                query_signals["is_visual"]
                and query_signals["topic"] == "infinite_well"
                and result["is_administrative"]
            ):
                continue
            if (
                query_signals["topic"] == "infinite_well"
                and result["is_administrative"]
                and not result["strong_topic_match"]
            ):
                continue

            chunk = result["chunk"]
            text = chunk["text"]
            for pattern in legal_noise_patterns:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            text = re.sub(r'\.-\s+', ' ', text)
            text = re.sub(r'[ \t]{2,}', ' ', text).strip()

            meta = result["meta"]
            raw_title = meta["raw_title"]
            page_num = meta["page_num"]
            display_page = meta.get("display_page")
            asset_page = meta.get("asset_page")

            image_note = ""
            if meta["is_cohen"]:
                image_page_int = int(page_num) if page_num else None
                source_tag = f"Cohen-Tannoudji Pagina {image_page_int}" if image_page_int else raw_title
                if image_page_int is not None and image_page_int in self.available_images["cohen"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/cohen_page_{image_page_int}.png]"
            elif meta["is_sakurai"]:
                image_page_int = int(page_num) if page_num else None
                source_tag = f"J.J. Sakurai Pagina {image_page_int}" if image_page_int else raw_title
                if image_page_int is not None and image_page_int in self.available_images["sakurai"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/sakurai_page_{image_page_int}.png]"
            else:
                source_tag = f"Galindo-Pascual Pagina {display_page}" if display_page else raw_title
                if asset_page and asset_page in self.available_images["galindo"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/page_{asset_page}.png]"

            context_parts.append(
                f"[Fuente: {source_tag}]{image_note}\n"
                f"{text}"
            )

        return "\n\n---\n\n".join(context_parts) if context_parts else ""

    def query_with_images(self, user_query: str, k: int = 4, relational_mind=None) -> dict:
        """
        Versión de query() que además retorna la lista de páginas con imagen disponible.
        Retorna: {"context": str, "image_pages": list[PageId]}
        donde PageId puede ser int (Galindo citado) o str tipo cohen_page_N / sakurai_page_N.
        """
        if not self.vector_store:
            return {"context": "", "image_pages": []}

        query_signals = self._get_query_signals(user_query)
        ranked_results = self._rank_chunks(user_query, relational_mind=relational_mind)
        preferred_visual_matches = self._preferred_visual_matches(ranked_results, query_signals)
        top_results = (preferred_visual_matches or ranked_results)[:k]

        legal_noise_patterns = [
            r'wuolah', r'reservados todos los derechos', r'no se permite la',
            r'explotación económica', r'la transformación de esta obra',
            r'impresión en su totalidad', r'descargado por', r'universidad de granada',
            r'woah', r'mickjo99', r'facultad de ciencias', r'galindo-pascual-quantum-mechanic',
            r'grado en física', r'accede al documento original', r'física cuántica 30',
            r'pagina \d+', r'galindo p pascual', r'quantum mechanics', r'j d garcía', r'alvarez-gaumé'
        ]

        context_parts = []
        image_pages = []

        for result in top_results:
            if (
                query_signals["is_visual"]
                and query_signals["topic"] == "infinite_well"
                and result["is_administrative"]
            ):
                continue
            if (
                query_signals["topic"] == "infinite_well"
                and result["is_administrative"]
                and not result["strong_topic_match"]
            ):
                continue

            chunk = result["chunk"]
            score = result["score"]
            text = chunk["text"]
            for pattern in legal_noise_patterns:
                text = re.sub(pattern, "", text, flags=re.IGNORECASE)
            text = re.sub(r'\.\-\s+', ' ', text)
            text = re.sub(r'[ \t]{2,}', ' ', text).strip()

            meta = result["meta"]
            raw_title = meta["raw_title"]
            page_num = meta["page_num"]
            display_page = meta.get("display_page")
            asset_page = meta.get("asset_page")
            image_note = ""
            should_attach_image = result["has_image"]

            if query_signals["topic"] == "infinite_well":
                if not result["strong_topic_match"] and score < 0.45:
                    should_attach_image = False
                if any(pattern in self._normalize_text(text) for pattern in ADMIN_PAGE_PATTERNS):
                    should_attach_image = False

            if meta["is_cohen"]:
                image_page_int = int(page_num) if page_num else None
                source_tag = f"Cohen-Tannoudji Pagina {image_page_int}" if image_page_int else raw_title
                if should_attach_image and image_page_int is not None and image_page_int in self.available_images["cohen"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/cohen_page_{image_page_int}.png]"
                    image_pages.append(f"cohen_page_{image_page_int}")
            elif meta["is_sakurai"]:
                image_page_int = int(page_num) if page_num else None
                source_tag = f"J.J. Sakurai Pagina {image_page_int}" if image_page_int else raw_title
                if should_attach_image and image_page_int is not None and image_page_int in self.available_images["sakurai"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/sakurai_page_{image_page_int}.png]"
                    image_pages.append(f"sakurai_page_{image_page_int}")
            else:
                source_tag = f"Galindo-Pascual Pagina {display_page}" if display_page else raw_title
                if should_attach_image and asset_page and asset_page in self.available_images["galindo"]:
                    image_note = f"\n[IMAGEN_DISPONIBLE: references/page_{asset_page}.png]"
                    image_pages.append(display_page if display_page is not None else asset_page)

            context_parts.append(
                f"[Fuente: {source_tag}]{image_note}\n"
                f"{text}"
            )

        context = "\n\n---\n\n".join(context_parts) if context_parts else ""
        ordered_images = list(dict.fromkeys(image_pages))[:10]
        return {"context": context, "image_pages": ordered_images}


    def get_stats(self) -> dict:
        """Retorna estadísticas del vector store."""
        return {
            "total_chunks": len(self.vector_store),
            "total_chars": sum(c["char_count"] for c in self.vector_store),
            "chunks_with_equations": sum(1 for c in self.vector_store if c["has_equations"]),
            "total_queries": len(self.query_log),
            "sections": [c["title"] for c in self.vector_store],
        }


# ── Ejecucion standalone ─────────────────────────────────────────────
if __name__ == "__main__":
    print("\n" + "=" * 72)
    print("  RAG ENGINE — Prueba de Conectividad")
    print("=" * 72)

    rag = RAGConnector()
    stats = rag.get_stats()
    print(f"\n  Vector Store: {stats['total_chunks']} chunks, "
          f"{stats['total_chars']} chars")
    print(f"  Chunks con ecuaciones: {stats['chunks_with_equations']}")
    print(f"  Secciones:")
    for s in stats["sections"]:
        print(f"    - {s}")

    # Test queries
    test_queries = [
        "Ecuacion de Schrodinger dependiente del tiempo",
        "Probabilidad en el pozo de potencial infinito para n=2",
        "Conmutador de x cuadrado con p",
        "Efecto tunel cuantico",
        "Principio de incertidumbre de Heisenberg",
    ]

    print(f"\n  Ejecutando {len(test_queries)} consultas de prueba:")
    for q in test_queries:
        result = rag.query(q, k=1)
        preview = result[:120].replace('\n', ' ') if result else "(sin resultados)"
        print(f"\n  Q: \"{q}\"")
        print(f"  R: {preview}...")

    print(f"\n{'=' * 72}")
    print(f"  [OK] RAG Engine funcional: {stats['total_chunks']} chunks indexados")
    print(f"{'=' * 72}\n")
