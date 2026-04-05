from __future__ import annotations

import hashlib
import ipaddress
import json
import os
import re
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from fastapi import Request, UploadFile

from quantum_tutor_paths import API_ABUSE_STATE_PATH, API_EDGE_RATE_LIMITS_PATH, ensure_output_dirs, write_json_atomic
from security_audit import SecurityEventLogger
from security_controls import AbuseDecision, FileAbusePrevention


def _bool_env(name: str, default: bool = False) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


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


def _normalize_text(value: str, max_len: int = 128) -> str:
    collapsed = re.sub(r"\s+", " ", (value or "").strip())
    return collapsed[:max_len]


def _hash_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


@dataclass
class ClientIdentity:
    remote_addr: str
    client_ip: str
    forwarded_ip: str
    authenticated_user: str
    user_agent_hash: str
    source: str
    proxy_trusted: bool
    rate_limit_key: str
    abuse_key: str
    provider_user_id: str


@dataclass
class EdgeRateLimitDecision:
    allowed: bool
    retry_after_seconds: float
    remaining_tokens: float
    capacity: float
    refill_tokens: float
    refill_seconds: float
    consumed_tokens: float
    route: str
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
            "route": self.route,
            "bucket_id": self.bucket_id,
        }


class FileEdgeRateLimiter:
    def __init__(self, state_path: Path = API_EDGE_RATE_LIMITS_PATH):
        ensure_output_dirs()
        self.state_path = Path(state_path)
        self._lock = threading.Lock()

    def _load_state(self) -> dict[str, Any]:
        try:
            with self.state_path.open("r", encoding="utf-8") as handle:
                payload = json.load(handle)
        except (FileNotFoundError, json.JSONDecodeError, OSError):
            payload = {}
        payload.setdefault("buckets", {})
        return payload

    def _save_state(self, payload: dict[str, Any]) -> None:
        write_json_atomic(self.state_path, payload, indent=2, ensure_ascii=False)

    def _bucket_id(self, route: str, bucket_key: str) -> str:
        return _hash_text(f"{route}::{bucket_key}")[:24]

    def _refill(self, bucket: dict[str, Any], now: float, capacity: float, refill_rate: float) -> float:
        tokens = float(bucket.get("tokens", capacity))
        last_refill_at = float(bucket.get("last_refill_at", now))
        elapsed = max(now - last_refill_at, 0.0)
        replenished = elapsed * refill_rate
        return min(capacity, tokens + replenished)

    def consume(
        self,
        *,
        route: str,
        bucket_key: str,
        capacity: float,
        refill_tokens: float,
        refill_seconds: float,
        cost: float = 1.0,
    ) -> EdgeRateLimitDecision:
        now = time.time()
        refill_rate = (refill_tokens / refill_seconds) if refill_seconds > 0 else 0.0
        bucket_id = self._bucket_id(route, bucket_key)

        with self._lock:
            state = self._load_state()
            bucket = state["buckets"].get(bucket_id, {})
            tokens = self._refill(bucket, now, capacity, refill_rate)

            if tokens < cost:
                state["buckets"][bucket_id] = {
                    "route": route,
                    "tokens": tokens,
                    "last_refill_at": now,
                }
                self._save_state(state)
                retry_after = ((cost - tokens) / refill_rate) if refill_rate > 0 else refill_seconds
                return EdgeRateLimitDecision(
                    allowed=False,
                    retry_after_seconds=max(retry_after, 0.0),
                    remaining_tokens=max(tokens, 0.0),
                    capacity=capacity,
                    refill_tokens=refill_tokens,
                    refill_seconds=refill_seconds,
                    consumed_tokens=0.0,
                    route=route,
                    bucket_id=bucket_id,
                )

            tokens -= cost
            state["buckets"][bucket_id] = {
                "route": route,
                "tokens": tokens,
                "last_refill_at": now,
            }
            self._save_state(state)
            return EdgeRateLimitDecision(
                allowed=True,
                retry_after_seconds=0.0,
                remaining_tokens=max(tokens, 0.0),
                capacity=capacity,
                refill_tokens=refill_tokens,
                refill_seconds=refill_seconds,
                consumed_tokens=cost,
                route=route,
                bucket_id=bucket_id,
            )


class APISecurityManager:
    def __init__(
        self,
        edge_state_path: Path = API_EDGE_RATE_LIMITS_PATH,
        abuse_state_path: Path = API_ABUSE_STATE_PATH,
    ):
        self.edge_rate_limiter = FileEdgeRateLimiter(edge_state_path)
        self.abuse_prevention = FileAbusePrevention(abuse_state_path)
        self.audit_logger = SecurityEventLogger()
        self.trust_proxy_headers = _bool_env("QT_TRUST_PROXY_HEADERS", False)
        self.allow_proxy_user_id = _bool_env("QT_ALLOW_PROXY_USER_ID", False)
        self.allow_direct_user_id = _bool_env("QT_ALLOW_DIRECT_USER_ID", False)
        self.trusted_proxy_ranges = [
            item.strip()
            for item in os.getenv("QT_TRUSTED_PROXY_RANGES", "127.0.0.1,::1,localhost").split(",")
            if item.strip()
        ]
        self.chat_capacity = _float_env("QT_EDGE_CHAT_CAPACITY", 30.0)
        self.chat_refill_tokens = _float_env("QT_EDGE_CHAT_REFILL_TOKENS", 15.0)
        self.chat_refill_seconds = _float_env("QT_EDGE_CHAT_REFILL_SECONDS", 60.0)
        self.vision_capacity = _float_env("QT_EDGE_VISION_CAPACITY", 6.0)
        self.vision_refill_tokens = _float_env("QT_EDGE_VISION_REFILL_TOKENS", 3.0)
        self.vision_refill_seconds = _float_env("QT_EDGE_VISION_REFILL_SECONDS", 60.0)
        self.max_chat_body_bytes = _int_env("QT_API_MAX_BODY_BYTES", 65536)
        self.max_history_messages = _int_env("QT_API_MAX_HISTORY_MESSAGES", 40)
        self.max_history_chars = _int_env("QT_API_MAX_HISTORY_CHARS", 12000)
        self.max_history_entry_chars = _int_env("QT_API_MAX_HISTORY_ENTRY_CHARS", 4000)
        self.max_vision_upload_bytes = _int_env("QT_VISION_MAX_UPLOAD_BYTES", 5 * 1024 * 1024)
        self.allowed_vision_types = {
            item.strip().lower()
            for item in os.getenv("QT_VISION_ALLOWED_TYPES", "image/png,image/jpeg,image/webp").split(",")
            if item.strip()
        }
        self.allowed_vision_suffixes = {
            item.strip().lower()
            for item in os.getenv("QT_VISION_ALLOWED_SUFFIXES", ".png,.jpg,.jpeg,.webp").split(",")
            if item.strip()
        }
        self.abuse_points = {
            "EDGE_RATE_LIMITED": 15.0,
            "PAYLOAD_TOO_LARGE": 25.0,
            "HISTORY_TOO_LONG": 10.0,
            "HISTORY_TOO_LARGE": 10.0,
            "HISTORY_ENTRY_TOO_LONG": 8.0,
            "INVALID_HISTORY_ROLE": 8.0,
            "UNSUPPORTED_MEDIA_TYPE": 12.0,
            "UNSUPPORTED_FILE_EXTENSION": 12.0,
            "IMAGE_TOO_LARGE": 20.0,
            "EMPTY_UPLOAD": 6.0,
        }

    def _is_trusted_proxy(self, remote_addr: str) -> bool:
        raw_value = (remote_addr or "").strip()
        if not raw_value:
            return False
        for candidate in self.trusted_proxy_ranges:
            try:
                network = ipaddress.ip_network(candidate, strict=False)
                ip_value = ipaddress.ip_address(raw_value)
                if ip_value in network:
                    return True
                continue
            except ValueError:
                if raw_value == candidate:
                    return True
        return False

    def _sanitize_user_identifier(self, value: Optional[str]) -> str:
        cleaned = _normalize_text(value or "", max_len=128)
        if not cleaned:
            return ""
        return re.sub(r"[^A-Za-z0-9@._:-]", "", cleaned)[:128]

    def _first_forwarded_ip(self, request: Request) -> str:
        forwarded_for = _normalize_text(request.headers.get("x-forwarded-for", ""), max_len=256)
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        return _normalize_text(request.headers.get("x-real-ip", ""), max_len=64)

    def resolve_identity(self, request: Request, claimed_user_id: Optional[str] = None) -> ClientIdentity:
        remote_addr = _normalize_text(request.client.host if request.client else "unknown", max_len=128) or "unknown"
        trusted_proxy = self.trust_proxy_headers and self._is_trusted_proxy(remote_addr)
        forwarded_ip = ""
        authenticated_user = ""
        source = "remote_addr"

        if trusted_proxy:
            forwarded_ip = self._first_forwarded_ip(request)
            authenticated_user = self._sanitize_user_identifier(request.headers.get("x-authenticated-user"))
            if not authenticated_user and self.allow_proxy_user_id:
                authenticated_user = self._sanitize_user_identifier(
                    request.headers.get("x-user-id") or claimed_user_id
                )
            if authenticated_user:
                source = "trusted_proxy_authenticated_user"
            elif forwarded_ip:
                source = "trusted_proxy_forwarded_ip"
        elif self.allow_direct_user_id:
            authenticated_user = self._sanitize_user_identifier(claimed_user_id)
            if authenticated_user:
                source = "direct_user_id"

        client_ip = forwarded_ip or remote_addr
        user_agent_hash = _hash_text(_normalize_text(request.headers.get("user-agent", ""), max_len=256) or "unknown")[:12]
        if authenticated_user:
            bucket_key = f"user:{authenticated_user}"
            abuse_key = f"user:{authenticated_user}"
        else:
            bucket_key = f"ip:{client_ip}|ua:{user_agent_hash}"
            abuse_key = f"ip:{client_ip}"

        return ClientIdentity(
            remote_addr=remote_addr,
            client_ip=client_ip,
            forwarded_ip=forwarded_ip,
            authenticated_user=authenticated_user,
            user_agent_hash=user_agent_hash,
            source=source,
            proxy_trusted=trusted_proxy,
            rate_limit_key=bucket_key,
            abuse_key=abuse_key,
            provider_user_id=bucket_key,
        )

    def check_temporary_block(self, identity: ClientIdentity, request_id: str | None = None) -> AbuseDecision:
        decision = self.abuse_prevention.inspect(identity.abuse_key)
        if decision.blocked:
            fields = {
                "identity": identity.abuse_key,
                "client_ip": identity.client_ip,
                "retry_after_seconds": decision.retry_after_seconds,
                "score": decision.score,
                "reason": decision.reason,
            }
            if request_id:
                fields["request_id"] = request_id
            self.audit_logger.log_event(
                event_type="api_security",
                action="temporary_block_enforced",
                severity="WARNING",
                fields=fields,
            )
        return decision

    def record_abuse(
        self,
        identity: ClientIdentity,
        reason: str,
        points: float | None = None,
        request_id: str | None = None,
    ) -> AbuseDecision:
        score = self.abuse_points.get(reason, 0.0) if points is None else points
        decision = self.abuse_prevention.record_event(identity.abuse_key, score, reason)
        fields = {
            "identity": identity.abuse_key,
            "client_ip": identity.client_ip,
            "reason": reason,
            "points": score,
            "score": decision.score,
            "blocked": decision.blocked,
            "retry_after_seconds": decision.retry_after_seconds,
            "block_count": decision.block_count,
        }
        if request_id:
            fields["request_id"] = request_id
        self.audit_logger.log_event(
            event_type="api_security",
            action="abuse_score_updated",
            severity="WARNING" if decision.blocked else "INFO",
            fields=fields,
        )
        return decision

    def _edge_limits_for_route(self, route: str) -> tuple[float, float, float, float]:
        if route == "vision":
            return self.vision_capacity, self.vision_refill_tokens, self.vision_refill_seconds, 1.0
        return self.chat_capacity, self.chat_refill_tokens, self.chat_refill_seconds, 1.0

    def enforce_edge_rate_limit(self, route: str, identity: ClientIdentity) -> EdgeRateLimitDecision:
        capacity, refill_tokens, refill_seconds, cost = self._edge_limits_for_route(route)
        return self.edge_rate_limiter.consume(
            route=route,
            bucket_key=identity.rate_limit_key,
            capacity=capacity,
            refill_tokens=refill_tokens,
            refill_seconds=refill_seconds,
            cost=cost,
        )

    def validate_chat_request(self, request: Request, history: list[Any]) -> tuple[bool, int, str, str]:
        content_length = _int_env("QT_API_MAX_BODY_BYTES", self.max_chat_body_bytes)
        announced_length = request.headers.get("content-length")
        if announced_length:
            try:
                if int(announced_length) > content_length:
                    return False, 413, "PAYLOAD_TOO_LARGE", "La solicitud excede el tamano maximo permitido."
            except ValueError:
                pass

        if len(history) > self.max_history_messages:
            return False, 400, "HISTORY_TOO_LONG", "La conversacion excede el maximo permitido de mensajes previos."

        total_chars = 0
        for item in history:
            content = getattr(item, "content", "")
            total_chars += len(content or "")
            if len(content or "") > self.max_history_entry_chars:
                return False, 400, "HISTORY_ENTRY_TOO_LONG", "Uno de los mensajes del historial excede el tamano permitido."
            role = (getattr(item, "role", "") or "").strip().lower()
            if role and role not in {"user", "assistant", "system"}:
                return False, 400, "INVALID_HISTORY_ROLE", "El historial contiene un rol no permitido."

        if total_chars > self.max_history_chars:
            return False, 400, "HISTORY_TOO_LARGE", "La conversacion acumulada excede el tamano permitido."

        return True, 200, "", ""

    def validate_vision_upload(self, request: Request, file: UploadFile) -> tuple[bool, int, str, str]:
        announced_length = request.headers.get("content-length")
        if announced_length:
            try:
                if int(announced_length) > self.max_vision_upload_bytes:
                    return False, 413, "IMAGE_TOO_LARGE", "La imagen excede el tamano maximo permitido."
            except ValueError:
                pass

        content_type = (file.content_type or "").strip().lower()
        if content_type not in self.allowed_vision_types:
            return False, 415, "UNSUPPORTED_MEDIA_TYPE", "Solo se aceptan imagenes PNG, JPEG o WEBP."

        suffix = Path(file.filename or "upload.bin").suffix.lower()
        if suffix and suffix not in self.allowed_vision_suffixes:
            return False, 415, "UNSUPPORTED_FILE_EXTENSION", "La extension del archivo no esta permitida."

        return True, 200, "", ""

    async def read_limited_upload(self, file: UploadFile) -> tuple[bool, bytes, int, str, str]:
        payload = await file.read()
        if not payload:
            return False, b"", 400, "EMPTY_UPLOAD", "La imagen subida esta vacia."
        if len(payload) > self.max_vision_upload_bytes:
            return False, b"", 413, "IMAGE_TOO_LARGE", "La imagen excede el tamano maximo permitido."
        return True, payload, 200, "", ""
