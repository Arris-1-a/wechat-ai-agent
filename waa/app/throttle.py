"""Reply throttle — prevents rapid-fire responses to the same contact."""
from __future__ import annotations

import time

class ReplyThrottle:
    """Enforces minimum delay between replies to the same contact."""

    def __init__(self, min_delay: int = 3, max_delay: int = 8):
        self._min_delay = min_delay
        self._max_delay = max_delay
        self._last_reply: dict[str, float] = {}

    def can_reply(self, contact_id: str) -> bool:
        now = time.time()
        last = self._last_reply.get(contact_id, 0)
        return (now - last) >= self._min_delay

    def record_reply(self, contact_id: str) -> None:
        self._last_reply[contact_id] = time.time()

    def next_delay(self, contact_id: str) -> int:
        """Return how many seconds to wait before next reply."""
        return self._min_delay

    def get_cooldown_remaining(self, contact_id: str) -> float:
        now = time.time()
        last = self._last_reply.get(contact_id, 0)
        remaining = self._min_delay - (now - last)
        return max(0.0, remaining)
