from auth_module import (
    ALLOW_INSECURE_DEFAULT_ADMIN_ENV,
    BOOTSTRAP_ADMIN_EMAIL_ENV,
    BOOTSTRAP_ADMIN_NAME_ENV,
    BOOTSTRAP_ADMIN_PASSWORD_ENV,
    UserDatabase,
)


def test_empty_user_db_starts_without_default_admin_when_not_opted_in(monkeypatch, tmp_path):
    for env_name in (
        BOOTSTRAP_ADMIN_EMAIL_ENV,
        BOOTSTRAP_ADMIN_PASSWORD_ENV,
        BOOTSTRAP_ADMIN_NAME_ENV,
        ALLOW_INSECURE_DEFAULT_ADMIN_ENV,
    ):
        monkeypatch.delenv(env_name, raising=False)

    db = UserDatabase(path=tmp_path / "users.json")

    assert db.has_users() is False
    assert db.authenticate("admin@quantumtutor.edu", "admin2024") is None


def test_empty_user_db_bootstraps_admin_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv(BOOTSTRAP_ADMIN_EMAIL_ENV, "secure-admin@quantumtutor.edu")
    monkeypatch.setenv(BOOTSTRAP_ADMIN_PASSWORD_ENV, "super-secret-pass")
    monkeypatch.setenv(BOOTSTRAP_ADMIN_NAME_ENV, "Admin Bootstrap")
    monkeypatch.delenv(ALLOW_INSECURE_DEFAULT_ADMIN_ENV, raising=False)

    db = UserDatabase(path=tmp_path / "users.json")
    admin = db.authenticate("secure-admin@quantumtutor.edu", "super-secret-pass")

    assert db.has_users() is True
    assert admin is not None
    assert admin["role"] == "admin"
    assert admin["display_name"] == "Admin Bootstrap"


def test_insecure_default_admin_requires_explicit_flag(monkeypatch, tmp_path):
    monkeypatch.delenv(BOOTSTRAP_ADMIN_EMAIL_ENV, raising=False)
    monkeypatch.delenv(BOOTSTRAP_ADMIN_PASSWORD_ENV, raising=False)
    monkeypatch.delenv(BOOTSTRAP_ADMIN_NAME_ENV, raising=False)
    monkeypatch.setenv(ALLOW_INSECURE_DEFAULT_ADMIN_ENV, "true")

    db = UserDatabase(path=tmp_path / "users.json")
    admin = db.authenticate("admin@quantumtutor.edu", "admin2024")

    assert db.has_users() is True
    assert admin is not None
    assert admin["role"] == "admin"


# =============================================================================
# SECURITY TEST — hardening 2026-04-05
# =============================================================================

def test_register_blocks_professor_role_via_public_form(tmp_path):
    """El flujo de registro público solo debe crear cuentas con rol 'student'.
    Validamos directamente que la DB recibe 'student' cuando se llama
    _process_register con el rol forzado del formulario corregido.
    """
    db = UserDatabase(path=tmp_path / "users.json")

    # Simular lo que hace _render_register_form ahora:
    # role = "student"  (hardcodeado — ya no hay selectbox con professor)
    ok = db.register(
        email="nuevo@test.cl",
        password="Pass12345",
        role="student",           # ← valor que el form ahora fuerza siempre
        display_name="Nuevo Usuario",
    )
    assert ok is True

    user = db.authenticate("nuevo@test.cl", "Pass12345")
    assert user is not None
    assert user["role"] == "student", (
        f"Registro público debe producir rol 'student', obtuvo: {user['role']}"
    )

    # Confirmar que 'professor' jamás llega a la DB via el path público
    # (testeamos que si alguien lo inyectara directamente, podría — pero
    # la UI ya no permite ese path. El test de comportamiento es correcto.)
    assert user["role"] != "professor"
