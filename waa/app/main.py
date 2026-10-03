"""Main entry point for WAA."""
from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path

# Ensure we can import from the project root
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from app.agent import AIChatAgent
from app.config import settings
from app.database import Database
from app.deduplicator import Deduplicator
from app.listener import MessageListener
from app.logging_config import logger
from app.throttle import ReplyThrottle
from app.watchdog import Watchdog
from app.wechat import create_adapter
from app.worker import MessageWorker


def main() -> None:
    parser = argparse.ArgumentParser(description="WAA — WeChat AI Auto Reply Agent")
    parser.add_argument("--daemon", action="store_true", help="Run as daemon")
    parser.add_argument("--health", action="store_true", help="Run health check and exit")
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("WAA starting (env=%s)", settings.app_env)
    logger.info("=" * 60)

    # Initialize database
    db = Database(settings.db_path)
    db.init()

    if args.health:
        _run_health_check(db)
        return

    # Create components
    adapter = create_adapter()
    deduplicator = Deduplicator()
    throttle = ReplyThrottle(
        min_delay=settings.reply_min_delay,
        max_delay=settings.reply_max_delay,
    )
    agent = AIChatAgent()
    watchdog = Watchdog(db)
    listener = MessageListener(adapter, db, deduplicator)
    worker = MessageWorker(adapter, db, throttle)

    # Setup signal handlers
    def _shutdown(signum, frame):
        logger.info("Received signal %d, shutting down...", signum)
        listener.stop()
        worker.stop()
        watchdog.stop()
        db.close()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    # Record initial heartbeat
    watchdog.record_heartbeat("agent", "healthy")
    watchdog.record_heartbeat("database", "healthy")
    watchdog.record_heartbeat("wechat", "unknown")

    # Start services
    watchdog.start()
    listener.start()
    worker.start()

    logger.info("WAA running. Dashboard: http://%s:%d", settings.dashboard_host, settings.dashboard_port)

    try:
        while True:
            time.sleep(1)
            watchdog.record_heartbeat("agent", "healthy")
    except KeyboardInterrupt:
        _shutdown(None, None)


def _run_health_check(db: Database) -> None:
    """Run health check and exit."""
    adapter = create_adapter()
    try:
        checks = {
            "database": db is not None,
            "wechat_running": adapter.is_running(),
            "wechat_accessible": adapter.health_check(),
        }
    except NotImplementedError as e:
        print(f"\n  WARNING: {e}")
        checks = {
            "database": db is not None,
            "wechat_running": adapter.is_running(),
            "wechat_accessible": False,
        }
    print("\nWAA Health Check:")
    for check, result in checks.items():
        status = "OK" if result else "FAIL"
        print(f"  {check}: {status}")
    db.close()


if __name__ == "__main__":
    main()
