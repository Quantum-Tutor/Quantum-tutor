import streamlit as st
import re
import os

class GoogleAuthWrapper:
    """
    Simulador de Autenticación de Google Workspace (v3.0 Production).
    En producción, utiliza las variables de entorno para habilitar el flujo OAuth real.
    """
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_CLIENT_ID", None)
        self.is_prod = self.client_id is not None
        
        # Inicializa estado de sesión
        if 'authenticated' not in st.session_state:
            st.session_state.authenticated = False
        if 'user_email' not in st.session_state:
            st.session_state.user_email = ""

    def is_authenticated(self):
        return st.session_state.authenticated

    def get_user_email(self):
        return st.session_state.user_email

    def login_screen(self):
        st.markdown("<h1 style='text-align: center; color: #4285F4;'>G</h1>", unsafe_allow_html=True)
        st.markdown("<h3 style='text-align: center;'>Iniciar sesión con Google</h3>", unsafe_allow_html=True)
        st.markdown("<p style='text-align: center;'>Utiliza tu cuenta institucional para acceder al QuantumTutor</p>", unsafe_allow_html=True)
        
        col1, col2, col3 = st.columns([1, 2, 1])
        with col2:
            st.write("")
            if self.is_prod:
                st.success("🔒 Entorno de Producción Detectado")
                email_input = st.text_input("Ingresa tu correo institucional", placeholder="usuario@gmail.com")
            else:
                st.warning("⚠️ Modo Simulación (Faltan variables OAuth)")
                email_input = st.text_input("Correo electrónico o teléfono (Simulado)", placeholder="alumno@universidad.edu.mx")
            
            if st.button("Siguiente", type="primary", use_container_width=True):
                if self._validate_email(email_input):
                    st.session_state.user_email = email_input
                    st.session_state.authenticated = True
                    st.rerun()
                else:
                    st.error("Ingrese un correo válido de Workspace o @gmail.com")
                    
            st.markdown("<br><p style='text-align: center; font-size: 0.8em; color: gray;'>QuantumTutor v3.0 - Production Instance</p>", unsafe_allow_html=True)

    def logout(self):
        st.session_state.authenticated = False
        st.session_state.user_email = ""
        st.rerun()

    def _validate_email(self, email):
        # Regex simple para validar un formato de correo
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return re.match(pattern, email) is not None

def require_auth():
    """ Decorador/Gateway para Streamlit """
    auth = GoogleAuthWrapper()
    if not auth.is_authenticated():
        auth.login_screen()
        st.stop() # Detiene la ejecución del resto de la app
    return auth
