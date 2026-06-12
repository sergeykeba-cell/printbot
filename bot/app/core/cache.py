"""
cache.py — асинхронний TTL-кеш в пам'яті.
Thread-safe через asyncio.Lock. Не потребує зовнішніх залежностей.
"""
import asyncio
import time
from typing import Any


class TTLCache:
    def __init__(self, ttl: int = 300):
        self._store: dict[str, tuple[Any, float]] = {}
        self._lock = asyncio.Lock()
        self.ttl = ttl

    async def get(self, key: str) -> Any | None:
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                return None
            return value

    async def get_stale(self, key: str) -> Any | None:
        """Повертає значення навіть якщо прострочене (stale fallback)."""
        async with self._lock:
            entry = self._store.get(key)
            return entry[0] if entry else None

    async def set(self, key: str, value: Any) -> None:
        async with self._lock:
            self._store[key] = (value, time.monotonic() + self.ttl)

    async def delete(self, key: str) -> None:
        async with self._lock:
            self._store.pop(key, None)


# Глобальний інстанс — shared між всіма запитами
instance_config_cache = TTLCache(ttl=300)
