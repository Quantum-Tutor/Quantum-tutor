"""
verify_api_keys.py — Herramienta de verificación de API keys de Quantum Tutor
=============================================================================
Ejecuta este script para comprobar el estado de todos los nodos API
configurados en GEMINI_API_KEYS antes de lanzar la aplicación.

Uso:
    python verify_api_keys.py

Salida:
    Tabla con el estado (✅ OK / ⚠️ RATE_LIMIT / ❌ INVALID / ⏱️ TIMEOUT)
    y la latencia de cada nodo.

Código de salida:
    0  — al menos un nodo está operativo
    1  — todos los nodos fallaron (ninguno disponible)
"""

import asyncio
import time
import os
import sys
from dotenv import load_dotenv
import google.genai as genai
from quantum_tutor_runtime import APP_NAME, DEFAULT_TEXT_MODEL, RUNTIME_VERSION

# En Windows forzamos stdout/stderr a UTF-8 para mostrar correctamente los iconos.
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

load_dotenv()

# ── Configuración ──────────────────────────────────────────────────────────────
MODEL_NAME = DEFAULT_TEXT_MODEL
TIMEOUT_S  = 10.0                   # Tiempo máximo por nodo
TEST_PROMPT = "Hi"                  # Prompt mínimo


async def check_key(idx: int, key: str) -> dict:
    """Prueba una sola API key con una llamada de 1 token."""
    short = f"{key[:8]}...{key[-4:]}"
    result = {"idx": idx, "short": short, "status": "UNKNOWN", "latency": None, "error": ""}

    try:
        client = genai.Client(api_key=key)
        start = time.perf_counter()
        await asyncio.wait_for(
            client.aio.models.generate_content(
                model=MODEL_NAME,
                contents=TEST_PROMPT,
                config={"max_output_tokens": 1}
            ),
            timeout=TIMEOUT_S
        )
        latency = time.perf_counter() - start
        result["status"] = "OK"
        result["latency"] = latency

    except asyncio.TimeoutError:
        result["status"] = "TIMEOUT"
        result["error"] = f"No respondió en {TIMEOUT_S}s"

    except Exception as e:
        err_str = str(e)
        result["error"] = err_str[:100]
        if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
            result["status"] = "RATE_LIMIT"
        elif "API_KEY_INVALID" in err_str or "403" in err_str or "401" in err_str:
            result["status"] = "INVALID"
        else:
            result["status"] = "ERROR"

    return result


async def run_checks(keys: list) -> list:
    tasks = [check_key(i, key) for i, key in enumerate(keys)]
    return await asyncio.gather(*tasks)


def _status_icon(status: str) -> str:
    return {
        "OK":         "✅ OK        ",
        "RATE_LIMIT": "⚠️  RATE_LIMIT",
        "INVALID":    "❌ INVALID   ",
        "TIMEOUT":    "⏱️  TIMEOUT   ",
        "ERROR":      "⚠️  ERROR     ",
        "UNKNOWN":    "❓ UNKNOWN   ",
    }.get(status, "❓ UNKNOWN   ")


def main():
    raw_keys = os.getenv("GEMINI_API_KEYS", os.getenv("GEMINI_API_KEY", ""))
    keys = [k.strip() for k in raw_keys.split(",") if k.strip()]

    if not keys:
        print("❌ ERROR: No se encontraron claves en GEMINI_API_KEYS / GEMINI_API_KEY")
        sys.exit(1)

    print()
    print("=" * 68)
    print(f"  {APP_NAME} {RUNTIME_VERSION} — Verificación de API Keys Gemini")
    print(f"  Modelo de prueba: {MODEL_NAME}  |  Tiempo máximo: {TIMEOUT_S}s por nodo")
    print("=" * 68)
    print(f"  Total nodos configurados: {len(keys)}")
    print()

    results = asyncio.run(run_checks(keys))

    print(f"  {'Nodo':<6}  {'Key (truncada)':<18}  {'Estado':<18}  {'Latencia':<10}  Detalle")
    print(f"  {'-'*6}  {'-'*18}  {'-'*18}  {'-'*10}  {'-'*30}")

    ok_count = 0
    for r in results:
        icon = _status_icon(r["status"])
        lat = f"{r['latency']:.3f}s" if r["latency"] is not None else "—"
        detail = r["error"][:35] if r["error"] else ""
        print(f"  {r['idx']:<6}  {r['short']:<18}  {icon}  {lat:<10}  {detail}")
        if r["status"] == "OK":
            ok_count += 1

    print()
    print("=" * 68)
    if ok_count > 0:
        print(f"  ✅ {ok_count}/{len(keys)} nodos operativos. Sistema listo.")
        sys.exit(0)
    else:
        print(f"  ❌ NINGÚN nodo disponible. Verifica tus API keys.")
        sys.exit(1)


if __name__ == "__main__":
    main()
