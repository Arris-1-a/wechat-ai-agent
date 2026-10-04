"""Main entry point for WAA with PID management and graceful shutdown."""
from __future__ import annotations

import argparse
import os
import signal
import sys
import time
from pathlib import Path

project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.config import settings
from app.database import Database
from app.deduplicator import Deduplicator
from app.dashboard import Dashboard
from app.listener import MessageListener
from app.logging_config import logger
from app.state import state
from app.throttle import ReplyThrottle
from app.watchdog import Watchdog
from app.wechat import create_adapter
from app.worker import MessageWorker

_components = {}


def _write_pid() -> None:
    settings.pid_path.parent.mkdir(parents=True, exist_ok=True)
    settings.pid_path.write_text(str(os.getpid()))


def _remove_pid() -> None:
    try:
        settings.pid_path.unlink(missing_ok=True)
    except OSError:
        pass


def _shutdown(signum: int, frame) -> None:
    logger.info("Received signal %d, shutting down gracefully...", signum)
    for name in ("listener", "worker", "watchdog"):
        comp = _components.get(name)
        if comp and hasattr(comp, "stop"):
            comp.stop()
    _components.get("agent") and _components["agent"].close()
    db = _components.get("db")
    if db:
        db.close()
    _remove_pid()
    logger.info("WAA stopped.")
    sys.exit(0)


def main() -> None:
    parser = argparse.ArgumentParser(description="WAA — WeChat AI Auto Reply Agent")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--health", action="store_true", help="Run health check and exit")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("WAA starting (env=%s)", settings.app_env)
    logger.info("=" * 60)

    _write_pid()
    state.pid = os.getpid()
    state.start_time = time.time()

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    db = Database(settings.db_path)
    db.init()
    _components["db"] = db

    if args.health:
        _run_health_check(db)
        db.close()
        return

    adapter = create_adapter()
    deduplicator = Deduplicator()
    throttle = ReplyThrottle(min_delay=settings.reply_min_delay, max_delay=settings.reply_max_delay)
    watchdog = Watchdog(db)
    listener = MessageListener(adapter, db, deduplicator)
    worker = MessageWorker(adapter, db, throttle)
    dashboard = Dashboard(db)

    _components.update({
        "adapter": adapter,
        "deduplicator": deduplicator,
        "throttle": throttle,
        "watchdog": watchdog,
        "listener": listener,
        "worker": worker,
        "dashboard": dashboard,
    })

    watchdog.record_heartbeat("agent", "healthy")
    watchdog.record_heartbeat("database", "healthy")
    watchdog.record_heartbeat("wechat", "unknown")

    watchdog.start()
    listener.start()
    worker.start()
    dashboard.start_server()

    state.agent_running = True
    logger.info("WAA running. Dashboard: %s", settings.dashboard_url)

    try:
        while True:
            time.sleep(1)
            watchdog.record_heartbeat("agent", "healthy")
    except KeyboardInterrupt:
        _shutdown(2, None)


def _run_health_check(db: Database) -> None:
    """Run health check and exit."""
    from app.wechat import create_adapter
    adapter = create_adapter()
    checks = {
        "database": True,
        "wechat_running": adapter.is_running(),
        "wechat_accessible": False,
    }
    try:
        checks["wechat_accessible"] = adapter.health_check()
    except Exception:
        pass

    print("\nWAA Health Check:")
    for check, result in checks.items():
        status = "OK" if result else "FAIL"
        print(f"  {check}: {status}")

    errors = settings.validate()
    if errors:
        print("\nConfiguration errors:")
        for e in errors:
            print(f"  ✗ {e}")
    else:
        print("\nConfiguration: OK")

    db.close()


if __name__ == "__main__":
    main()
