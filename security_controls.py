from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from quantum_tutor_paths import (
    API_ABUSE_STATE_PATH,
    PROVIDER_CIRCUIT_BREAKERS_PATH,
    ensure_output_dirs,
    write_json_atomic,
)


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except (TypeError, ValueError):
        return default


@dataclass
class AbuseDecision:
    blocked: bool
    retry_after_seconds: float
    score: float
    threshold: float
    identifier: str
    reason: str
    block_seconds: float
    block_count: int

    def as_metadata(self) -> dict[str, Any]:
        return {
            "blocked": self.blocked,
            "retry_after_seconds": round(max(self.retry_after_seconds, 0.0), 3),
            "score": round(max(self.score, 0.0), 3),
            "threshold": self.threshold,
            "identifier": self.identifier,
            "reason": self.reason,
            "block_seconds": round(max(self.block_seconds, 0.0), 3),
            "block_count": max(int(self.block_count), 0),
        }


class FileAbusePrevention:
    def __init__(
        self,
        state_path: Path = API_ABUSE_STATE_PATH,
        threshold: float | None = None,
        decay_seconds: float | None = None,
        block_seconds: float | None = None,
        max_block_seconds: float | None = None,
    ):
        ensure_output_dirs()
        self.state_path = Path(state_path)
        self.threshold = threshold if threshold is not None else _float_env("QT_ABUSE_BLOCK_THRESHOLD", 60.0)
        self.decay_seconds = decay_seconds if decay_seconds is not None else _float_env("QT_ABUSE_DECAY_SECONDS", 1800.0)
        self.block_seconds = block_seconds if block_seconds is not None else _float_env("QT_ABUSE_BLOCK_SECONDS", 900.0)
        self.max_block_seconds = max_block_seconds if max_block_seconds is not None else _float_env("QT_ABUSE_MAX_BLOCK_SECONDS", 86400.0)
        self._lock = threading.Lock()

    def _load_state(self) -> dict[str, Any]:
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            payload = {}
        payload.setdefault("identities", {})
        return payload

    def _save_state(self, payload: dict[str, Any]) -> None:
        write_json_atomic(self.state_path, payload, indent=2, ensure_ascii=False)

    def _decay_score(self, score: float, elapsed_seconds: float) -> float:
        if score <= 0 or self.decay_seconds <= 0:
            return max(score, 0.0)
        decay_per_second = self.threshold / self.decay_seconds
        return max(score - (elapsed_seconds * decay_per_second), 0.0)

    def _normalize_entry(self, entry: dict[str, Any], now: float) -> dict[str, Any]:
        score = float(entry.get("score", 0.0))
        updated_at = float(entry.get("updated_at", now))
        block_until = float(entry.get("block_until", 0.0))
        elapsed = max(now - updated_at, 0.0)
        decayed_score = self._decay_score(score, elapsed)
        return {
            "score": decayed_score,
            "updated_at": now,
            "block_until": block_until,
            "last_reason": entry.get("last_reason", ""),
            "block_count": int(entry.get("block_count", 0)),
        }

    def inspect(self, identifier: str) -> AbuseDecision:
        now = time.time()
        with self._lock:
            state = self._load_state()
            entry = self._normalize_entry(state["identities"].get(identifier, {}), now)
            state["identities"][identifier] = entry
            self._save_state(state)

        retry_after = max(entry["block_until"] - now, 0.0)
        return AbuseDecision(
            blocked=retry_after > 0,
            retry_after_seconds=retry_after,
            score=entry["score"],
            threshold=self.threshold,
            identifier=identifier,
            reason=entry.get("last_reason", ""),
            block_seconds=retry_after,
            block_count=entry["block_count"],
        )

    def record_event(self, identifier: str, points: float, reason: str) -> AbuseDecision:
        now = time.time()
        with self._lock:
            state = self._load_state()
            entry = self._normalize_entry(state["identities"].get(identifier, {}), now)
            entry["score"] = min(entry["score"] + max(points, 0.0), self.threshold * 4.0)
            entry["last_reason"] = reason
            if entry["score"] >= self.threshold:
                entry["block_count"] = int(entry.get("block_count", 0)) + 1
                block_for = min(self.block_seconds * entry["block_count"], self.max_block_seconds)
                entry["block_until"] = max(float(entry.get("block_until", 0.0)), now + block_for)
            state["identities"][identifier] = entry
            self._save_state(state)

        retry_after = max(entry["block_until"] - now, 0.0)
        return AbuseDecision(
            blocked=retry_after > 0,
            retry_after_seconds=retry_after,
            score=entry["score"],
            threshold=self.threshold,
            identifier=identifier,
            reason=reason,
            block_seconds=retry_after,
            block_count=entry["block_count"],
        )

    def list_entries(self, limit: int = 200) -> list[dict[str, Any]]:
        now = time.time()
        with self._lock:
            state = self._load_state()
            normalized = {}
            for identifier, raw_entry in state["identities"].items():
                normalized[identifier] = self._normalize_entry(raw_entry, now)
            state["identities"] = normalized
            self._save_state(state)

        rows = []
        for identifier, entry in normalized.items():
            retry_after = max(float(entry.get("block_until", 0.0)) - now, 0.0)
            rows.append({
                "identifier": identifier,
                "score": round(float(entry.get("score", 0.0)), 3),
                "blocked": retry_after > 0,
                "retry_after_seconds": round(retry_after, 3),
                "block_count": int(entry.get("block_count", 0)),
                "last_reason": entry.get("last_reason", ""),
                "updated_at": float(entry.get("updated_at", 0.0)),
            })
        rows.sort(key=lambda item: (item["blocked"], item["score"], item["updated_at"]), reverse=True)
        return rows[:limit]

    def clear_identifier(self, identifier: str) -> bool:
        with self._lock:
            state = self._load_state()
            existed = identifier in state["identities"]
            if existed:
                state["identities"].pop(identifier, None)
                self._save_state(state)
            return existed


@dataclass
class CircuitBreakerDecision:
    provider: str
    state: str
    allowed: bool
    blocked: bool
    active: bool
    retry_after_seconds: float
    failure_count: int
    failure_threshold: int
    opened_until: float
    last_failure_category: str

    def as_metadata(self) -> dict[str, Any]:
        return {
            "provider": self.provider,
            "state": self.state,
            "allowed": self.allowed,
            "blocked": self.blocked,
            "active": self.active,
            "retry_after_seconds": round(max(self.retry_after_seconds, 0.0), 3),
            "failure_count": max(int(self.failure_count), 0),
            "failure_threshold": max(int(self.failure_threshold), 1),
            "opened_until": self.opened_until,
            "last_failure_category": self.last_failure_category,
        }


class FileCircuitBreaker:
    def __init__(
        self,
        state_path: Path = PROVIDER_CIRCUIT_BREAKERS_PATH,
        failure_threshold: int | None = None,
        window_seconds: float | None = None,
        open_seconds: float | None = None,
        half_open_retry_seconds: float | None = None,
    ):
        ensure_output_dirs()
        self.state_path = Path(state_path)
        self.failure_threshold = failure_threshold if failure_threshold is not None else _int_env("QT_PROVIDER_BREAKER_FAILURE_THRESHOLD", 4)
        self.window_seconds = window_seconds if window_seconds is not None else _float_env("QT_PROVIDER_BREAKER_WINDOW_SECONDS", 45.0)
        self.open_seconds = open_seconds if open_seconds is not None else _float_env("QT_PROVIDER_BREAKER_OPEN_SECONDS", 30.0)
        self.half_open_retry_seconds = half_open_retry_seconds if half_open_retry_seconds is not None else _float_env("QT_PROVIDER_BREAKER_HALF_OPEN_RETRY_SECONDS", 3.0)
        self._lock = threading.Lock()

    def _load_state(self) -> dict[str, Any]:
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            payload = {}
        payload.setdefault("providers", {})
        return payload

    def _save_state(self, payload: dict[str, Any]) -> None:
        write_json_atomic(self.state_path, payload, indent=2, ensure_ascii=False)

    def _normalize_entry(self, entry: dict[str, Any], now: float) -> dict[str, Any]:
        failures = [
            float(ts)
            for ts in entry.get("failure_timestamps", [])
            if now - float(ts) <= self.window_seconds
        ]
        state = entry.get("state", "closed")
        opened_until = float(entry.get("opened_until", 0.0))
        next_probe_at = float(entry.get("next_probe_at", 0.0))
        if state == "open" and opened_until <= now:
            state = "half_open"
            next_probe_at = now
        return {
            "state": state,
            "failure_timestamps": failures,
            "opened_until": opened_until,
            "next_probe_at": next_probe_at,
            "last_failure_category": entry.get("last_failure_category", ""),
            "last_failure_at": float(entry.get("last_failure_at", 0.0)),
            "last_success_at": float(entry.get("last_success_at", 0.0)),
        }

    def status(self, provider: str) -> CircuitBreakerDecision:
        now = time.time()
        with self._lock:
            state = self._load_state()
            entry = self._normalize_entry(state["providers"].get(provider, {}), now)
            state["providers"][provider] = entry
            self._save_state(state)

        if entry["state"] == "open" and entry["opened_until"] > now:
            retry_after = entry["opened_until"] - now
            return CircuitBreakerDecision(
                provider=provider,
                state="open",
                allowed=False,
                blocked=True,
                active=True,
                retry_after_seconds=retry_after,
                failure_count=len(entry["failure_timestamps"]),
                failure_threshold=self.failure_threshold,
                opened_until=entry["opened_until"],
                last_failure_category=entry["last_failure_category"],
            )
        if entry["state"] == "half_open" and entry["next_probe_at"] > now:
            retry_after = entry["next_probe_at"] - now
            return CircuitBreakerDecision(
                provider=provider,
                state="half_open",
                allowed=False,
                blocked=True,
                active=True,
                retry_after_seconds=retry_after,
                failure_count=len(entry["failure_timestamps"]),
                failure_threshold=self.failure_threshold,
                opened_until=entry["opened_until"],
                last_failure_category=entry["last_failure_category"],
            )
        return CircuitBreakerDecision(
            provider=provider,
            state=entry["state"],
            allowed=True,
            blocked=False,
            active=entry["state"] != "closed",
            retry_after_seconds=0.0,
            failure_count=len(entry["failure_timestamps"]),
            failure_threshold=self.failure_threshold,
            opened_until=entry["opened_until"],
            last_failure_category=entry["last_failure_category"],
        )

    def allow_request(self, provider: str) -> CircuitBreakerDecision:
        now = time.time()
        with self._lock:
            state = self._load_state()
            entry = self._normalize_entry(state["providers"].get(provider, {}), now)
            decision = None
            if entry["state"] == "open" and entry["opened_until"] > now:
                decision = CircuitBreakerDecision(
                    provider=provider,
                    state="open",
                    allowed=False,
                    blocked=True,
                    active=True,
                    retry_after_seconds=entry["opened_until"] - now,
                    failure_count=len(entry["failure_timestamps"]),
                    failure_threshold=self.failure_threshold,
                    opened_until=entry["opened_until"],
                    last_failure_category=entry["last_failure_category"],
                )
            elif entry["state"] == "half_open":
                if entry["next_probe_at"] > now:
                    decision = CircuitBreakerDecision(
                        provider=provider,
                        state="half_open",
                        allowed=False,
                        blocked=True,
                        active=True,
                        retry_after_seconds=entry["next_probe_at"] - now,
                        failure_count=len(entry["failure_timestamps"]),
                        failure_threshold=self.failure_threshold,
                        opened_until=entry["opened_until"],
                        last_failure_category=entry["last_failure_category"],
                    )
                else:
                    entry["next_probe_at"] = now + self.half_open_retry_seconds
            state["providers"][provider] = entry
            self._save_state(state)

        if decision is not None:
            return decision
        return CircuitBreakerDecision(
            provider=provider,
            state=entry["state"],
            allowed=True,
            blocked=False,
            active=entry["state"] != "closed",
            retry_after_seconds=0.0,
            failure_count=len(entry["failure_timestamps"]),
            failure_threshold=self.failure_threshold,
            opened_until=entry["opened_until"],
            last_failure_category=entry["last_failure_category"],
        )

    def record_failure(self, provider: str, category: str) -> CircuitBreakerDecision:
        now = time.time()
        with self._lock:
            state = self._load_state()
            entry = self._normalize_entry(state["providers"].get(provider, {}), now)
            entry["last_failure_category"] = category
            entry["last_failure_at"] = now
            if entry["state"] == "half_open":
                entry["state"] = "open"
                entry["failure_timestamps"] = [now]
                entry["opened_until"] = now + self.open_seconds
                entry["next_probe_at"] = 0.0
            else:
                entry["failure_timestamps"].append(now)
                if len(entry["failure_timestamps"]) >= self.failure_threshold:
                    entry["state"] = "open"
                    entry["opened_until"] = now + self.open_seconds
                    entry["next_probe_at"] = 0.0
            state["providers"][provider] = entry
            self._save_state(state)
        return self.status(provider)

    def record_success(self, provider: str) -> CircuitBreakerDecision:
        now = time.time()
        with self._lock:
            state = self._load_state()
            entry = self._normalize_entry(state["providers"].get(provider, {}), now)
            entry["state"] = "closed"
            entry["failure_timestamps"] = []
            entry["opened_until"] = 0.0
            entry["next_probe_at"] = 0.0
            entry["last_success_at"] = now
            state["providers"][provider] = entry
            self._save_state(state)
        return self.status(provider)

    def list_entries(self) -> list[dict[str, Any]]:
        now = time.time()
        with self._lock:
            state = self._load_state()
            normalized = {}
            for provider, raw_entry in state["providers"].items():
                normalized[provider] = self._normalize_entry(raw_entry, now)
            state["providers"] = normalized
            self._save_state(state)

        rows = []
        for provider in normalized:
            rows.append(self.status(provider).as_metadata())
        rows.sort(key=lambda item: (item["blocked"], item["active"], item["failure_count"]), reverse=True)
        return rows

    def reset(self, provider: str) -> CircuitBreakerDecision:
        return self.record_success(provider)
