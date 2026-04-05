from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

import numpy as np
from scipy.spatial.distance import cosine
from sentence_transformers import SentenceTransformer

from quantum_tutor_paths import (
    API_USAGE_BUCKETS_PATH,
    LLM_RESPONSE_CACHE_PATH,
    ensure_output_dirs,
    write_json_atomic,
)


logger = logging.getLogger("QuantumTutor.RequestOptimization")


def _float_env(name: str, default: float) -> float:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except (TypeError, ValueError):
        return default


def _int_env(name: str, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return default


def normalize_query(text: str) -> str:
    cleaned = (text or "").strip().lower()
    return re.sub(r"\s+", " ", cleaned)


def _stable_hash(*parts: str) -> str:
    payload = "::".join(parts)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


@dataclass
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: float
    remaining_tokens: float
    capacity: float
    refill_tokens: float
    refill_seconds: float
    consumed_tokens: float
    bucket_id: str

    def as_metadata(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "limited": not self.allowed,
            "retry_after_seconds": round(max(self.retry_after_seconds, 0.0), 3),
            "remaining_tokens": round(max(self.remaining_tokens, 0.0), 3),
            "capacity": self.capacity,
            "refill_tokens": self.refill_tokens,
            "refill_seconds": self.refill_seconds,
            "consumed_tokens": self.consumed_tokens,
            "bucket_id": self.bucket_id,
        }


@dataclass
class BackpressureDecision:
    limited: bool
    retry_after_seconds: float
    queue_timeout_seconds: float
    queue_depth: int
    concurrency_limit: int
    operation: str
    wait_time_seconds: float = 0.0

    def as_metadata(self) -> dict[str, Any]:
        return {
            "limited": self.limited,
            "retry_after_seconds": round(max(self.retry_after_seconds, 0.0), 3),
            "queue_timeout_seconds": round(max(self.queue_timeout_seconds, 0.0), 3),
            "queue_depth": max(int(self.queue_depth), 0),
            "concurrency_limit": max(int(self.concurrency_limit), 1),
            "operation": self.operation,
            "wait_time_seconds": round(max(self.wait_time_seconds, 0.0), 3),
        }


class RequestRateLimitedError(RuntimeError):
    def __init__(self, decision: RateLimitDecision, message: Optional[str] = None):
        self.decision = decision
        self.retry_after_seconds = decision.retry_after_seconds
        super().__init__(message or "Provider request rate limit exceeded.")


class RequestBackpressureError(RuntimeError):
    def __init__(self, decision: BackpressureDecision, message: Optional[str] = None):
        self.decision = decision
        self.retry_after_seconds = decision.retry_after_seconds
        super().__init__(message or "Provider queue is saturated.")


class FileTokenBucketRateLimiter:
    """
    File-backed token bucket for single-host runtimes.
    In multi-host production, the same contract can be moved to Redis.
    """

    def __init__(
        self,
        state_path: Path = API_USAGE_BUCKETS_PATH,
        capacity: Optional[float] = None,
        refill_tokens: Optional[float] = None,
        refill_seconds: Optional[float] = None,
    ):
        ensure_output_dirs()
        self.state_path = Path(state_path)
        self.capacity = capacity if capacity is not None else _float_env("QT_RATE_LIMIT_CAPACITY", 20.0)
        self.refill_tokens = refill_tokens if refill_tokens is not None else _float_env("QT_RATE_LIMIT_REFILL_TOKENS", 1.0)
        self.refill_seconds = refill_seconds if refill_seconds is not None else _float_env("QT_RATE_LIMIT_REFILL_SECONDS", 3.0)
        self._lock = threading.Lock()

    @property
    def refill_tokens_per_second(self) -> float:
        if self.refill_seconds <= 0:
            return 0.0
        return self.refill_tokens / self.refill_seconds

    def _load_state(self) -> dict[str, Any]:
        try:
            with self.state_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except (json.JSONDecodeError, OSError):
            data = {}
        data.setdefault("users", {})
        return data

    def _save_state(self, data: dict[str, Any]) -> None:
        write_json_atomic(self.state_path, data, indent=2)

    def _bucket_id(self, user_id: str) -> str:
        normalized = normalize_query(user_id) or "anonymous"
        return _stable_hash("bucket", normalized)[:24]

    def _refill(self, bucket: dict[str, Any], now: float) -> float:
        tokens = float(bucket.get("tokens", self.capacity))
        last_refill_at = float(bucket.get("last_refill_at", now))
        elapsed = max(now - last_refill_at, 0.0)
        replenished = elapsed * self.refill_tokens_per_second
        return min(self.capacity, tokens + replenished)

    def _build_decision(
        self,
        *,
        allowed: bool,
        tokens_after: float,
        consumed_tokens: float,
        bucket_id: str,
        retry_after_seconds: float = 0.0,
    ) -> RateLimitDecision:
        return RateLimitDecision(
            allowed=allowed,
            retry_after_seconds=max(retry_after_seconds, 0.0),
            remaining_tokens=max(tokens_after, 0.0),
            capacity=self.capacity,
            refill_tokens=self.refill_tokens,
            refill_seconds=self.refill_seconds,
            consumed_tokens=consumed_tokens,
            bucket_id=bucket_id,
        )

    def consume(self, user_id: str, cost: float = 1.0) -> RateLimitDecision:
        now = time.time()
        bucket_id = self._bucket_id(user_id)

        with self._lock:
            state = self._load_state()
            bucket = state["users"].get(bucket_id, {})
            tokens = self._refill(bucket, now)

            if tokens < cost:
                state["users"][bucket_id] = {
                    "tokens": tokens,
                    "last_refill_at": now,
                }
                self._save_state(state)
                refill_rate = self.refill_tokens_per_second
                retry_after_seconds = ((cost - tokens) / refill_rate) if refill_rate > 0 else self.refill_seconds
                return self._build_decision(
                    allowed=False,
                    tokens_after=tokens,
                    consumed_tokens=0.0,
                    bucket_id=bucket_id,
                    retry_after_seconds=retry_after_seconds,
                )

            tokens -= cost
            state["users"][bucket_id] = {
                "tokens": tokens,
                "last_refill_at": now,
            }
            self._save_state(state)
            return self._build_decision(
                allowed=True,
                tokens_after=tokens,
                consumed_tokens=cost,
                bucket_id=bucket_id,
            )


@dataclass
class ModelRoute:
    tier: str
    model_name: str
    max_output_tokens: int
    temperature: float
    reasoning_enabled: bool
    reasoning_model: str
    reasoning_max_tokens: int
    cacheable: bool
    cache_namespace: str

    def as_metadata(self) -> dict[str, Any]:
        return {
            "tier": self.tier,
            "model_name": self.model_name,
            "max_output_tokens": self.max_output_tokens,
            "temperature": self.temperature,
            "reasoning_enabled": self.reasoning_enabled,
            "reasoning_model": self.reasoning_model,
            "reasoning_max_tokens": self.reasoning_max_tokens,
            "cacheable": self.cacheable,
            "cache_namespace": self.cache_namespace,
        }


class RequestModelRouter:
    def __init__(self, default_model: str):
        self.default_model = default_model
        self.simple_model = os.getenv("QT_MODEL_SIMPLE", default_model)
        self.medium_model = os.getenv("QT_MODEL_MEDIUM", default_model)
        self.complex_model = os.getenv("QT_MODEL_COMPLEX", self.medium_model)

        self.simple_max_tokens = _int_env("QT_MAX_TOKENS_SIMPLE", 256)
        self.medium_max_tokens = _int_env("QT_MAX_TOKENS_MEDIUM", 512)
        self.complex_max_tokens = _int_env("QT_MAX_TOKENS_COMPLEX", 896)
        self.reasoning_max_tokens = _int_env("QT_REASONING_MAX_TOKENS", 160)
        self.default_temperature = _float_env("QT_LLM_TEMPERATURE", 0.2)

    def classify(self, query: str, intent: str = "GENERAL", prior_history_turns: int = 0) -> str:
        normalized = normalize_query(query)
        word_count = len(normalized.split())
        math_symbols = len(re.findall(r"(\\int|\\sum|[=+\-*/^])", query or ""))
        math_keywords = sum(
            1
            for token in (
                "integral",
                "deriva",
                "derivada",
                "demuestra",
                "analiza",
                "compara",
                "conmutador",
                "normaliza",
                "schrodinger",
                "hamiltoniano",
                "operador",
                "eigen",
                "autovalor",
            )
            if token in normalized
        )

        if intent == "VISUAL":
            return "complex"
        if prior_history_turns >= 4:
            return "complex"
        if (
            word_count <= 10
            and math_symbols == 0
            and math_keywords <= 1
            and any(
                normalized.startswith(prefix)
                for prefix in (
                    "que es",
                    "que significa",
                    "define",
                    "explica breve",
                    "resumen de",
                )
            )
        ):
            return "simple"
        if word_count <= 8 and math_symbols == 0 and math_keywords == 0:
            return "simple"
        if len(normalized) >= 320 or math_symbols >= 3 or math_keywords >= 2:
            return "complex"
        return "medium"

    def _is_cacheable_query(self, query: str, intent: str, prior_history_turns: int) -> bool:
        normalized = normalize_query(query)
        personalized_markers = (
            "mi derivacion",
            "mi respuesta",
            "mi progreso",
            "mi sesion",
            "subi una foto",
            "subi una imagen",
            "historial",
            "chat anterior",
            "corrige mi",
        )
        if intent != "GENERAL":
            return False
        if prior_history_turns > 0:
            return False
        if len(normalized) < 12 or len(normalized) > 350:
            return False
        if any(marker in normalized for marker in personalized_markers):
            return False
        return True

    def route(self, query: str, intent: str = "GENERAL", prior_history_turns: int = 0) -> ModelRoute:
        tier = self.classify(query=query, intent=intent, prior_history_turns=prior_history_turns)
        cacheable = self._is_cacheable_query(query=query, intent=intent, prior_history_turns=prior_history_turns)

        if tier == "simple":
            return ModelRoute(
                tier=tier,
                model_name=self.simple_model,
                max_output_tokens=self.simple_max_tokens,
                temperature=0.1,
                reasoning_enabled=False,
                reasoning_model=self.simple_model,
                reasoning_max_tokens=self.reasoning_max_tokens,
                cacheable=cacheable,
                cache_namespace="general-simple-v1",
            )
        if tier == "complex":
            return ModelRoute(
                tier=tier,
                model_name=self.complex_model,
                max_output_tokens=self.complex_max_tokens,
                temperature=self.default_temperature,
                reasoning_enabled=True,
                reasoning_model=self.simple_model,
                reasoning_max_tokens=self.reasoning_max_tokens,
                cacheable=False,
                cache_namespace="general-complex-v1",
            )

        return ModelRoute(
            tier=tier,
            model_name=self.medium_model,
            max_output_tokens=self.medium_max_tokens,
            temperature=self.default_temperature,
            reasoning_enabled=False,
            reasoning_model=self.simple_model,
            reasoning_max_tokens=self.reasoning_max_tokens,
            cacheable=cacheable,
            cache_namespace="general-medium-v1",
        )


class LLMResponseCache:
    def __init__(
        self,
        cache_path: Path = LLM_RESPONSE_CACHE_PATH,
        exact_ttl_seconds: Optional[int] = None,
        semantic_ttl_seconds: Optional[int] = None,
        semantic_threshold: float = 0.84,
        max_entries: Optional[int] = None,
    ):
        ensure_output_dirs()
        self.cache_path = Path(cache_path)
        self.exact_ttl_seconds = exact_ttl_seconds if exact_ttl_seconds is not None else _int_env("QT_RESPONSE_CACHE_TTL_SECONDS", 86400)
        self.semantic_ttl_seconds = semantic_ttl_seconds if semantic_ttl_seconds is not None else _int_env("QT_RESPONSE_SEMANTIC_TTL_SECONDS", 43200)
        self.semantic_threshold = semantic_threshold
        self.max_entries = max_entries if max_entries is not None else _int_env("QT_RESPONSE_CACHE_MAX_ENTRIES", 250)
        self._encoder = None
        self._lock = threading.Lock()

    @property
    def encoder(self):
        if self._encoder is None:
            try:
                logger.info("[RESPONSE-CACHE] Loading SentenceTransformer model.")
                self._encoder = SentenceTransformer("all-MiniLM-L6-v2")
            except Exception as exc:
                logger.warning(f"[RESPONSE-CACHE] Semantic cache disabled: {exc}")
                self._encoder = None
        return self._encoder

    def _load_state(self) -> dict[str, Any]:
        try:
            with self.cache_path.open("r", encoding="utf-8") as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {}
        except (json.JSONDecodeError, OSError):
            data = {}
        data.setdefault("entries", [])
        return data

    def _save_state(self, state: dict[str, Any]) -> None:
        write_json_atomic(self.cache_path, state, indent=2)

    def _cache_key(self, namespace: str, normalized_query: str) -> str:
        return _stable_hash("response-cache", namespace, normalized_query)

    def _is_exact_fresh(self, entry: dict[str, Any], now: float) -> bool:
        created_at = float(entry.get("created_at", 0.0))
        return (now - created_at) <= self.exact_ttl_seconds

    def _is_semantic_fresh(self, entry: dict[str, Any], now: float) -> bool:
        created_at = float(entry.get("created_at", 0.0))
        return (now - created_at) <= self.semantic_ttl_seconds and bool(entry.get("embedding"))

    def _prune_entries(self, entries: list[dict[str, Any]], now: float) -> list[dict[str, Any]]:
        max_ttl = max(self.exact_ttl_seconds, self.semantic_ttl_seconds)
        fresh_entries = [
            entry for entry in entries
            if (now - float(entry.get("created_at", 0.0))) <= max_ttl
        ]
        fresh_entries.sort(key=lambda item: float(item.get("last_hit_at", item.get("created_at", 0.0))), reverse=True)
        return fresh_entries[: self.max_entries]

    def lookup(self, query: str, namespace: str) -> Optional[dict[str, Any]]:
        normalized_query = normalize_query(query)
        exact_key = self._cache_key(namespace, normalized_query)
        now = time.time()

        with self._lock:
            state = self._load_state()
            entries = self._prune_entries(state.get("entries", []), now)
            state["entries"] = entries

            for entry in entries:
                if entry.get("namespace") != namespace:
                    continue
                if entry.get("key") != exact_key or not self._is_exact_fresh(entry, now):
                    continue
                entry["hits"] = int(entry.get("hits", 0)) + 1
                entry["last_hit_at"] = now
                self._save_state(state)
                return {
                    "response": entry.get("response", ""),
                    "match_type": "exact",
                    "similarity": 1.0,
                    "metadata": entry.get("metadata", {}),
                }

            encoder = self.encoder
            if not encoder:
                self._save_state(state)
                return None

            query_embedding = encoder.encode(normalized_query)
            best_match = None
            best_similarity = 0.0

            for entry in entries:
                if entry.get("namespace") != namespace or not self._is_semantic_fresh(entry, now):
                    continue
                try:
                    cached_embedding = np.array(entry["embedding"])
                    similarity = 1.0 - cosine(query_embedding, cached_embedding)
                except Exception:
                    continue
                if similarity > best_similarity:
                    best_similarity = float(similarity)
                    best_match = entry

            if best_match and best_similarity >= self.semantic_threshold:
                best_match["hits"] = int(best_match.get("hits", 0)) + 1
                best_match["last_hit_at"] = now
                self._save_state(state)
                return {
                    "response": best_match.get("response", ""),
                    "match_type": "semantic",
                    "similarity": round(best_similarity, 4),
                    "metadata": best_match.get("metadata", {}),
                }

            self._save_state(state)
            return None

    def store(
        self,
        *,
        query: str,
        response: str,
        namespace: str,
        metadata: Optional[dict[str, Any]] = None,
        semantic_enabled: bool = True,
    ) -> None:
        normalized_query = normalize_query(query)
        if not normalized_query or not response.strip():
            return

        now = time.time()
        exact_key = self._cache_key(namespace, normalized_query)
        embedding = None

        if semantic_enabled and self.encoder is not None:
            try:
                embedding = self.encoder.encode(normalized_query).tolist()
            except Exception:
                embedding = None

        entry = {
            "key": exact_key,
            "namespace": namespace,
            "query": query,
            "normalized_query": normalized_query,
            "response": response,
            "metadata": metadata or {},
            "created_at": now,
            "last_hit_at": now,
            "hits": 0,
            "embedding": embedding,
        }

        with self._lock:
            state = self._load_state()
            entries = [
                existing for existing in state.get("entries", [])
                if not (
                    existing.get("namespace") == namespace
                    and existing.get("key") == exact_key
                )
            ]
            entries.append(entry)
            state["entries"] = self._prune_entries(entries, now)
            self._save_state(state)
