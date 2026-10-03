"""Watchdog — monitors all services and restarts on failure."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from typing import Callable, Optional

from app.config import settings
from app.logging_config import logger

logger = logging.getLogger("waa.watchdog")


class Watchdog:
    """Monitors service health via heartbeats and triggers alerts."""

    def __init__(
        self,
        db,
        check_interval: int = 30,
        heartbeat_timeout: int = 90,
    ):
        self._db = db
        self._check_interval = check_interval
        self._heartbeat_timeout = heartbeat_timeout
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._callbacks: dict[str, list[Callable]] = {}

    def register_callback(self, service: str, callback: Callable) -> None:
        if service not in self._callbacks:
            self._callbacks[service] = []
        self._callbacks[service].append(callback)

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="watchdog")
        self._thread.start()
        logger.info("Watchdog started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while self._running:
            try:
                self._check()
            except Exception as e:
                logger.error("Watchdog check error: %s", e)
            time.sleep(self._check_interval)

    def _check(self) -> None:
        now = datetime.utcnow().isoformat()
        heartbeats = self._db.get_heartbeats()
        timeout_ts = time.time() - self._heartbeat_timeout

        for service, data in heartbeats.items():
            last_seen = data.get("last_seen", "")
            if last_seen:
                try:
                    last_dt = datetime.fromisoformat(last_seen)
                    if last_dt.timestamp() < timeout_ts:
                        logger.warning("Service %s heartbeat timeout", service)
                        self._db.log_event(
                            "heartbeat_timeout", "WARNING",
                            f"Service {service} heartbeat timeout",
                            {"service": service},
                        )
                        self._fire_callbacks(service, f"heartbeat_timeout:{service}")
                except (ValueError, TypeError):
                    pass

    def _fire_callbacks(self, service: str, event: str) -> None:
        for cb in self._callbacks.get(service, []):
            try:
                cb(event)
            except Exception as e:
                logger.error("Watchdog callback error: %s", e)

    def record_heartbeat(self, service: str, status: str = "healthy", metadata: Optional[dict] = None) -> None:
        self._db.update_heartbeat(service, status, metadata)
