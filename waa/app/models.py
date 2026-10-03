"""Message pipeline models."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class Direction(str, Enum):
    INCOMING = "incoming"
    OUTGOING = "outgoing"


class MessageStatus(str, Enum):
    RECEIVED = "received"
    PROCESSING = "processing"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"
    SENDING = "sending"
    SENT = "sent"
    SEND_UNKNOWN = "send_unknown"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AiAction(str, Enum):
    REPLY = "reply"
    HOLD = "hold"
    BLOCK = "block"


class EventSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class WeChatMessage:
    """Raw message from WeChat adapter."""
    contact_id: str
    content: str
    message_type: str = "text"
    timestamp: Optional[datetime] = None
    wx_message_id: Optional[str] = None

    @property
    def dedup_key(self) -> str:
        ts = self.timestamp.isoformat() if self.timestamp else ""
        return f"{self.contact_id}|{ts}|{self.content}|{self.message_type}"


@dataclass
class AiResponse:
    """Structured AI response."""
    action: AiAction
    reply: Optional[str] = None
    risk: RiskLevel = RiskLevel.LOW
    reason: str = ""


@dataclass
class SystemEvent:
    """System event for monitoring."""
    event_type: str
    severity: EventSeverity
    message: str
    metadata: dict = field(default_factory=dict)
