"""
Diagnostico vivo de navegador para Quantum Tutor.

Ejecuta una bateria mas profunda que el smoke test basico:
- login
- varias consultas reales
- referencias visuales
- panel lateral y metricas
- botones de accion
- scroll buttons
- nueva sesion y logout
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unicodedata
from pathlib import Path
from typing import Any

from galindo_page_map import resolve_galindo_reference
from ui_live_smoke_test import (
    APP_URL,
    CDP_PORT,
    ROOT_DIR,
    SMOKE_LOGIN_EMAIL,
    SMOKE_LOGIN_PASSWORD,
    STREAMLIT_PORT,
    CDPClient,
    _capture_screenshot,
    _find_browser,
    _start_browser,
    _start_streamlit,
    _wait_for_http,
    _wait_for_page_target,
)


OUTPUT_DIR = ROOT_DIR / "outputs" / "ui_live_diagnostics"


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    stripped = "".join(ch for ch in normalized if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", stripped).strip().lower()


def _slugify(text: str) -> str:
    slug = _normalize_text(text)
    slug = re.sub(r"[^a-z0-9]+", "_", slug).strip("_")
    return slug or "step"


def _map_caption_to_file(caption: str) -> str | None:
    if "Galindo & Pascual p." in caption:
        page_num = caption.rsplit(" ", 1)[-1]
        resolved_ref = resolve_galindo_reference(display_page=page_num)
        image_filename = resolved_ref.get("image_filename")
        if image_filename:
            return str(ROOT_DIR / "static_web" / "references" / image_filename)
        return None
    if "Cohen Tannoudji p." in caption:
        page_num = caption.rsplit(" ", 1)[-1]
        return str(ROOT_DIR / "static_web" / "references" / f"cohen_page_{page_num}.png")
    if "Sakurai p." in caption:
        page_num = caption.rsplit(" ", 1)[-1]
        return str(ROOT_DIR / "static_web" / "references" / f"sakurai_page_{page_num}.png")
    return None


async def _wait_for_body_contains(cdp: CDPClient, text: str, timeout: float = 60.0) -> None:
    normalized = _normalize_text(text)
    await cdp.wait_for(
        f"""
        (() => {{
            const body = document.body ? document.body.innerText : '';
            const normalizedBody = body.normalize('NFD').replace(/[\\u0300-\\u036f]/g, '').toLowerCase();
            return normalizedBody.includes({json.dumps(normalized)});
        }})()
        """,
        timeout=timeout,
        interval=0.5,
    )


async def _click_button(cdp: CDPClient, label_substring: str) -> bool:
    target = _normalize_text(label_substring)
    return bool(
        await cdp.evaluate(
            f"""
            (() => {{
                const normalize = (value) => (value || '')
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '')
                    .replace(/\\s+/g, ' ')
                    .trim()
                    .toLowerCase();
                const target = {json.dumps(target)};
                const btn = [...document.querySelectorAll('button')].find(
                    (button) => normalize(button.innerText).includes(target)
                );
                if (!btn) return false;
                btn.click();
                return true;
            }})()
            """
        )
    )


async def _click_tab(cdp: CDPClient, label_substring: str) -> bool:
    target = _normalize_text(label_substring)
    return bool(
        await cdp.evaluate(
            f"""
            (() => {{
                const normalize = (value) => (value || '')
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '')
                    .replace(/\\s+/g, ' ')
                    .trim()
                    .toLowerCase();
                const target = {json.dumps(target)};
                const tab = [...document.querySelectorAll('[role="tab"]')].find(
                    (node) => normalize(node.innerText).includes(target)
                );
                if (!tab) return false;
                tab.click();
                return true;
            }})()
            """
        )
    )


async def _get_body_text(cdp: CDPClient) -> str:
    return await cdp.evaluate("document.body ? document.body.innerText : ''")


async def _get_chat_blocks(cdp: CDPClient) -> list[dict[str, Any]]:
    blocks = await cdp.evaluate(
        """
        (() => {
            return [...document.querySelectorAll('[data-testid="stChatMessage"]')].map((block, index) => ({
                index,
                text: (block.innerText || '').trim(),
            }));
        })()
        """
    )
    return blocks or []


async def _get_chat_messages(cdp: CDPClient) -> list[str]:
    blocks = await _get_chat_blocks(cdp)
    return [str(block.get("text", "")).strip() for block in blocks if str(block.get("text", "")).strip()]


async def _get_reference_captions(cdp: CDPClient, block_index: int | None = None) -> list[str]:
    block_index_json = json.dumps(block_index)
    captions = await cdp.evaluate(
        """
        (() => {
            const blocks = [...document.querySelectorAll('[data-testid="stChatMessage"]')];
            const blockIndex = __BLOCK_INDEX__;
            const scope = Number.isInteger(blockIndex) ? (blocks[blockIndex] || blocks.at(-1) || document) : document;
            const values = [...scope.querySelectorAll('*')]
                .map((node) => (node.innerText || '').trim())
                .filter((text) => text.startsWith('Extracto: '));
            return [...new Set(values)];
        })()
        """
        .replace("__BLOCK_INDEX__", block_index_json)
    )
    return captions or []


async def _wait_for_chat_settle(cdp: CDPClient, *, min_block_count: int, timeout: float = 12.0) -> None:
    start = time.perf_counter()
    stable_polls = 0
    last_signature = None

    while time.perf_counter() - start < timeout:
        state = await cdp.evaluate(
            f"""
            (() => {{
                const blocks = [...document.querySelectorAll('[data-testid="stChatMessage"]')];
                const body = document.body ? document.body.innerText : '';
                const lastText = blocks.length ? (blocks.at(-1).innerText || '').trim() : '';
                const statsMatch = body.match(/(\\d+)\\s+W-CALLS\\s+(\\d+)\\s+RAG-ANCHORS/);
                return {{
                    blockCount: blocks.length,
                    hasSpinner: body.includes('Procesando respuesta (v6)...'),
                    lastText,
                    stats: statsMatch ? `${{statsMatch[1]}}-${{statsMatch[2]}}` : 'na',
                }};
            }})()
            """
        )
        if state["blockCount"] >= min_block_count and not state["hasSpinner"]:
            signature = (state["blockCount"], state["lastText"], state["stats"])
            if signature == last_signature:
                stable_polls += 1
            else:
                stable_polls = 0
                last_signature = signature
            if stable_polls >= 2:
                return
        await asyncio.sleep(0.6)


async def _get_visible_stats(cdp: CDPClient) -> dict[str, int | None]:
    body = await _get_body_text(cdp)
    match = re.search(r"(\d+)\s+W-CALLS\s+(\d+)\s+RAG-ANCHORS", body)
    if not match:
        return {"wolfram_calls": None, "rag_anchors": None}
    return {
        "wolfram_calls": int(match.group(1)),
        "rag_anchors": int(match.group(2)),
    }


async def _get_user_panel_snapshot(cdp: CDPClient) -> dict[str, Any]:
    body = await _get_body_text(cdp)
    normalized_body = _normalize_text(body)
    return {
        "has_user_active": "usuario activo" in normalized_body,
        "has_admin_label": "admin" in normalized_body,
        "has_api_key_health": "api key health" in normalized_body,
        "has_learning_analytics": "learning analytics" in normalized_body,
        "stats": await _get_visible_stats(cdp),
    }


async def _send_chat_prompt(cdp: CDPClient, prompt: str, screenshot_name: str) -> dict[str, Any]:
    await _click_tab(cdp, "Interfaz de Sesion Cuantica")
    await cdp.wait_for(
        "document.querySelector('[data-testid=\"stChatInput\"] textarea') !== null",
        timeout=30.0,
        interval=0.5,
    )

    before_blocks = await _get_chat_blocks(cdp)
    before_count = len(before_blocks)

    await cdp.evaluate(
        """
        (() => {
            const textarea = document.querySelector('[data-testid="stChatInput"] textarea');
            if (!textarea) return false;
            textarea.focus();
            const setter = Object.getOwnPropertyDescriptor(window.HTMLTextAreaElement.prototype, 'value').set;
            setter.call(textarea, '');
            textarea.dispatchEvent(new Event('input', { bubbles: true }));
            textarea.dispatchEvent(new Event('change', { bubbles: true }));
            return true;
        })()
        """
    )
    await cdp.call("Input.insertText", {"text": prompt})
    await cdp.wait_for(
        """
        (() => {
            const textarea = document.querySelector('[data-testid="stChatInput"] textarea');
            return !!textarea && textarea.value.length > 0;
        })()
        """,
        timeout=10.0,
        interval=0.2,
    )

    submitted_with = await cdp.evaluate(
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

    start = time.perf_counter()
    await cdp.wait_for(
        f"""
        (() => {{
            const body = document.body ? document.body.innerText : '';
            const count = document.querySelectorAll('[data-testid="stChatMessage"]').length;
            return count >= {before_count + 2} && !body.includes('Procesando respuesta (v6)...');
        }})()
        """,
        timeout=150.0,
        interval=1.0,
    )
    await _wait_for_chat_settle(cdp, min_block_count=before_count + 2)
    duration = time.perf_counter() - start

    await _capture_screenshot(cdp, OUTPUT_DIR / screenshot_name)

    blocks = await _get_chat_blocks(cdp)
    new_blocks = blocks[before_count:] if before_count < len(blocks) else blocks
    assistant_block = new_blocks[-1] if new_blocks else (blocks[-1] if blocks else {"index": None, "text": ""})
    assistant_response = str(assistant_block.get("text", "") or "")
    body = await _get_body_text(cdp)
    captions = await _get_reference_captions(cdp, assistant_block.get("index"))
    return {
        "prompt": prompt,
        "submit_method": submitted_with,
        "duration_s": round(duration, 2),
        "message_count_before": before_count,
        "message_count_after": len(blocks),
        "assistant_response": assistant_response,
        "response_excerpt": assistant_response[:900],
        "reference_captions": captions,
        "reference_files": [path for path in (_map_caption_to_file(caption) for caption in captions) if path],
        "stats_after": await _get_visible_stats(cdp),
        "body_excerpt": body[:2500],
    }


async def _test_scroll_buttons(cdp: CDPClient) -> dict[str, Any]:
    result = await cdp.evaluate(
        """
        (() => {
            const pdoc = window.parent.document;
            const topBtn = pdoc.getElementById('eic-scroll-top');
            const bottomBtn = pdoc.getElementById('eic-scroll-bottom');

            const candidates = [
                pdoc.querySelector('section.main'),
                pdoc.querySelector('.main'),
                pdoc.querySelector('[data-testid="stAppViewContainer"]'),
                pdoc.scrollingElement,
                pdoc.documentElement,
                pdoc.body,
                window,
            ].filter(Boolean);

            const getScrollTop = (target) => {
                if (!target || target === window) {
                    return pdoc.defaultView.pageYOffset || pdoc.documentElement.scrollTop || pdoc.body.scrollTop || 0;
                }
                if (target === pdoc.documentElement || target === pdoc.body || target === pdoc.scrollingElement) {
                    return pdoc.defaultView.pageYOffset || target.scrollTop || 0;
                }
                return target.scrollTop || 0;
            };

            const getScrollHeight = (target) => {
                if (!target || target === window || target === pdoc.documentElement || target === pdoc.body || target === pdoc.scrollingElement) {
                    return Math.max(
                        pdoc.documentElement.scrollHeight || 0,
                        pdoc.body ? pdoc.body.scrollHeight || 0 : 0
                    );
                }
                return target.scrollHeight || 0;
            };

            const getClientHeight = (target) => {
                if (!target || target === window || target === pdoc.documentElement || target === pdoc.body || target === pdoc.scrollingElement) {
                    return pdoc.documentElement.clientHeight || pdoc.defaultView.innerHeight || 0;
                }
                return target.clientHeight || 0;
            };

            const isScrollable = (target) => (getScrollHeight(target) - getClientHeight(target)) > 40;
            const getLabel = (target) => {
                if (target === window) return 'window';
                if (target === pdoc.documentElement) return 'documentElement';
                if (target === pdoc.body) return 'body';
                if (target && target.id) return `#${target.id}`;
                if (target && target.className && typeof target.className === 'string') return target.className;
                return target && target.tagName ? target.tagName.toLowerCase() : 'unknown';
            };

            let container = candidates.find(isScrollable) || candidates[0] || pdoc.documentElement;
            let spacer = null;
            if (!isScrollable(container)) {
                spacer = pdoc.createElement('div');
                spacer.id = 'eic-scroll-spacer';
                spacer.style.height = '2400px';
                spacer.style.pointerEvents = 'none';
                spacer.style.opacity = '0';
                spacer.setAttribute('aria-hidden', 'true');
                const host = container && container.appendChild ? container : (pdoc.body || pdoc.documentElement);
                host.appendChild(spacer);
                container = candidates.find(isScrollable) || host;
            }

            const before = getScrollTop(container);
            if (bottomBtn) bottomBtn.click();
            return new Promise((resolve) => {
                setTimeout(() => {
                    const afterBottom = getScrollTop(container);
                    if (topBtn) topBtn.click();
                    setTimeout(() => {
                        const afterTop = getScrollTop(container);
                        if (spacer && spacer.parentNode) spacer.parentNode.removeChild(spacer);
                        resolve({
                            has_top_button: !!topBtn,
                            has_bottom_button: !!bottomBtn,
                            scroll_target: getLabel(container),
                            forced_overflow: !!spacer,
                            scroll_before: before,
                            scroll_after_bottom: afterBottom,
                            scroll_after_top: afterTop
                        });
                    }, 900);
                }, 900);
            });
        })()
        """,
        await_promise=True,
    )
    return result


async def _test_button_effect(cdp: CDPClient, label: str) -> dict[str, Any]:
    before_body = _normalize_text(await _get_body_text(cdp))
    before_messages = await _get_chat_messages(cdp)
    before_stats = await _get_visible_stats(cdp)
    clicked = await _click_button(cdp, label)
    await asyncio.sleep(2.0)
    after_body = _normalize_text(await _get_body_text(cdp))
    after_messages = await _get_chat_messages(cdp)
    after_stats = await _get_visible_stats(cdp)

    return {
        "clicked": clicked,
        "message_count_before": len(before_messages),
        "message_count_after": len(after_messages),
        "stats_before": before_stats,
        "stats_after": after_stats,
        "observable_change": (
            len(before_messages) != len(after_messages)
            or before_stats != after_stats
            or before_body != after_body
        ),
    }


async def _fill_login_input(cdp: CDPClient, *, kind: str, value: str) -> bool:
    return bool(
        await cdp.evaluate(
            f"""
            (() => {{
                const normalize = (raw) => (raw || '')
                    .normalize('NFD')
                    .replace(/[\\u0300-\\u036f]/g, '')
                    .replace(/\\s+/g, ' ')
                    .trim()
                    .toLowerCase();
                const desiredKind = {json.dumps(kind)};
                const desiredValue = {json.dumps(value)};
                const input = [...document.querySelectorAll('input')].find((node) => {{
                    const type = (node.getAttribute('type') || '').toLowerCase();
                    const autocomplete = (node.getAttribute('autocomplete') || '').toLowerCase();
                    const aria = normalize(node.getAttribute('aria-label'));
                    const placeholder = normalize(node.getAttribute('placeholder'));
                    if (desiredKind === 'password') {{
                        return type === 'password';
                    }}
                    return (
                        type === 'email'
                        || autocomplete === 'username'
                        || aria.includes('correo')
                        || placeholder.includes('correo')
                        || aria.includes('email')
                        || placeholder.includes('email')
                    );
                }});
                if (!input) return false;
                input.focus();
                input.click();
                const previousValue = input.value;
                const setter = Object.getOwnPropertyDescriptor(window.HTMLInputElement.prototype, 'value').set;
                setter.call(input, desiredValue);
                input.setAttribute('value', desiredValue);
                if (input._valueTracker) {{
                    input._valueTracker.setValue(previousValue);
                }}
                input.dispatchEvent(new Event('input', {{ bubbles: true }}));
                input.dispatchEvent(new Event('change', {{ bubbles: true }}));
                input.dispatchEvent(new Event('blur', {{ bubbles: true }}));
                return input.value === desiredValue;
            }})()
            """
        )
    )


async def _login(cdp: CDPClient) -> None:
    await _wait_for_body_contains(cdp, "Iniciar Sesion", timeout=90.0)
    deadline = time.time() + 30.0
    filled = False
    while time.time() < deadline:
        email_filled = await cdp.evaluate(
            _set_input_js(
                'input[aria-label=\"DirecciÃ³n de correo electrÃ³nico\"]',
                SMOKE_LOGIN_EMAIL,
            )
        )
        password_filled = await cdp.evaluate(
            _set_input_js('input[type=\"password\"]', SMOKE_LOGIN_PASSWORD)
        )
        if email_filled and password_filled:
            filled = True
            break
        await asyncio.sleep(0.5)

    if not filled:
        raise TimeoutError("No fue posible completar el formulario de login del diagnóstico profundo.")

    clicked = await _click_button(cdp, "Continuar")
    if not clicked:
        raise RuntimeError("No se pudo pulsar el boton Continuar en login.")
    await _wait_for_body_contains(cdp, "Quantum Tutor Avanzado", timeout=90.0)


async def _login_resilient(cdp: CDPClient) -> None:
    await _wait_for_body_contains(cdp, "Iniciar Sesion", timeout=90.0)
    deadline = time.time() + 30.0
    filled = False
    while time.time() < deadline:
        email_filled = await _fill_login_input(cdp, kind="email", value=SMOKE_LOGIN_EMAIL)
        password_filled = await _fill_login_input(cdp, kind="password", value=SMOKE_LOGIN_PASSWORD)
        if email_filled and password_filled:
            filled = True
            break
        await asyncio.sleep(0.5)

    if not filled:
        raise TimeoutError("No fue posible completar el formulario de login del diagnóstico profundo.")

    clicked = await _click_button(cdp, "Continuar")
    if not clicked:
        raise RuntimeError("No se pudo pulsar el boton Continuar en login.")
    await _wait_for_body_contains(cdp, "Quantum Tutor Avanzado", timeout=90.0)


def _score_congruence(response_text: str, expected_terms: list[str], optional_terms: list[str]) -> dict[str, Any]:
    normalized_response = _normalize_text(response_text).replace("∫", " integral ")
    found_expected = [term for term in expected_terms if _normalize_text(term) in normalized_response]
    found_optional = [term for term in optional_terms if _normalize_text(term) in normalized_response]
    minimum_expected_hits = 1 if len(expected_terms) <= 1 else max(2, len(expected_terms) - 1)
    return {
        "found_expected": found_expected,
        "missing_expected": [term for term in expected_terms if term not in found_expected],
        "found_optional": found_optional,
        "is_congruent": len(found_expected) >= minimum_expected_hits,
    }


async def _run_browser_flow() -> dict[str, Any]:
    browser_path = _find_browser()
    temp_profile = Path(tempfile.mkdtemp(prefix="qt_live_diag_"))
    browser = _start_browser(browser_path, temp_profile)
    try:
        _wait_for_http(f"http://127.0.0.1:{CDP_PORT}/json/version", timeout=30.0)
        page_target = _wait_for_page_target(APP_URL, timeout=30.0)
        ws_url = page_target["webSocketDebuggerUrl"]

        async with CDPClient(ws_url) as cdp:
            await cdp.call("Page.enable")
            await cdp.call("Runtime.enable")
            await cdp.call("DOM.enable")

            await _login_resilient(cdp)
            await _capture_screenshot(cdp, OUTPUT_DIR / "01_logged_in.png")

            report: dict[str, Any] = {
                "browser": str(browser_path),
                "login_user": SMOKE_LOGIN_EMAIL,
                "target_url": page_target.get("url"),
                "initial_panel": await _get_user_panel_snapshot(cdp),
            }

            report["concept_query"] = await _send_chat_prompt(
                cdp,
                "Explica por que en el pozo infinito la probabilidad en el centro es cero para n=2, sin saltarte la intuicion fisica.",
                "02_concept_query.png",
            )
            report["concept_query"]["congruence"] = _score_congruence(
                report["concept_query"]["assistant_response"],
                expected_terms=["pozo infinito", "probabilidad", "centro", "n=2"],
                optional_terms=["nodo", "funcion de onda", "densidad de probabilidad", "simetria"],
            )

            report["math_query"] = await _send_chat_prompt(
                cdp,
                "Calcula la integral de e^-x desde 0 hasta infinito y explica el significado del resultado.",
                "03_math_query.png",
            )
            report["math_query"]["congruence"] = _score_congruence(
                report["math_query"]["assistant_response"],
                expected_terms=["integral", "infinito"],
                optional_terms=["resultado", "converge", "1", "area"],
            )

            report["visual_query"] = await _send_chat_prompt(
                cdp,
                "Podrias mostrar las imagenes del libro que hablan del pozo infinito?",
                "04_visual_query.png",
            )
            report["visual_query"]["congruence"] = _score_congruence(
                report["visual_query"]["assistant_response"],
                expected_terms=["pozo infinito"],
                optional_terms=["referencias", "bibliograficas", "imagen", "libro"],
            )

            await _click_tab(cdp, "Dashboard Analitico Cognitivo")
            await _wait_for_body_contains(cdp, "Perfil de Comprension Cuantica", timeout=30.0)
            await _capture_screenshot(cdp, OUTPUT_DIR / "05_analytics_tab.png")
            analytics_body = await _get_body_text(cdp)
            report["analytics_tab"] = {
                "loaded": "Perfil de Comprensión Cuántica" in analytics_body,
                "has_heatmap": "Mapa de Esfuerzo por Concepto" in analytics_body,
                "has_anomalies": "Anomalías Detectadas" in analytics_body,
                "has_mastered": "Terrenos Dominados" in analytics_body,
            }

            await _click_tab(cdp, "Interfaz de Sesion Cuantica")
            await _wait_for_body_contains(cdp, "Quantum Tutor Avanzado", timeout=30.0)
            report["scroll_buttons"] = await _test_scroll_buttons(cdp)

            sidebar_buttons = [
                "Nuevo chat",
                "Buscar chats",
                "Imagenes",
                "Aplicaciones",
                "Investigacion avanzada",
                "Codex",
                "Iniciar un chat de grupo",
            ]
            report["sidebar_buttons"] = {}
            for label in sidebar_buttons:
                report["sidebar_buttons"][label] = await _test_button_effect(cdp, label)
                if label == "Nuevo chat":
                    report["sidebar_buttons"][label]["messages_cleared"] = (
                        report["sidebar_buttons"][label]["message_count_after"] == 0
                    )
                    report["sidebar_buttons"][label]["stats_preserved"] = (
                        report["sidebar_buttons"][label]["stats_before"] == report["sidebar_buttons"][label]["stats_after"]
                    )

            report["new_session"] = await _test_button_effect(cdp, "Nueva Sesion")
            report["new_session"]["messages_cleared"] = (
                report["new_session"]["message_count_after"] == 0
            )
            report["new_session"]["stats_reset"] = (
                report["new_session"]["stats_after"].get("wolfram_calls") == 0
                and report["new_session"]["stats_after"].get("rag_anchors") == 0
            )
            await _capture_screenshot(cdp, OUTPUT_DIR / "06_after_new_session.png")

            report["logout"] = await _test_button_effect(cdp, "Cerrar Sesion")
            await _wait_for_body_contains(cdp, "Iniciar Sesion", timeout=30.0)
            report["logout"]["returned_to_login"] = True
            await _capture_screenshot(cdp, OUTPUT_DIR / "07_logout.png")

            return report
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
        result["app_url"] = APP_URL
        result["streamlit_port"] = STREAMLIT_PORT
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
    output_path = OUTPUT_DIR / "deep_diagnostics_result.json"
    output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
