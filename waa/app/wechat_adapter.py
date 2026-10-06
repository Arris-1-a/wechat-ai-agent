"""WeChat adapter interface — abstract base."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional


class WeChatAdapter(ABC):
    """Abstract adapter for WeChat automation."""

    @abstractmethod
    def health_check(self) -> bool:
        """Return True if WeChat is healthy and accessible."""
        ...

    @abstractmethod
    def is_running(self) -> bool:
        """Check if WeChat process is running."""
        ...

    @abstractmethod
    def is_logged_in(self) -> bool:
        """Check if user is logged into WeChat."""
        ...

    @abstractmethod
    def get_unread_messages(self) -> list[dict]:
        """Return list of unread message dicts."""
        ...

    @abstractmethod
    def get_recent_messages(
        self, contact_id: str, limit: int = 20
    ) -> list[dict]:
        """Return recent messages for a contact."""
        ...

    @abstractmethod
    def open_chat(self, contact_id: str) -> bool:
        """Open chat window for a contact."""
        ...

    @abstractmethod
    def send_text(self, contact_id: str, message: str) -> bool:
        """Send a text message. Returns True on success."""
        ...

    @abstractmethod
    def get_contacts(self) -> list[dict]:
        """Return list of contacts."""
        ...

    @abstractmethod
    def verify_message_sent(
        self, contact_id: str, message: str
    ) -> bool:
        """Verify the message was actually sent."""
        ...


class WeChatAdapterNotAvailableError(Exception):
    """Raised when no compatible adapter is available."""


class NotImplementedAdapter(WeChatAdapter):
    """Placeholder adapter — raises NotImplementedError on all calls."""

    def _raise(self, method: str) -> None:
        raise NotImplementedError(
            f"WeChat adapter not available: {method} requires Accessibility permission."
            " Grant Accessibility permission in System Settings → Privacy & Security → Accessibility,"
            " then restart the agent."
        )

    def health_check(self) -> bool:
        self._raise("health_check")

    def is_running(self) -> bool:
        return False

    def is_logged_in(self) -> bool:
        self._raise("is_logged_in")

    def get_unread_messages(self) -> list[dict]:
        self._raise("get_unread_messages")

    def get_recent_messages(self, contact_id: str, limit: int = 20) -> list[dict]:
        self._raise("get_recent_messages")

    def open_chat(self, contact_id: str) -> bool:
        self._raise("open_chat")

    def send_text(self, contact_id: str, message: str) -> bool:
        self._raise("send_text")

    def get_contacts(self) -> list[dict]:
        self._raise("get_contacts")

    def verify_message_sent(self, contact_id: str, message: str) -> bool:
        self._raise("verify_message_sent")


# Factory — returns real adapter; health check will validate accessibility
def create_adapter() -> WeChatAdapter:
    from app.wechat.accessibility_adapter import AccessibilityAdapter
    return AccessibilityAdapter()
