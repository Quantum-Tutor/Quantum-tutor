"""
Smoke test local de navegador para Quantum Tutor.

Levanta la app Streamlit, abre Chrome headless con DevTools Protocol,
inicia sesión con el admin por defecto, envía una consulta breve y
captura screenshots del flujo.
"""

from __future__ import annotations

import asyncio
import base64
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

import websockets


ROOT_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT_DIR / "outputs" / "ui_live_smoke"
STREAMLIT_PORT = 8501
CDP_PORT = 9222
APP_URL = f"http://127.0.0.1:{STREAMLIT_PORT}"
SMOKE_LOGIN_EMAIL = os.getenv("QT_BOOTSTRAP_ADMIN_EMAIL", "admin@quantumtutor.edu")
SMOKE_LOGIN_PASSWORD = os.getenv("QT_BOOTSTRAP_ADMIN_PASSWORD", "admin2024")
CHROME_CANDIDATES = [
    Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe"),
    Path(r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"),
    Path(r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"),
]


def _find_browser() -> Path:
    for candidate in CHROME_CANDIDATES:
        if candidate.exists():
            return candidate
    raise FileNotFoundError("No se encontró Chrome/Edge para la prueba local.")


def _wait_for_http(url: str, timeout: float = 90.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2.0) as response:
                if response.status < 500:
                    return
        except Exception:
            time.sleep(1.0)
    raise TimeoutError(f"No fue posible alcanzar {url} antes del timeout.")


def _http_json(url: str) -> Any:
    with urllib.request.urlopen(url, timeout=5.0) as response:
        return json.loads(response.read().decode("utf-8"))


def _select_page_target(targets: list[dict[str, Any]], expected_url: str | None = None) -> dict[str, Any]:
    page_targets = [
        target
        for target in targets
        if target.get("type") == "page" and target.get("webSocketDebuggerUrl")
    ]
    if not page_targets:
        raise RuntimeError("No hay targets CDP de tipo page disponibles.")

    if expected_url:
        normalized_expected = expected_url.rstrip("/")
        matching_targets = [
            target
            for target in page_targets
            if (target.get("url") or "").rstrip("/").startswith(normalized_expected)
        ]
        if matching_targets:
            return matching_targets[0]

    local_targets = [
        target
        for target in page_targets
        if "127.0.0.1" in (target.get("url") or "") or "localhost" in (target.get("url") or "")
    ]
    if local_targets:
        return local_targets[0]

    return page_targets[0]


def _wait_for_page_target(expected_url: str, timeout: float = 30.0, interval: float = 0.5) -> dict[str, Any]:
    deadline = time.time() + timeout
    last_targets: list[dict[str, Any]] = []
    while time.time() < deadline:
        try:
            targets = _http_json(f"http://127.0.0.1:{CDP_PORT}/json/list")
        except Exception:
            time.sleep(interval)
            continue

        last_targets = targets
        try:
            target = _select_page_target(targets, expected_url)
        except RuntimeError:
            time.sleep(interval)
            continue

        if (target.get("url") or "").rstrip("/").startswith(expected_url.rstrip("/")):
            return target
        time.sleep(interval)

    visible_targets = [
        {
            "type": target.get("type"),
            "title": target.get("title"),
            "url": target.get("url"),
        }
        for target in last_targets
        if target.get("type") == "page"
    ]
    raise TimeoutError(
        f"No apareció un target CDP para {expected_url}. Targets visibles: {json.dumps(visible_targets[:6], ensure_ascii=False)}"
    )


def _start_streamlit() -> subprocess.Popen[str]:
    env = os.environ.copy()
    env["PYTHONIOENCODING"] = "utf-8"
    env["BROWSER"] = "none"
    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        "app_quantum_tutor.py",
        "--server.headless=true",
        f"--server.port={STREAMLIT_PORT}",
        "--server.address=127.0.0.1",
        "--browser.gatherUsageStats=false",
        "--server.fileWatcherType=none",
    ]
    log_path = OUTPUT_DIR / "streamlit_live_smoke.log"
    log_file = log_path.open("w", encoding="utf-8")
    return subprocess.Popen(
        command,
        cwd=ROOT_DIR,
        stdout=log_file,
        stderr=subprocess.STDOUT,
        text=True,
        env=env,
    )


def _start_browser(browser_path: Path, user_data_dir: Path) -> subprocess.Popen[bytes]:
    args = [
        str(browser_path),
        "--headless=new",
        "--disable-gpu",
        "--no-first-run",
        "--no-default-browser-check",
        "--disable-background-networking",
        "--disable-sync",
        "--window-size=1600,1200",
        f"--remote-debugging-port={CDP_PORT}",
        f"--user-data-dir={user_data_dir}",
        APP_URL,
    ]
    return subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


class CDPClient:
    def __init__(self, websocket_url: str):
        self.websocket_url = websocket_url
        self.ws = None
        self._msg_id = 0

    async def __aenter__(self) -> "CDPClient":
        self.ws = await websockets.connect(self.websocket_url, max_size=20_000_000)
        return self

    async def __aexit__(self, exc_type, exc, tb) -> None:
        if self.ws:
            await self.ws.close()

    async def call(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        assert self.ws is not None
        self._msg_id += 1
        current_id = self._msg_id
        payload = {"id": current_id, "method": method, "params": params or {}}
        await self.ws.send(json.dumps(payload))

        while True:
            raw = await self.ws.recv()
            message = json.loads(raw)
            if message.get("id") != current_id:
                continue
            if "error" in message:
                raise RuntimeError(f"CDP error en {method}: {message['error']}")
            return message.get("result", {})

    async def evaluate(self, expression: str, await_promise: bool = False) -> Any:
        result = await self.call(
            "Runtime.evaluate",
            {
                "expression": expression,
                "returnByValue": True,
                "awaitPromise": await_promise,
            },
        )
        return result.get("result", {}).get("value")

    async def wait_for(self, expression: str, timeout: float = 45.0, interval: float = 0.5) -> Any:
        deadline = time.time() + timeout
        while time.time() < deadline:
            value = await self.evaluate(expression)
            if value:
                return value
            await asyncio.sleep(interval)
        raise TimeoutError(f"Timeout esperando condición JS: {expression}")


def _set_input_js(selector: str, value: str, is_textarea: bool = False) -> str:
    prototype = "HTMLTextAreaElement" if is_textarea else "HTMLInputElement"
    return f"""
    (() => {{
        const el = document.querySelector({json.dumps(selector)});
        if (!el) return false;
        el.focus();
        el.click();
        if (typeof el.select === 'function') {{
            el.select();
        }}
        const previousValue = el.value;
        const setter = Object.getOwnPropertyDescriptor(window.{prototype}.prototype, "value").set;
        setter.call(el, {json.dumps(value)});
        el.setAttribute("value", {json.dumps(value)});
        if (el._valueTracker) {{
            el._valueTracker.setValue(previousValue);
        }}
        el.dispatchEvent(new Event("input", {{ bubbles: true }}));
        el.dispatchEvent(new Event("change", {{ bubbles: true }}));
        el.dispatchEvent(new Event("blur", {{ bubbles: true }}));
        return el.value === {json.dumps(value)};
    }})()
    """


async def _focus_selector(cdp: CDPClient, selector: str) -> None:
    focused = await cdp.evaluate(
        f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return false;
            el.focus();
            el.click();
            return true;
        }})()
        """
    )
    if not focused:
        raise RuntimeError(f"No se pudo enfocar el selector {selector}")


async def _clear_and_type_input(cdp: CDPClient, selector: str, value: str) -> None:
    await _focus_selector(cdp, selector)
    await cdp.evaluate(
        f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return false;
            el.value = '';
            el.dispatchEvent(new Event('input', {{ bubbles: true }}));
            el.dispatchEvent(new Event('change', {{ bubbles: true }}));
            return true;
        }})()
        """
    )
    await cdp.call("Input.insertText", {"text": value})
    await cdp.wait_for(
        f"""
        (() => {{
            const el = document.querySelector({json.dumps(selector)});
            return !!el && el.value === {json.dumps(value)};
        }})()
        """,
        timeout=10.0,
        interval=0.2,
    )


async def _capture_screenshot(cdp: CDPClient, path: Path) -> None:
    data = await cdp.call("Page.captureScreenshot", {"format": "png", "fromSurface": True})
    path.write_bytes(base64.b64decode(data["data"]))


async def _run_browser_flow() -> dict[str, Any]:
    browser_path = _find_browser()
    temp_profile = Path(tempfile.mkdtemp(prefix="qt_live_smoke_"))
    browser = _start_browser(browser_path, temp_profile)
    try:
        _wait_for_http(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=30.0)
        page_target = _wait_for_page_target(APP_URL, timeout=30.0)
        ws_url = page_target["webSocketDebuggerUrl"]

        async with CDPClient(ws_url) as cdp:
            await cdp.call("Page.enable")
            await cdp.call("Runtime.enable")
            await cdp.call("DOM.enable")

            try:
                await cdp.wait_for("document.body && document.body.innerText.includes('Iniciar Sesión')", timeout=90.0)
                await _capture_screenshot(cdp, OUTPUT_DIR / "01_login.png")

                await cdp.evaluate(
                    _set_input_js(
                        'input[aria-label=\"Dirección de correo electrónico\"]',
                        SMOKE_LOGIN_EMAIL,
                    )
                )
                await cdp.evaluate(
                    _set_input_js('input[type=\"password\"]', SMOKE_LOGIN_PASSWORD)
                )
                await cdp.wait_for(
                    """
                    (() => {
                        const email = document.querySelector('input[aria-label="Dirección de correo electrónico"]');
                        const password = document.querySelector('input[type="password"]');
                        return !!email && !!password &&
                               email.value.length > 0 &&
                               password.value.length > 0;
                    })()
                    """,
                    timeout=10.0,
                    interval=0.2,
                )
                await cdp.evaluate(
                    """
                    (() => {
                        const btn = [...document.querySelectorAll("button")].find(
                            b => b.innerText && b.innerText.includes("Continuar")
                        );
                        if (!btn) return false;
                        btn.click();
                        return true;
                    })()
                    """
                )

                await cdp.wait_for("document.body.innerText.includes('Quantum Tutor Avanzado')", timeout=90.0)
                await _capture_screenshot(cdp, OUTPUT_DIR / "02_logged_in.png")

                dom_debug = await cdp.evaluate(
                    """
                    (() => ({
                        buttons: [...document.querySelectorAll("button")].map(b => ({
                            text: (b.innerText || '').trim(),
                            aria: b.getAttribute('aria-label'),
                            testid: b.getAttribute('data-testid')
                        })).slice(0, 40),
                        textareas: [...document.querySelectorAll("textarea")].map(t => ({
                            placeholder: t.getAttribute('placeholder'),
                            aria: t.getAttribute('aria-label'),
                            testid: t.getAttribute('data-testid')
                        })),
                        tabs: [...document.querySelectorAll('[role=\"tab\"]')].map(t => t.innerText.trim())
                    }))()
                    """
                )

                chat_query = "Hola"
                await cdp.wait_for("document.querySelector('[data-testid=\"stChatInput\"] textarea') !== null", timeout=60.0)
                await cdp.evaluate(
                    """
                    (() => {
                        const textarea = document.querySelector('[data-testid="stChatInput"] textarea');
                        if (!textarea) return false;
                        textarea.focus();
                        return true;
                    })()
                    """
                )
                await cdp.call("Input.insertText", {"text": chat_query})
                await cdp.wait_for(
                    "document.querySelector('[data-testid=\"stChatInput\"] textarea').value.length > 0",
                    timeout=10.0,
                )
                sent = await cdp.evaluate(
                    """
                    (() => {
                        const button = document.querySelector('[data-testid="stChatInputSubmitButton"]');
                        if (button) {
                            button.click();
                            return 'button-click';
                        }
                        const textarea = document.querySelector('[data-testid="stChatInput"] textarea');
                        if (!textarea) return 'textarea-missing';
                        textarea.focus();
                        textarea.dispatchEvent(new KeyboardEvent('keydown', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
                        textarea.dispatchEvent(new KeyboardEvent('keyup', {key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true}));
                        return 'enter-dispatch';
                    })()
                    """
                )

                await cdp.wait_for(
                    f"document.body.innerText.includes({json.dumps(chat_query)}) || document.querySelectorAll('[data-testid=\"stChatMessage\"]').length >= 1",
                    timeout=30.0,
                    interval=0.5,
                )
                await cdp.wait_for(
                    "document.querySelectorAll('[data-testid=\"stChatMessage\"]').length >= 2 && !document.body.innerText.includes('Procesando respuesta (v6)...')",
                    timeout=120.0,
                    interval=1.0,
                )
                await _capture_screenshot(cdp, OUTPUT_DIR / "03_chat_response.png")

                assistant_messages = await cdp.evaluate(
                    """
                    (() => {
                        const blocks = [...document.querySelectorAll('[data-testid="stChatMessage"]')];
                        return blocks.map(b => (b.innerText || '').trim()).filter(Boolean);
                    })()
                    """
                )

                await cdp.evaluate(
                    """
                    (() => {
                        const tab = [...document.querySelectorAll('[role="tab"]')].find(
                            t => (t.innerText || '').includes('Dashboard Analítico Cognitivo')
                        );
                        if (!tab) return false;
                        tab.click();
                        return true;
                    })()
                    """
                )
                await cdp.wait_for("document.body.innerText.includes('Perfil de Comprensión Cuántica')", timeout=60.0)
                await _capture_screenshot(cdp, OUTPUT_DIR / "04_analytics_tab.png")

                body_text = await cdp.evaluate("document.body.innerText")
                return {
                    "browser": str(browser_path),
                    "chat_submit_method": sent,
                    "dom_debug": dom_debug,
                    "assistant_messages": assistant_messages,
                    "body_excerpt": body_text[:4000],
                }
            except Exception as exc:
                await _capture_screenshot(cdp, OUTPUT_DIR / "99_failure_state.png")
                failure_body = await cdp.evaluate("document.body ? document.body.innerText : ''")
                failure_debug = await cdp.evaluate(
                    """
                    (() => ({
                        buttons: [...document.querySelectorAll("button")].map(b => ({
                            text: (b.innerText || '').trim(),
                            aria: b.getAttribute('aria-label'),
                            testid: b.getAttribute('data-testid')
                        })).slice(0, 60),
                        inputs: [...document.querySelectorAll('input, textarea')].map(el => ({
                            tag: el.tagName,
                            type: el.getAttribute('type'),
                            placeholder: el.getAttribute('placeholder'),
                            aria: el.getAttribute('aria-label'),
                            testid: el.getAttribute('data-testid')
                        })).slice(0, 60)
                    }))()
                    """
                )
                raise RuntimeError(
                    json.dumps(
                        {
                            "error": str(exc),
                            "body_excerpt": failure_body[:4000],
                            "dom_debug": failure_debug,
                        },
                        ensure_ascii=False,
                    )
                ) from exc
    finally:
        browser.terminate()
        try:
            browser.wait(timeout=10)
        except subprocess.TimeoutExpired:
            browser.kill()
        shutil.rmtree(temp_profile, ignore_errors=True)


async def run() -> dict[str, Any]:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    streamlit = _start_streamlit()
    try:
        _wait_for_http(APP_URL, timeout=90.0)
        result = await _run_browser_flow()
        result["status"] = "ok"
        return result
    finally:
        streamlit.terminate()
        try:
            streamlit.wait(timeout=10)
        except subprocess.TimeoutExpired:
            streamlit.kill()


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    result = asyncio.run(run())
    output_path = OUTPUT_DIR / "live_smoke_result.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
