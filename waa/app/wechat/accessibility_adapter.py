"""macOS Accessibility-based WeChat adapter."""
from __future__ import annotations

import logging
import subprocess
import time
from typing import Optional

from AppKit import NSWorkspace

from app.wechat_adapter import WeChatAdapter

logger = logging.getLogger("waa.adapter")


class AccessibilityAdapter(WeChatAdapter):
    """WeChat automation via macOS Accessibility API (osascript + AX)."""

    def __init__(self):
        self._wechat_pid: Optional[int] = None
        self._last_check: float = 0
        self._health: bool = False

    # ── Core helpers ──────────────────────────────────────────

    def _get_wechat_pid(self) -> Optional[int]:
        ws = NSWorkspace.sharedWorkspace()
        for app in ws.runningApplications():
            name = app.localizedName()
            if name and ("WeChat" in name or "微信" in name):
                return app.processIdentifier()
        return None

    def _ensure_ref(self) -> bool:
        """Verify WeChat is running and accessible."""
        now = time.time()
        if now - self._last_check < 5:
            return self._health

        self._wechat_pid = self._get_wechat_pid()
        if self._wechat_pid is None:
            self._health = False
            return False

        # Verify accessibility by trying a simple AX query
        try:
            result = self._osascript('tell application "System Events" to get name of every UI element of process "WeChat"')
            if result is not None:
                self._health = True
            else:
                self._health = False
        except Exception:
            self._health = False
            return False

        self._last_check = now
        return self._health

    def _osascript(self, script: str) -> Optional[str]:
        """Execute an AppleScript and return output, or None on failure."""
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                return result.stdout.strip()
            return None
        except Exception as e:
            logger.debug("_osascript failed: %s", e)
            return None

    def _osascript_click(self, script: str) -> bool:
        """Execute an AppleScript that performs a click or action."""
        try:
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                text=True,
                timeout=10,
            )
            return result.returncode == 0
        except Exception as e:
            logger.debug("_osascript_click failed: %s", e)
            return False

    def _osascript_type(self, text: str) -> bool:
        """Type text using System Events."""
        # Escape quotes in text
        escaped = text.replace('"', '\\"')
        script = f'tell application "System Events" to keystroke "{escaped}"'
        return self._osascript_click(script)

    def _osascript_enter(self) -> bool:
        """Press Enter key."""
        return self._osascript_click('tell application "System Events" to key code 36')

    def _osascript_command_a(self) -> bool:
        """Select all (Cmd+A)."""
        return self._osascript_click('tell application "System Events" to tell process "WeChat" to keystroke "a" using command down')

    def _osascript_delete(self) -> bool:
        """Delete selected text (Backspace)."""
        return self._osascript_click('tell application "System Events" to key code 51')

    # ── Health checks ─────────────────────────────────────────

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
        # Check if WeChat main window is open and not a login dialog
        try:
            result = self._osascript(
                'tell application "System Events" to get name of every window of process "WeChat"'
            )
            if result:
                windows = result.split(", ")
                for w in windows:
                    if "登录" in w or "Login" in w:
                        return False
                return True
        except Exception:
            pass
        return True  # Assume logged in if we can't verify

    # ── Message reading ───────────────────────────────────────

    def get_unread_messages(self) -> list[dict]:
        if not self._ensure_ref():
            return []
        try:
            return self._scan_unread_messages()
        except Exception as e:
            logger.error("get_unread_messages failed: %s", e)
            return []

    def _scan_unread_messages(self) -> list[dict]:
        """Scan for unread messages in WeChat's contact list."""
        messages = []
        try:
            # Get all windows
            windows_result = self._osascript(
                'tell application "System Events" to get name of every window of process "WeChat"'
            )
            if not windows_result:
                return []

            # Get all UI elements to find contact list
            result = self._osascript(
                'tell application "System Events" to get name of every UI element of window 1 of process "WeChat"'
            )
            if result:
                elements = result.split(", ")
                # Look for list or scroll area
                for elem in elements:
                    if "列表" in elem or "List" in elem or "滚动" in elem:
                        # Try to get items from this list
                        list_result = self._osascript(
                            'tell application "System Events" to get name of every static text of UI element "' + elem + '" of window 1 of process "WeChat"'
                        )
                        if list_result:
                            items = list_result.split(", ")
                            for item in items[:20]:
                                if item.strip():
                                    messages.append({
                                        "contact_id": item.strip(),
                                        "display_name": item.strip(),
                                        "content": "",
                                        "message_type": "text",
                                        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                                        "is_unread": True,
                                    })
        except Exception as e:
            logger.debug("_scan_unread_messages failed: %s", e)

        return messages

    def get_recent_messages(self, contact_id: str, limit: int = 20) -> list[dict]:
        """Get recent messages for a contact."""
        if not self._ensure_ref():
            return []
        try:
            self.open_chat(contact_id)
            time.sleep(0.5)
            return self._scan_chat_messages(contact_id, limit)
        except Exception as e:
            logger.error("get_recent_messages failed: %s", e)
            return []

    def _scan_chat_messages(self, contact_id: str, limit: int = 20) -> list[dict]:
        """Scan current chat window for messages."""
        messages = []
        try:
            # Try to get text content from the chat window
            result = self._osascript(
                'tell application "System Events" to get value of text area 1 of window "' + contact_id + '" of process "WeChat"'
            )
            if result:
                lines = result.split("\n")
                for line in lines[-limit:]:
                    if line.strip():
                        messages.append({
                            "content": line.strip(),
                            "message_type": "text",
                            "is_sent": False,
                            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
                        })
        except Exception as e:
            logger.debug("_scan_chat_messages failed: %s", e)

        return messages

    # ── Navigation ────────────────────────────────────────────

    def open_chat(self, contact_id: str) -> bool:
        """Search for a contact and open their chat."""
        if not self._ensure_ref():
            return False
        try:
            # Click on search field
            self._osascript_click(
                'tell application "System Events" to click text field 1 of window 1 of process "WeChat"'
            )
            time.sleep(0.2)

            # Select all and delete
            self._osascript_command_a()
            time.sleep(0.1)
            self._osascript_delete()
            time.sleep(0.1)

            # Type contact name
            self._osascript_type(contact_id)
            time.sleep(0.3)

            # Press Enter to search
            self._osascript_enter()
            time.sleep(0.5)

            # Click first result
            self._osascript_click(
                'tell application "System Events" to click static text 1 of list 1 of window 1 of process "WeChat"'
            )
            time.sleep(0.5)
            return True
        except Exception as e:
            logger.error("open_chat failed: %s", e)
            return False

    # ── Message sending ───────────────────────────────────────

    def send_text(self, contact_id: str, message: str) -> bool:
        """Open chat and send a text message."""
        if not self._ensure_ref():
            return False
        try:
            self.open_chat(contact_id)
            time.sleep(0.3)

            # Click on message input field
            self._osascript_click(
                'tell application "System Events" to click text area 1 of window "' + contact_id + '" of process "WeChat"'
            )
            time.sleep(0.2)

            # Select all and delete existing text
            self._osascript_command_a()
            time.sleep(0.1)
            self._osascript_delete()
            time.sleep(0.1)

            # Type message
            self._osascript_type(message)
            time.sleep(0.1)

            # Press Enter to send
            self._osascript_enter()
            time.sleep(0.3)

            return True
        except Exception as e:
            logger.error("send_text failed: %s", e)
            return False

    # ── Contact list ──────────────────────────────────────────

    def get_contacts(self) -> list[dict]:
        """Get list of contacts from the sidebar."""
        if not self._ensure_ref():
            return []
        try:
            contacts = []
            result = self._osascript(
                'tell application "System Events" to get name of every static text of list 1 of scroll area 1 of window 1 of process "WeChat"'
            )
            if result:
                names = result.split(", ")
                for name in names[:50]:
                    if name.strip() and name.strip() not in contacts:
                        contacts.append({
                            "contact_id": name.strip(),
                            "display_name": name.strip(),
                        })
            return contacts
        except Exception as e:
            logger.error("get_contacts failed: %s", e)
            return []

    # ── Verification ──────────────────────────────────────────

    def verify_message_sent(self, contact_id: str, message: str) -> bool:
        """Verify the message appeared in the chat."""
        try:
            self.open_chat(contact_id)
            time.sleep(0.3)
            messages = self._scan_chat_messages(contact_id, 5)
            for msg in messages[:3]:
                if msg.get("content") == message:
                    return True
            return False
        except Exception as e:
            logger.error("verify_message_sent failed: %s", e)
            return False

    def __del__(self):
        self._wechat_pid = None
