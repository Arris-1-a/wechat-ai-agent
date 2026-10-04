"""Shared process-level state — auto-reply toggle, safe mode, emergency stop."""
from __future__ import annotations

import threading
from typing import Optional


class AppState:
    """Global process state shared across all modules."""

    _instance: Optional["AppState"] = None
    _lock = threading.Lock()

    def __new__(cls) -> "AppState":
        with cls._lock:
            if cls._instance is None:
                cls._instance = super().__new__(cls)
                cls._instance._init()
            return cls._instance

    def _init(self) -> None:
        self.auto_reply_enabled: bool = True
        self.safe_mode: bool = True
        self.agent_running: bool = False
        self.wechat_status: str = "unknown"
        self.ai_status: str = "unknown"
        self.db_status: str = "unknown"
        self.dashboard_url: str = "http://127.0.0.1:8765"
        self.pid: Optional[int] = None
        self.start_time: Optional[float] = None

    def emergency_stop(self) -> None:
        """Immediately disable all auto-reply behavior."""
        self.auto_reply_enabled = False
        self.safe_mode = True

    def restart(self) -> None:
        self._init()


state = AppState()
