import streamlit as st
import time
import json
import asyncio
import pandas as pd
from quantum_tutor_orchestrator import QuantumTutorOrchestrator
from learning_analytics import LearningAnalytics
from multimodal_vision_parser import MultimodalVisionParser
from auth_module import require_auth

# Configuración de la página
st.set_page_config(
    page_title="QuantumTutor v3.0 | Production Edition",
    page_icon="static/logo_192.png",
    layout="wide"
)

# Inyección de metadatos PWA y branding
st.logo("static/logo_192.png", icon_image="static/logo_192.png")
st.markdown(
    """
    <link rel="manifest" href="static/manifest.json">
    <meta name="theme-color" content="#FF4B4B">
    <style>
    .stApp > header {
        background-color: transparent;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Inicialización del Orquestador (Singleton para evitar recargas)
@st.cache_resource
def init_tutor():
    tutor = QuantumTutorOrchestrator()
    return tutor

@st.cache_resource
def init_analytics():
    return LearningAnalytics('student_profile.json')

@st.cache_resource
def init_vision():
    return MultimodalVisionParser()

# GATEWAY: Autenticación Obligatoria
auth = require_auth()

tutor = init_tutor()
analytics = init_analytics()
vision_parser = init_vision()

# Sidebar: Estado del Sistema y Analítica
with st.sidebar:
    st.title("🛠️ System Monitor")
    st.success("Core: v3.0 [Production-Ready]")
    st.markdown(f"**Usuario:** `{auth.get_user_email()}`")
    st.info("Knowledge Base: Galindo & Pascual")
    
    st.divider()
    if st.button("Cerrar Sesión (Google)"):
        auth.logout()
    
    st.divider()
    st.subheader("Métricas de Sesión")
    if "stats" not in st.session_state:
        st.session_state.stats = {"wolfram_hits": 0, "rag_queries": 0}
    
    st.metric("Wolfram Calls", st.session_state.stats["wolfram_hits"])
    st.metric("RAG Anchors", st.session_state.stats["rag_queries"])
    
    st.divider()
    st.subheader("🧠 Cognitive Profiler (v2.0 PoC)")
    
    clusters = analytics.get_misconception_clusters()
    heatmap = analytics.get_content_heatmap()
    
    with st.expander("Ver Mapa de Malentendidos", expanded=True):
        if clusters["Error_Calculo"]: st.warning(f"🧮 Error Cálculo: {', '.join(clusters['Error_Calculo'])}")
        if clusters["Error_Conceptual"]: st.error(f"🤔 Error Conceptual: {', '.join(clusters['Error_Conceptual'])}")
        if clusters["Falla_Base"]: st.error(f"🚨 Falla Base: {', '.join(clusters['Falla_Base'])}")
        if clusters["Dominado"]: st.success(f"✅ Dominado: {', '.join(clusters['Dominado'])}")
        if not any(clusters.values()): st.write("Aún no hay suficientes datos históricos.")
        
    with st.expander("🔥 Content Heatmap (Struggle Index)"):
        if heatmap:
            df = pd.DataFrame(heatmap)
            st.dataframe(df.style.background_gradient(cmap='OrRd', subset=['struggle_index']), hide_index=True)
        else:
            st.write("Sin datos.")

    st.divider()
    if st.button("Resetear Conversación"):
        st.session_state.messages = []
        st.session_state.stats = {"wolfram_hits": 0, "rag_queries": 0}
        st.rerun()

# Área Principal
st.title("⚛️ QuantumTutor v3.0")
st.markdown("""
Bienvenido al tutor especializado en Mecánica Cuántica. 
*Utiliza LaTeX para tus dudas y deja que exploremos juntos los fundamentos de la física.*
""")

# Historial de Chat
if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

# 📷 Interfaz Multimodal
vision_prompt = None
with st.expander("📷 Análisis Multimodal (Sube tu derivación manuscrita en formato imagen)"):
    uploaded_file = st.file_uploader("Formatos soportados: png, jpg. (Simulador PoC v2.0)", type=["png", "jpg", "jpeg"])
    if uploaded_file is not None and st.button("Analizar Fotografía"):
        with st.spinner("Parseando matemáticas vía OCR y Multimodal Vision..."):
            steps = vision_parser.parse_derivation_image(uploaded_file.name)
            vision_prompt = f"He subido una foto de mi derivación ({uploaded_file.name}). El modelo de visión extrajo esto:\n\n"
            for step in steps:
                flag = " ⚠️ [Alerta OCR: Posible Error]" if step.get("error_flag") else ""
                vision_prompt += f"- **Paso {step['step']}:** $${step['latex']}$$ (Confianza: {step['confidence']}){flag}\n"
            vision_prompt += "\nPor favor revisa mi procedimiento paso a paso y guíame socraticamente hacia el error."

# Input de Usuario
chat_input_val = st.chat_input("Ej: ¿Cómo se comporta la probabilidad en el centro de un pozo infinito para n=2?")
prompt = vision_prompt if vision_prompt else chat_input_val

if prompt:
    # Mostrar mensaje del usuario
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # Generación de Respuesta
    with st.chat_message("assistant"):
        response_placeholder = st.empty()
        full_response = ""
        
        # Simulación de flujo asíncrono y streaming
        with st.spinner("Consultando base de conocimientos y motor simbólico..."):
            # Llamada al orquestador consolidado (usamos el método asíncrono)
            try:
                loop = asyncio.get_event_loop()
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                
            response_data = loop.run_until_complete(tutor.generate_response_async(prompt))
            
            # Actualizamos estadísticas para el Dashboard
            if response_data.get("context_retrieved"):
                st.session_state.stats["rag_queries"] += 1
            if response_data.get("wolfram_used"):
                st.session_state.stats["wolfram_hits"] += 1
                
            # Extraer tópico rudimentario del prompt para Analytics (simulado)
            topic = "General"
            prompt_lower = prompt.lower()
            if "pozo" in prompt_lower: topic = "Pozo Infinito"
            elif "tunel" in prompt_lower or "túnel" in prompt_lower: topic = "Efecto Túnel"
            elif "espin" in prompt_lower or "espín" in prompt_lower: topic = "Espín"
            elif "oscilador" in prompt_lower: topic = "Oscilador Armónico"
            elif "conmutador" in prompt_lower: topic = "Conmutadores"
            
            # Simulamos el 'passed_socratic' asumiendo fallo si es muy corto el prompt o pide respuesta directa
            passed_soc = not ("dime" in prompt_lower or "respuesta" in prompt_lower or len(prompt_lower) < 15)
            analytics.log_interaction(topic, wolfram_invoked=response_data.get("wolfram_used", False), passed_socratic=passed_soc)

        # El streaming simulado se hace localmente iterando sobre las partes
        # En vez de response_data.split() que corta espacios innecesarios
        chunk_size = 5
        response_text = response_data['response']
        
        for i in range(0, len(response_text), chunk_size):
            chunk = response_text[i:i+chunk_size]
            full_response += chunk
            time.sleep(0.01) # Faster streaming effect
            response_placeholder.markdown(full_response + "▌")
            
        # Añadir metadata de latencia al final de la respuesta de forma disimulada
        latency_info = f"\n\n*(⏱️ I/O: {response_data['latency']['io_fetch']}s | RAG: {'Sí' if response_data['context_retrieved'] else 'No'} | Wolfram: {'Sí' if response_data['wolfram_used'] else 'No'})*"
        full_response += latency_info
        
        response_placeholder.markdown(full_response)
    
    st.session_state.messages.append({"role": "assistant", "content": full_response})
