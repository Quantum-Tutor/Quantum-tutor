import json
import os
import time
import threading
from typing import Dict

class AdaptiveCalibrator:
    def __init__(self, path: str = "scheduler_thresholds.json",
                 default_threshold: float = 0.2,
                 reload_interval: int = 60,
                 clamp=(0.1, 0.7)):
        base_dir = os.path.dirname(os.path.abspath(__file__))
        self.path = os.path.join(base_dir, path) if not os.path.isabs(path) else path
        
        self.default_threshold = default_threshold
        self.threshold = default_threshold

        self.reload_interval = reload_interval
        self.clamp_min, self.clamp_max = clamp

        self._last_mtime = 0.0
        self._last_checked = 0.0
        self._lock = threading.Lock()

        self._safe_load(initial=True)

    # ── Public API ───────────────────────
    def should_use_wolfram(self, scores: Dict[str, float]) -> bool:
        if not scores: # Fallback conservador
            return False
            
        self._maybe_reload()

        w = scores.get("wolfram", 0.0)
        r = scores.get("rag", 0.0)
        delta = w - r

        return delta > self.threshold

    # ── Internal ─────────────────────────
    def _maybe_reload(self):
        now = time.time()
        if now - self._last_checked < self.reload_interval:
            return

        self._last_checked = now

        try:
            mtime = os.path.getmtime(self.path)
        except OSError:
            return

        if mtime <= self._last_mtime:
            return

        self._safe_load()

    def _safe_load(self, initial=False):
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    data = json.load(f)

                new_theta = float(data.get("threshold", self.default_threshold))

                # Clamp de seguridad
                new_theta = max(self.clamp_min, min(new_theta, self.clamp_max))

                self.threshold = new_theta
                self._last_mtime = os.path.getmtime(self.path)

            except Exception:
                # fallback silencioso en runtime
                if initial:
                    self.threshold = self.default_threshold
