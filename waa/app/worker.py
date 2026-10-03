"""Message worker — processes pending messages through safety + AI pipeline."""
from __future__ import annotations

import logging
import threading
import time
from typing import Optional

from app.config import settings
from app.database import Database
from app.logging_config import logger
from app.safety.policy import SafetyPolicy
from app.safety.validator import ReplyValidator
from app.throttle import ReplyThrottle
from app.wechat_adapter import WeChatAdapter

logger = logging.getLogger("waa.worker")


class MessageWorker:
    """Processes pending messages: safety check → AI reply → send."""

    def __init__(
        self,
        adapter: WeChatAdapter,
        db: Database,
        throttle: ReplyThrottle,
        poll_interval: float = 5.0,
    ):
        self._adapter = adapter
        self._db = db
        self._throttle = throttle
        self._poll_interval = poll_interval
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._safety = SafetyPolicy(high_risk_mode=settings.high_risk_mode)
        self._validator = ReplyValidator(max_length=settings.max_reply_length)

    def start(self) -> None:
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True, name="worker")
        self._thread.start()
        logger.info("Message worker started")

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)

    def _run(self) -> None:
        while self._running:
            try:
                self._process_pending()
            except Exception as e:
                logger.error("Worker error: %s", e)
            time.sleep(self._poll_interval)

    def _process_pending(self) -> None:
        pending = self._db.get_pending_messages(limit=10)
        if not pending:
            return

        for msg in pending:
            self._process_one(msg)

    def _process_one(self, msg: dict) -> None:
        contact_id = msg.get("wx_id", msg.get("contact_id", "unknown"))
        content = msg.get("content", "")
        msg_id = msg.get("id")

        if not content.strip():
            self._db.update_message_status(msg_id, "ignored")
            return

        # Throttle check
        if not self._throttle.can_reply(contact_id):
            remaining = self._throttle.get_cooldown_remaining(contact_id)
            logger.debug("Throttled: %s, %.1fs remaining", contact_id, remaining)
            return

        # Safety assessment
        risk_level, risk_reason = self._safety.assess_risk(content)
        logger.info("Message risk=%s contact=%s reason=%s", risk_level, contact_id, risk_reason)

        # Critical risk → block
        if risk_level == "critical":
            logger.warning("Blocked critical message: %s", risk_reason)
            self._db.update_message_status(msg_id, "ignored")
            self._db.log_event(
                "message_blocked", "WARNING",
                f"contact={contact_id} reason={risk_reason}",
                {"contact_id": contact_id, "reason": risk_reason},
            )
            return

        # High risk → warn but may process
        if risk_level == "high" and self._safety.is_safe("high") is False:
            logger.warning("Blocked high-risk message: %s", risk_reason)
            self._db.update_message_status(msg_id, "ignored")
            self._db.log_event(
                "message_blocked", "WARNING",
                f"contact={contact_id} reason={risk_reason}",
                {"contact_id": contact_id, "reason": risk_reason},
            )
            return

        # Mark as processing
        self._db.update_message_status(msg_id, "processing")

        # Get conversation context
        context = self._build_context(contact_id, msg)

        # Generate AI reply
        reply = self._generate_reply(context, risk_level)

        if not reply:
            self._db.update_message_status(msg_id, "failed")
            return

        # Validate reply
        ok, reason = self._validator.validate(reply, risk_level)
        if not ok:
            logger.warning("Reply validation failed: %s", reason)
            self._db.update_message_status(msg_id, "failed")
            return

        # Send reply
        success = self._adapter.send_text(contact_id, reply)
        if success:
            self._db.update_message_status(msg_id, "sent")
            self._throttle.record_reply(contact_id)
            self._db.log_event(
                "message_sent", "INFO",
                f"contact={contact_id} reply={reply[:50]}...",
                {"contact_id": contact_id, "message_id": msg_id},
            )
            logger.info("Reply sent to %s: %.50s...", contact_id, reply)
        else:
            self._db.update_message_status(msg_id, "failed")
            logger.error("Failed to send reply to %s", contact_id)

    def _build_context(self, contact_id: str, current_msg: dict) -> str:
        """Build conversation context from recent messages."""
        recent = self._db.get_recent_messages(contact_id, limit=settings.max_context_messages)
        if not recent:
            return current_msg.get("content", "")

        context_lines = []
        for msg in reversed(recent):
            direction = msg.get("direction", "incoming")
            content = msg.get("content", "")
            if direction == "incoming":
                context_lines.append(f"对方: {content}")
            else:
                context_lines.append(f"我: {content}")

        return "\n".join(context_lines[-(settings.max_context_messages * 2):])

    def _generate_reply(self, context: str, risk_level: str) -> Optional[str]:
        """Generate AI reply using LLM. Placeholder for Phase F."""
        # TODO: Integrate with LLM API
        # For now, return a simple placeholder
        logger.debug("Generating reply for context (risk=%s)", risk_level)
        return None  # Will be implemented in Phase F
