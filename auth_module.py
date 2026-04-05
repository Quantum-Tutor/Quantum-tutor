"""
auth_module.py — QuantumTutor Authentication System v6.1
====================================================================
Componentes:
  - UserDatabase   : CRUD sobre la base local de usuarios con bcrypt hashing
  - RateLimiter    : Anti-brute-force (3 intentos → 60s lockout)
  - AuthSession    : Validación de sesión con expiración idle (4h)
  - QuantumAuthSystem : Gateway principal con UI Celestial-Harmonic
"""

import json
import os
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any

import streamlit as st
from quantum_tutor_runtime import APP_NAME, RUNTIME_VERSION
from quantum_tutor_paths import (
    AUTH_RATE_LIMITS_PATH,
    USERS_DB_PATH,
    resolve_runtime_path,
    write_json_atomic,
)

try:
    import bcrypt
    BCRYPT_AVAILABLE = True
except ImportError:
    BCRYPT_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constantes de configuración
# ---------------------------------------------------------------------------
USERS_FILE = resolve_runtime_path(USERS_DB_PATH, "users.json")
RATE_LIMITS_FILE = resolve_runtime_path(AUTH_RATE_LIMITS_PATH, "rate_limits.json")
SESSION_IDLE_TIMEOUT = 4 * 3600          # 4 horas en segundos
MAX_LOGIN_ATTEMPTS = 3
LOCKOUT_DURATION = 60                    # segundos
BOOTSTRAP_ADMIN_EMAIL_ENV = "QT_BOOTSTRAP_ADMIN_EMAIL"
BOOTSTRAP_ADMIN_PASSWORD_ENV = "QT_BOOTSTRAP_ADMIN_PASSWORD"
BOOTSTRAP_ADMIN_NAME_ENV = "QT_BOOTSTRAP_ADMIN_DISPLAY_NAME"
ALLOW_INSECURE_DEFAULT_ADMIN_ENV = "QT_ALLOW_INSECURE_DEFAULT_ADMIN"

ROLES = {
    "student":   {"label": "Estudiante",  "icon": "🎓"},
    "professor": {"label": "Profesor",    "icon": "👨‍🏫"},
    "admin":     {"label": "Admin",       "icon": "🛡️"},
}

# ---------------------------------------------------------------------------
# CSS Celestial-Harmonic para auth screen
# ---------------------------------------------------------------------------
AUTH_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600&family=Playfair+Display:ital,wght@0,700;1,400&display=swap');

.auth-card {
    background: #212121;
    border: 1px solid #333;
    border-radius: 12px;
    padding: 2.5rem 2.5rem;
    box-shadow: 0 4px 30px rgba(0,0,0,0.6);
    margin: 0 auto;
    max-width: 400px;
    color: white;
}

.auth-logo {
    text-align: center;
    font-family: 'Outfit', sans-serif;
    font-size: 2.2rem;
    font-weight: 600;
    margin-bottom: 0.5rem;
}

.auth-subtitle {
    text-align: center;
    font-family: 'Outfit', sans-serif;
    font-size: 0.95rem;
    color: #ccc;
    margin-bottom: 2rem;
}

.auth-divider {
    border: none;
    border-top: 1px solid #444;
    margin: 1.5rem 0;
    position: relative;
    text-align: center;
}

.auth-divider::after {
    content: "o";
    position: absolute;
    top: -12px;
    left: 50%;
    transform: translateX(-50%);
    background: #212121;
    padding: 0 10px;
    color: #888;
    font-size: 0.9rem;
}

.fake-social-btn {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    background-color: transparent;
    border: 1px solid #555;
    color: white;
    padding: 0.6rem 1rem;
    margin-bottom: 0.8rem;
    border-radius: 8px;
    cursor: default; /* Not functional */
    font-family: 'Outfit', sans-serif;
    font-weight: 500;
}

.fake-social-btn:hover {
    background-color: #333;
}

.lockout-warning {
    background: rgba(255, 60, 60, 0.1);
    border: 1px solid rgba(255, 60, 60, 0.3);
    border-radius: 8px;
    padding: 10px 14px;
    font-family: 'Outfit', sans-serif;
    font-size: 0.85rem;
    color: #ff8080;
    margin: 0.5rem 0;
}
</style>
"""


def _env_flag(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


# ===========================================================================
# UserDatabase
# ===========================================================================
class UserDatabase:
    """
    Gestiona la base local de usuarios con bcrypt hashing.
    Schema por usuario:
        email -> { password_hash, role, display_name, created_at }
    """

    def __init__(self, path: Path = USERS_FILE):
        self.path = path
        self.users: Dict[str, Any] = {}
        self._load()
        if not self.users:
            self._bootstrap_initial_users()

    # -------------------------------------------------------------------------
    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self.users = json.load(f)
            except (json.JSONDecodeError, IOError):
                self.users = {}

    def _save(self):
        write_json_atomic(self.path, self.users, indent=2, ensure_ascii=False)

    def has_users(self) -> bool:
        return bool(self.users)

    # -------------------------------------------------------------------------
    def _hash(self, password: str) -> str:
        if BCRYPT_AVAILABLE:
            return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        raise RuntimeError("CRITICAL: Bcrypt is mandatory for security. Falla de inicio seguro. Instalar dependencias.")

    def _verify(self, password: str, stored_hash: str) -> bool:
        if BCRYPT_AVAILABLE and not stored_hash.startswith("sha256:"):
            try:
                return bcrypt.checkpw(password.encode(), stored_hash.encode())
            except Exception:
                return False
        if not BCRYPT_AVAILABLE:
            raise RuntimeError("CRITICAL: Bcrypt is missing!")
        return False

    # -------------------------------------------------------------------------
    def _create_default_admin(self):
        """Crea cuenta admin por defecto si la DB está vacía."""
        self.register(
            email="admin@quantumtutor.edu",
            password="admin2024",
            role="admin",
            display_name="Administrador del Sistema"
        )

    def _bootstrap_initial_users(self):
        if self._bootstrap_admin_from_env():
            return
        if _env_flag(ALLOW_INSECURE_DEFAULT_ADMIN_ENV, default=False):
            print(
                "[AUTH] WARNING: activado bootstrap inseguro con credenciales "
                "admin por defecto. Usar solo en entorno local controlado."
            )
            self._create_default_admin()

    def _bootstrap_admin_from_env(self) -> bool:
        email = os.getenv(BOOTSTRAP_ADMIN_EMAIL_ENV, "").strip().lower()
        password = os.getenv(BOOTSTRAP_ADMIN_PASSWORD_ENV, "").strip()
        display_name = os.getenv(
            BOOTSTRAP_ADMIN_NAME_ENV,
            "Administrador del Sistema",
        ).strip()

        if not email or not password:
            return False

        self.register(
            email=email,
            password=password,
            role="admin",
            display_name=display_name or "Administrador del Sistema",
        )
        return True

    # -------------------------------------------------------------------------
    def user_exists(self, email: str) -> bool:
        return email.lower() in self.users

    def register(self, email: str, password: str, role: str = "student",
                 display_name: str = "") -> bool:
        email = email.lower().strip()
        if self.user_exists(email):
            return False
        self.users[email] = {
            "password_hash": self._hash(password),
            "role": role,
            "display_name": display_name or email.split("@")[0].capitalize(),
            "created_at": datetime.now().isoformat()
        }
        self._save()
        return True

    def authenticate(self, email: str, password: str) -> Optional[Dict]:
        email = email.lower().strip()
        user = self.users.get(email)
        if not user:
            return None
        if self._verify(password, user["password_hash"]):
            return {
                "email": email,
                "role": user["role"],
                "display_name": user["display_name"],
                "created_at": user["created_at"]
            }
        return None

    def get_all_users_summary(self) -> list:
        return [
            {"email": e, "role": u["role"], "display_name": u["display_name"],
             "created_at": u.get("created_at", "?")}
            for e, u in self.users.items()
        ]


# ===========================================================================
# RateLimiter (Persistent)
# ===========================================================================
class RateLimiter:
    """
    Anti-brute-force: bloquea un username tras MAX_LOGIN_ATTEMPTS fallos.
    Guarda en disco el estado de lockout para persistir tras reloads.
    """

    @staticmethod
    def _load_state() -> dict:
        if RATE_LIMITS_FILE.exists():
            try:
                with open(RATE_LIMITS_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except:
                pass
        return {}
        
    @staticmethod
    def _save_state(state: dict):
        write_json_atomic(RATE_LIMITS_FILE, state, ensure_ascii=False)

    @classmethod
    def is_locked(cls, identifier: str) -> tuple[bool, float]:
        """Retorna (locked, seconds_remaining)."""
        state = cls._load_state()
        data = state.get(identifier, {})
        if not data:
            return False, 0.0
        if data.get("locked_until", 0) > time.time():
            return True, data["locked_until"] - time.time()
        
        # Cleanup expired
        if "locked_until" in data and data["locked_until"] <= time.time():
            cls.reset(identifier)
        return False, 0.0

    @classmethod
    def record_failure(cls, identifier: str):
        state = cls._load_state()
        entry = state.get(identifier, {"attempts": 0, "locked_until": 0})
        entry["attempts"] = entry.get("attempts", 0) + 1
        if entry["attempts"] >= MAX_LOGIN_ATTEMPTS:
            entry["locked_until"] = time.time() + LOCKOUT_DURATION
            entry["attempts"] = 0   # reset para próximo ciclo
        state[identifier] = entry
        cls._save_state(state)

    @classmethod
    def reset(cls, identifier: str):
        state = cls._load_state()
        if identifier in state:
            state.pop(identifier, None)
            cls._save_state(state)


# ===========================================================================
# AuthSession (In-Memory)
# ===========================================================================
class AuthSession:
    """
    Maneja el estado autenticado solo en st.session_state.
    No expone tokens de sesión en query params ni persiste sesiones en disco.
    """

    @classmethod
    def _init(cls):
        defaults = {
            "auth_authenticated": False,
            "auth_user": None,
            "auth_last_activity": 0.0,
        }
        for k, v in defaults.items():
            if k not in st.session_state:
                st.session_state[k] = v

    @classmethod
    def is_authenticated(cls) -> bool:
        cls._init()
        if not st.session_state["auth_authenticated"]:
            return False
        idle = time.time() - st.session_state["auth_last_activity"]
        if idle > SESSION_IDLE_TIMEOUT:
            cls.logout(reason="timeout")
            return False
        cls.touch()
        return True

    @classmethod
    def login(cls, user_data: dict):
        cls._init()
        st.session_state["auth_authenticated"] = True
        st.session_state["auth_user"] = dict(user_data)
        st.session_state["auth_last_activity"] = time.time()

    @classmethod
    def logout(cls, reason: str = "manual"):
        cls._init()
        st.session_state["auth_authenticated"] = False
        st.session_state["auth_user"] = None
        st.session_state["auth_last_activity"] = 0.0
        if reason == "timeout":
            st.session_state["_auth_timeout"] = True

    @classmethod
    def touch(cls):
        cls._init()
        st.session_state["auth_last_activity"] = time.time()

    @classmethod
    def get_user(cls) -> Optional[dict]:
        return st.session_state.get("auth_user")

    @classmethod
    def get_role(cls) -> str:
        u = cls.get_user()
        return u["role"] if u else "student"

    @classmethod
    def get_email(cls) -> str:
        u = cls.get_user()
        return u["email"] if u else ""

    @classmethod
    def get_display_name(cls) -> str:
        u = cls.get_user()
        return u["display_name"] if u else ""


# ===========================================================================
# QuantumAuthSystem (main gateway)
# ===========================================================================
class QuantumAuthSystem:
    """
    Punto de entrada principal para autenticación en Streamlit.
    Interfaz compatible v1→v2 con get_user_email() y logout().
    """

    def __init__(self):
        self.db = UserDatabase()

    # ── Compat v1 ────────────────────────────────────────────────────────────
    def is_authenticated(self) -> bool:
        return AuthSession.is_authenticated()

    def get_user_email(self) -> str:
        return AuthSession.get_email()

    def get_display_name(self) -> str:
        return AuthSession.get_display_name()

    def get_role(self) -> str:
        return AuthSession.get_role()

    def logout(self):
        AuthSession.logout()
        st.rerun()

    # ── UI ───────────────────────────────────────────────────────────────────
    def login_screen(self):
        """Renderiza la pantalla de login/registro con diseño Celestial-Harmonic."""
        st.markdown(AUTH_CSS, unsafe_allow_html=True)

        # Detectar timeout previo
        if st.session_state.pop("_auth_timeout", False):
            st.warning("⏱️ Tu sesión expiró por inactividad. Por favor inicia sesión de nuevo.")

        # Centrar card
        col_l, col_c, col_r = st.columns([1, 2, 1])
        with col_c:
            st.markdown("<div class='auth-logo'>Bienvenidos</div>", unsafe_allow_html=True)
            st.markdown(
                "<div class='auth-subtitle'>Inicia sesión o suscríbete para obtener respuestas más inteligentes, cargar archivos e imágenes, y más.</div>",
                unsafe_allow_html=True
            )
            if not self.db.has_users():
                st.info(
                    "No hay usuarios provisionados todavía. Puedes crear una cuenta normal aquí, "
                    "o bootstrapear un admin con "
                    f"`{BOOTSTRAP_ADMIN_EMAIL_ENV}` y `{BOOTSTRAP_ADMIN_PASSWORD_ENV}` "
                    "antes de iniciar la app."
                )

            with st.container(border=True):
                tab_login, tab_register = st.tabs(["🔐 Iniciar Sesión", "📝 Registrarse"])

                with tab_login:
                    self._render_login_form()

                with tab_register:
                    self._render_register_form()

            st.markdown(
                "<hr class='auth-divider'>"
                "<p style='text-align:center;font-size:0.72rem;color:#555;font-family:Outfit,sans-serif;'>"
                f"{APP_NAME} Auth · {RUNTIME_VERSION} · Galindo &amp; Pascual Knowledge Core"
                "</p>",
                unsafe_allow_html=True
            )

    # ── Login form ────────────────────────────────────────────────────────────
    def _render_login_form(self):
        st.markdown(
            """
            <div class='fake-social-btn'>G Continuar con Google</div>
            <div class='fake-social-btn'>🍎 Continuar con Apple</div>
            <div class='fake-social-btn'>📞 Continuar con el teléfono</div>
            <hr class='auth-divider'>
            """, 
            unsafe_allow_html=True
        )

        with st.form("login_form", border=False):
            email = st.text_input(
                "Dirección de correo electrónico", key="login_email",
                placeholder="alumno@universidad.edu.mx"
            )
            password = st.text_input(
                "Contraseña", key="login_password",
                type="password", placeholder="••••••••"
            )

            # Comprobar lockout persistentmente
            locked, remaining = RateLimiter.is_locked(email.lower().strip() if email else "")
            
            btn_disabled = False
            if locked:
                st.markdown(
                    f"<div class='lockout-warning'>🔒 Demasiados intentos. "
                    f"Espera <b>{int(remaining)}s</b> antes de intentar de nuevo.</div>",
                    unsafe_allow_html=True
                )
                btn_disabled = True

            submitted = st.form_submit_button("Continuar", type="primary", use_container_width=True, disabled=btn_disabled)
            if submitted:
                self._process_login(email, password)

    def _process_login(self, email: str, password: str):
        email = (email or "").strip()
        if not email or not password:
            st.error("Por favor completa todos los campos.")
            return
        if not self._validate_email(email):
            st.error("Formato de correo inválido.")
            return

        user = self.db.authenticate(email, password)
        if user:
            RateLimiter.reset(email.lower())
            AuthSession.login(user)
            st.toast("✅ Sesión iniciada correctamente", icon="⚛️")
            st.rerun()
        else:
            RateLimiter.record_failure(email.lower())
            locked, rem = RateLimiter.is_locked(email.lower())
            if locked:
                st.error(f"🔒 Cuenta bloqueada temporalmente ({LOCKOUT_DURATION}s) por múltiples intentos fallidos.")
                time.sleep(1.5)
                st.rerun() # Force UI update immediately to trigger countdown logic
            else:
                state = RateLimiter._load_state().get(email.lower(), {})
                attempts = state.get("attempts", 0)
                remaining_attempts = MAX_LOGIN_ATTEMPTS - attempts
                st.error(f"❌ Credenciales incorrectas. Intentos restantes: {remaining_attempts}")

    # ── Register form ─────────────────────────────────────────────────────────
    def _render_register_form(self):
        with st.form("register_form", border=False):
            display_name = st.text_input(
                "Nombre completo", key="reg_name",
                placeholder="Prof. García López"
            )
            email = st.text_input(
                "Correo electrónico", key="reg_email",
                placeholder="usuario@universidad.edu.mx"
            )
            password = st.text_input(
                "Contraseña (mín. 8 caracteres)", key="reg_password",
                type="password"
            )
            password2 = st.text_input(
                "Confirmar contraseña", key="reg_password2",
                type="password"
            )

            # SECURITY: el rol professor no puede auto-asignarse en registro público.
            # Solo un administrador puede elevar el rol de un usuario existente.
            role = "student"
            st.caption(
                "🎓 Las cuentas de Profesor son asignadas por el Administrador del sistema. "
                "Regístrate como Estudiante y contacta al admin para elevar tu rol."
            )

            submitted = st.form_submit_button("Crear Cuenta", type="primary", use_container_width=True)
            if submitted:
                self._process_register(email, password, password2, display_name, role)

    def _process_register(self, email, password, password2, display_name, role):
        email = (email or "").strip()
        if not all([email, password, password2, display_name]):
            st.error("Todos los campos son obligatorios.")
            return
        if not self._validate_email(email):
            st.error("Formato de correo inválido.")
            return
        if len(password) < 8:
            st.error("La contraseña debe tener al menos 8 caracteres.")
            return
        if password != password2:
            st.error("Las contraseñas no coinciden.")
            return
        if self.db.user_exists(email):
            st.error("Este correo ya está registrado. Inicia sesión.")
            return

        ok = self.db.register(email, password, role=role, display_name=display_name)
        if ok:
            st.success(f"✅ Cuenta creada exitosamente como {ROLES[role]['icon']} {ROLES[role]['label']}. ¡Ahora inicia sesión!")
        else:
            st.error("Error al crear la cuenta. Intenta de nuevo.")

    # ── Validation ────────────────────────────────────────────────────────────
    @staticmethod
    def _validate_email(email: str) -> bool:
        pattern = r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"
        return bool(re.match(pattern, email))


# ===========================================================================
# Public API — drop-in compatible con auth_module v1
# ===========================================================================
def require_auth() -> QuantumAuthSystem:
    """
    Gateway de autenticación para Streamlit.
    Retorna el sistema de auth si el usuario está autenticado.
    Detiene la ejecución de Streamlit y muestra login_screen() si no.
    """
    auth = QuantumAuthSystem()
    if not auth.is_authenticated():
        auth.login_screen()
        st.stop()
    return auth
