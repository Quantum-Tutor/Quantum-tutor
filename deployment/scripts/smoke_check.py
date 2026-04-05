from __future__ import annotations

import argparse
import json
import urllib.error
import urllib.request


def _request(method: str, url: str, data: bytes | None = None, headers: dict[str, str] | None = None):
    request = urllib.request.Request(url, data=data, method=method)
    for key, value in (headers or {}).items():
        request.add_header(key, value)
    try:
        with urllib.request.urlopen(request, timeout=10) as response:
            payload = response.read().decode("utf-8")
            headers_dict = {k.lower(): v for k, v in response.headers.items()}
            return response.status, headers_dict, payload
    except urllib.error.HTTPError as exc:
        payload = exc.read().decode("utf-8")
        headers_dict = {k.lower(): v for k, v in exc.headers.items()}
        return exc.code, headers_dict, payload


def main() -> int:
    parser = argparse.ArgumentParser(description="Smoke check for deployed Quantum Tutor hosts.")
    parser.add_argument("--ui-url", required=True, help="Public UI URL, for example https://quantumtutor.cl")
    parser.add_argument("--api-url", required=True, help="Public API URL, for example https://api.quantumtutor.cl")
    args = parser.parse_args()

    ui_url = args.ui_url.rstrip("/")
    api_url = args.api_url.rstrip("/")

    ui_status, _, _ = _request("GET", f"{ui_url}/")
    if ui_status != 200:
        print(f"ui probe failed: status={ui_status}")
        return 1

    health_status, health_headers, health_body = _request(
        "GET",
        f"{api_url}/health",
        headers={"X-Request-ID": "smoke-health-1"},
    )
    if health_status != 200:
        print(f"health failed: status={health_status}")
        print(health_body)
        return 1

    health_json = json.loads(health_body)
    if health_json.get("status") != "ok":
        print("health returned unexpected payload")
        print(health_body)
        return 1
    if health_headers.get("x-request-id", "") != "smoke-health-1":
        print("health did not preserve X-Request-ID")
        return 1

    probe_payload = json.dumps({"message": "", "history": []}).encode("utf-8")
    chat_status, chat_headers, chat_body = _request(
        "POST",
        f"{api_url}/api/chat",
        data=probe_payload,
        headers={
            "Content-Type": "application/json",
            "X-Request-ID": "smoke-chat-1",
        },
    )
    if chat_status != 400:
        print(f"chat probe failed: status={chat_status}")
        print(chat_body)
        return 1

    chat_json = json.loads(chat_body)
    if chat_json.get("error_code") != "EMPTY_QUERY":
        print("chat probe returned unexpected payload")
        print(chat_body)
        return 1
    if chat_headers.get("x-request-id", "") != "smoke-chat-1":
        print("chat probe did not preserve X-Request-ID")
        return 1

    print("Smoke check OK")
    print(json.dumps({
        "ui_url": ui_url,
        "api_url": api_url,
        "health": health_json,
        "chat_probe": chat_json,
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
