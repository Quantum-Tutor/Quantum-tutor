APP_NAME = "Quantum Tutor"
SHORT_NAME = "QuantumTutor"
DISPLAY_VERSION = "v6.1"
RUNTIME_VERSION = "v6.1-stateless"
API_VERSION = "6.1"

ARCHITECTURE = "Stateless neuro-symbolic RAG tutor"
DEFAULT_TEXT_MODEL = "gemini-2.0-flash"
DEFAULT_VISION_MODEL = DEFAULT_TEXT_MODEL

API_TITLE = f"{APP_NAME} API"
STREAMLIT_PAGE_TITLE = f"{APP_NAME} | {RUNTIME_VERSION}"
WEB_CONSOLE_LABEL = f"{APP_NAME} {DISPLAY_VERSION}"
PWA_NAME = f"{APP_NAME} {DISPLAY_VERSION}"

SHORT_DESCRIPTION = (
    "Tutor de mecanica cuantica con orquestador stateless, "
    "RAG multi-fuente y fallback local."
)

LEGACY_DOCS = (
    "legacy/docs/QuantumTutor_v1.2_Especificacion.md",
    "legacy/docs/Roadmap_v2.0.md",
)
