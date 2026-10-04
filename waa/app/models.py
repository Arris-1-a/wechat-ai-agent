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
    QUEUED = "queued"
    AI_GENERATED = "ai_generated"
    SAFETY_CHECKED = "safety_checked"
    READY_TO_SEND = "ready_to_send"
    PROCESSED = "processed"
    FAILED = "failed"
    IGNORED = "ignored"
    SENDING = "sending"
    SENT = "sent"
    SEND_UNKNOWN = "send_unknown"
    BLOCKED = "blocked"
    HUMAN_REQUIRED = "human_required"


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


class SystemState(str, Enum):
    BOOTING = "booting"
    CHECKING = "checking"
    WAITING_WECHAT = "waiting_wechat"
    WECHAT_READY = "wechat_ready"
    AI_READY = "ai_ready"
    RUNNING = "running"
    DEGRADED = "degraded"
    RECOVERING = "recovering"
    STOPPED = "stopped"
    ERROR = "error"


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
    confidence: float = 0.0


@dataclass
class SystemEvent:
    """System event for monitoring."""
    event_type: str
    severity: EventSeverity
    message: str
    metadata: dict = field(default_factory=dict)
