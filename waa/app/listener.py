"""Message listener — captures incoming WeChat messages."""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from app.config import settings
from app.database import Database
from app.deduplicator import Deduplicator
from app.logging_config import logger
from app.state import state
from app.wechat_adapter import WeChatAdapter

logger = logging.getLogger("waa.listener")


class MessageListener:
    """Polls WeChat adapter for new messages and queues them."""

    def __init__(
        self,
        adapter: WeChatAdapter,
        db: Database,
        deduplicator: Deduplicator,
        poll_interval: float = 2.0,
    ):
        self._adapter = adapter
        self._db = db
        self._dedup = deduplicator
        self._poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._queue: list[dict] = []
        self._lock = threading.Lock()

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="listener")
        self._thread.start()
        logger.info("Message listener started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while self._running:
            try:
                self._poll()
            except Exception as e:
                logger.error("Listener poll error: %s", e)
            time.sleep(self._poll_interval)

    def _poll(self) -> None:
        if not self._adapter.is_running():
            return

        try:
            messages = self._adapter.get_unread_messages()
        except NotImplementedError:
            logger.debug("Adapter not ready (Accessibility permission needed)")
            return
        except Exception as e:
            logger.error("Failed to get messages: %s", e)
            return

        for msg in messages:
            dedup_key = Deduplicator.make_key(
                msg.get("contact_id", ""),
                msg.get("content", ""),
                msg.get("timestamp", ""),
            )

            if self._dedup.is_duplicate(dedup_key):
                logger.debug("Duplicate message skipped: %s", dedup_key[:8])
                continue

            # Upsert contact
            contact_id = msg.get("contact_id", "unknown")
            contact = self._db.get_contact(contact_id)
            if not contact:
                contact_id_int = self._db.upsert_contact(
                    contact_id, msg.get("display_name", contact_id)
                )
            else:
                contact_id_int = contact["id"]

            # Persist message
            msg_id = self._db.insert_message(
                contact_id=contact_id_int,
                direction="incoming",
                content=msg.get("content", ""),
                message_type=msg.get("message_type", "text"),
                timestamp=msg.get("timestamp", ""),
                wx_message_id=msg.get("wx_message_id"),
                status="received",
            )

            logger.info(
                "Message received: contact=%s id=%s content=%.50s...",
                contact_id, msg_id, msg.get("content", ""),
            )

            self._db.log_event(
                "message_received", "INFO",
                f"contact={contact_id} id={msg_id}",
                {"contact_id": contact_id, "message_id": msg_id},
            )
