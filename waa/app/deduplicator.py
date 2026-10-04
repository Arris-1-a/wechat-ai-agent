"""Message deduplication engine."""
from __future__ import annotations

import hashlib
import threading
import time
from typing import Optional


class Deduplicator:
    """Prevents duplicate message processing using content hash."""

    def __init__(self, max_cache_size: int = 10000, ttl_seconds: int = 3600):
        self._seen: dict[str, float] = {}
        self._lock = threading.Lock()
        self._max_size = max_cache_size
        self._ttl = ttl_seconds

    @staticmethod
    def make_key(contact_id: str, content: str, timestamp: str) -> str:
        raw = f"{contact_id}|{timestamp}|{content}"
        return hashlib.sha256(raw.encode()).hexdigest()[:16]

    def is_duplicate(self, key: str) -> bool:
        now = time.time()
        with self._lock:
            self._cleanup(now)
            if key in self._seen:
                return True
            self._seen[key] = now
            self._evict_if_needed()
        return False

    def _cleanup(self, now: float) -> None:
        cutoff = now - self._ttl
        expired = [k for k, v in self._seen.items() if v < cutoff]
        for k in expired:
            del self._seen[k]

    def _evict_if_needed(self) -> None:
        if len(self._seen) > self._max_size:
            sorted_keys = sorted(self._seen, key=self._seen.get)
            for k in sorted_keys[: len(self._seen) - self._max_size // 2]:
                del self._seen[k]

    @property
    def size(self) -> int:
        return len(self._seen)

    def clear(self) -> None:
        with self._lock:
            self._seen.clear()
