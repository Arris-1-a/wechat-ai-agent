"""macOS Accessibility-based WeChat adapter."""
from __future__ import annotations

import logging
import time
from typing import Optional

from AppKit import NSWorkspace
from AXUIElement import AXUIElement, AXValueCreate

from app.wechat_adapter import WeChatAdapter
from app.logging_config import logger

logger = logging.getLogger("waa.adapter")


class AccessibilityAdapter(WeChatAdapter):
    """WeChat automation via macOS Accessibility API."""

    def __init__(self):
        self._wechat_pid: Optional[int] = None
        self._ax_ref: Optional[AXUIElement] = None
        self._last_check: float = 0
        self._health: bool = False

    def _get_wechat_pid(self) -> Optional[int]:
        ws = NSWorkspace.sharedWorkspace()
        for app in ws.runningApplications():
            if app.localizedName() == "WeChat":
                return app.processIdentifier()
        return None

    def _ensure_ref(self) -> bool:
        """Reconnect AXUIElement reference if stale."""
        now = time.time()
        if now - self._last_check < 5:
            return self._health

        self._wechat_pid = self._get_wechat_pid()
        if self._wechat_pid is None:
            self._health = False
            return False

        self._ax_ref = AXUIElementCreateApplication(self._wechat_pid)
        self._last_check = now
        self._health = True
        return True

    def health_check(self) -> bool:
        try:
            return self._ensure_ref()
        except Exception as e:
            logger.warning("Health check failed: %s", e)
            self._health = False
            return False

    def is_running(self) -> bool:
        return self._wechat_pid is not None or self._get_wechat_pid() is not None

    def is_logged_in(self) -> bool:
        if not self._ensure_ref():
            return False
        # Check if WeChat shows a login window
        try:
            error, focused = AXUIElementCopyAttributeValue(
                self._ax_ref, "AXFocusedWindow", None
            )
            if error != 0:
                return False
            # If focused window is a login dialog, not logged in
            error2, role = AXUIElementCopyAttributeValue(focused, "AXRole", None)
            return role != "AXDialog" or not self._is_login_dialog(focused)
        except Exception:
            return True  # Assume logged in if we can't verify

    def _is_login_dialog(self, window) -> bool:
        try:
            error, title = AXUIElementCopyAttributeValue(window, "AXTitle", None)
            if error == 0 and title:
                return "登录" in str(title) or "Login" in str(title)
        except Exception:
            pass
        return False

    def get_unread_messages(self) -> list[dict]:
        if not self._ensure_ref():
            return []
        # TODO: Implement based on WeChat AX tree exploration
        return []

    def get_recent_messages(self, contact_id: str, limit: int = 20) -> list[dict]:
        if not self._ensure_ref():
            return []
        # TODO: Navigate to contact chat and read messages
        return []

    def open_chat(self, contact_id: str) -> bool:
        if not self._ensure_ref():
            return False
        # TODO: Search for contact and open chat
        return False

    def send_text(self, contact_id: str, message: str) -> bool:
        if not self._ensure_ref():
            return False
        # TODO: Navigate to chat, type message, send
        return False

    def get_contacts(self) -> list[dict]:
        if not self._ensure_ref():
            return []
        # TODO: Read contact list from AX tree
        return []

    def verify_message_sent(self, contact_id: str, message: str) -> bool:
        if not self._ensure_ref():
            return False
        # TODO: Check if message appears in chat
        return False

    def __del__(self):
        self._ax_ref = None
        self._wechat_pid = None
