import asyncio
import time
from pathlib import Path
from typing import Dict, Any

from relational_engine import RelationalMind
from learning_analytics import LearningAnalytics
from semantic_cache import SemanticCache
from quantum_tutor_paths import BASE_DIR, SEMANTIC_CACHE_PATH, STUDENT_PROFILE_PATH


class SessionStore:
    """
    Session Store in-memory (v6 base).
    Thread-safe / async-safe mediante locks por sesión.
    """

    def __init__(self, ttl_seconds: int = 3600):
        self._store: Dict[str, Dict[str, Any]] = {}
        self._locks: Dict[str, asyncio.Lock] = {}
        self._ttl = ttl_seconds

    def _now(self):
        return time.time()

    def _is_expired(self, session_data):
        return self._now() - session_data["last_access"] > self._ttl

    async def _get_lock(self, session_id: str) -> asyncio.Lock:
        if session_id not in self._locks:
            self._locks[session_id] = asyncio.Lock()
        return self._locks[session_id]

    async def get_or_create(
        self,
        session_id: str,
        factory_fn
    ) -> Dict[str, Any]:
        """
        Obtiene o crea estado de sesión de forma segura.
        factory_fn -> crea relational, analytics, cache
        """
        lock = await self._get_lock(session_id)

        async with lock:
            session = self._store.get(session_id)

            if session is None or self._is_expired(session):
                session = {
                    "data": factory_fn(),
                    "created_at": self._now(),
                    "last_access": self._now()
                }
                self._store[session_id] = session
            else:
                session["last_access"] = self._now()

            return session["data"]

    async def update(
        self,
        session_id: str,
        updater_fn
    ):
        """
        Permite mutar el estado de sesión de forma controlada.
        """
        lock = await self._get_lock(session_id)
        async with lock:
            session = self._store.get(session_id)
            if not session:
                return
            updater_fn(session["data"])
            session["last_access"] = self._now()

    async def delete(self, session_id: str):
        lock = await self._get_lock(session_id)
        async with lock:
            self._store.pop(session_id, None)
            self._locks.pop(session_id, None)

    async def cleanup(self):
        """
        Limpieza de sesiones expiradas.
        Ejecutar periódicamente (background task).
        """
        now = self._now()
        to_delete = []

        for sid, session in self._store.items():
            if now - session["last_access"] > self._ttl:
                to_delete.append(sid)

        for sid in to_delete:
            await self.delete(sid)


def create_session_state(base_dir: str):
    resolved_base_dir = BASE_DIR if not base_dir else Path(base_dir)
    profile_path = (
        STUDENT_PROFILE_PATH
        if resolved_base_dir.resolve() == BASE_DIR
        else resolved_base_dir / "student_profile.json"
    )
    cache_path = (
        SEMANTIC_CACHE_PATH
        if resolved_base_dir.resolve() == BASE_DIR
        else resolved_base_dir / "semantic_cache.json"
    )
    return {
        "relational": RelationalMind(),
        "analytics": LearningAnalytics(profile_path),
        "cache": SemanticCache(cache_file=cache_path, threshold=0.70)
    }
