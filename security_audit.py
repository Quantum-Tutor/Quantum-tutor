from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any

from quantum_tutor_paths import SECURITY_EVENTS_LOG_PATH, ensure_output_dirs


class SecurityEventLogger:
    def __init__(self, log_path: Path = SECURITY_EVENTS_LOG_PATH):
        ensure_output_dirs()
        self.log_path = Path(log_path)
        self._lock = threading.Lock()

    def log_event(
        self,
        *,
        event_type: str,
        action: str,
        severity: str = "INFO",
        actor: str = "system",
        fields: dict[str, Any] | None = None,
    ) -> None:
        payload = {
            "timestamp": round(time.time(), 3),
            "event_type": event_type,
            "action": action,
            "severity": severity,
            "actor": actor,
            "fields": fields or {},
        }
        line = json.dumps(payload, ensure_ascii=False)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self._lock:
            with self.log_path.open("a", encoding="utf-8") as handle:
                handle.write(line + "\n")

    def read_recent_events(self, limit: int = 200) -> list[dict[str, Any]]:
        try:
            with self.log_path.open("r", encoding="utf-8") as handle:
                lines = handle.readlines()
        except FileNotFoundError:
            return []
        events = []
        for raw in reversed(lines[-limit:]):
            raw = raw.strip()
            if not raw:
                continue
            try:
                events.append(json.loads(raw))
            except json.JSONDecodeError:
                continue
        return events
