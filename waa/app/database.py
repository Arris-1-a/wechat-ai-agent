"""SQLite database layer."""
from __future__ import annotations

import json
import sqlite3
import threading
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from app.models import Direction, MessageStatus
from app.logging_config import logger

_SCHEMA = """
CREATE TABLE IF NOT EXISTS contacts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wx_id TEXT UNIQUE,
    display_name TEXT,
    enabled INTEGER DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    wx_message_id TEXT UNIQUE,
    contact_id INTEGER NOT NULL,
    direction TEXT NOT NULL,
    content TEXT,
    message_type TEXT,
    timestamp TEXT NOT NULL,
    status TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY(contact_id) REFERENCES contacts(id)
);

CREATE TABLE IF NOT EXISTS ai_replies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    message_id INTEGER NOT NULL,
    prompt_hash TEXT,
    response TEXT,
    model TEXT,
    latency_ms INTEGER,
    status TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY(message_id) REFERENCES messages(id)
);

CREATE TABLE IF NOT EXISTS conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    contact_id INTEGER UNIQUE,
    summary TEXT,
    last_message_at TEXT,
    updated_at TEXT NOT NULL,
    FOREIGN KEY(contact_id) REFERENCES contacts(id)
);

CREATE TABLE IF NOT EXISTS system_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT,
    severity TEXT,
    message TEXT,
    metadata TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS heartbeats (
    service TEXT PRIMARY KEY,
    status TEXT,
    last_seen TEXT,
    metadata TEXT
);

CREATE INDEX IF NOT EXISTS idx_messages_contact ON messages(contact_id, timestamp DESC);
CREATE INDEX IF NOT EXISTS idx_messages_wxid ON messages(wx_message_id);
CREATE INDEX IF NOT EXISTS idx_messages_status ON messages(status);
CREATE INDEX IF NOT EXISTS idx_ai_replies_msg ON ai_replies(message_id);
"""


class Database:
    """SQLite database with connection pooling per thread."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self._local = threading.local()

    def _get_conn(self) -> sqlite3.Connection:
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self.db_path.parent.mkdir(parents=True, exist_ok=True)
            conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
            conn.row_factory = sqlite3.Row
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            self._local.conn = conn
        return self._local.conn

    @contextmanager
    def transaction(self):
        conn = self._get_conn()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def init(self) -> None:
        conn = self._get_conn()
        conn.executescript(_SCHEMA)
        logger.info("Database initialized at %s", self.db_path)

    # ── Contacts ──────────────────────────────────────────────

    def upsert_contact(self, wx_id: str, display_name: str) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO contacts (wx_id, display_name, created_at, updated_at)"
                " VALUES (?, ?, ?, ?)"
                " ON CONFLICT(wx_id) DO UPDATE SET display_name=excluded.display_name, updated_at=excluded.updated_at",
                (wx_id, display_name, now, now),
            )
            row = conn.execute("SELECT id FROM contacts WHERE wx_id = ?", (wx_id,)).fetchone()
            return row[0]

    def get_contact(self, wx_id: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM contacts WHERE wx_id = ?", (wx_id,)
        ).fetchone()
        return dict(row) if row else None

    def list_contacts(self, enabled_only: bool = True) -> list[dict]:
        conn = self._get_conn()
        if enabled_only:
            rows = conn.execute("SELECT * FROM contacts WHERE enabled = 1 ORDER BY display_name").fetchall()
        else:
            rows = conn.execute("SELECT * FROM contacts ORDER BY display_name").fetchall()
        return [dict(r) for r in rows]

    # ── Messages ──────────────────────────────────────────────

    def insert_message(
        self,
        contact_id: int,
        direction: str,
        content: str,
        message_type: str,
        timestamp: str,
        wx_message_id: Optional[str] = None,
        status: str = MessageStatus.RECEIVED,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO messages
                   (wx_message_id, contact_id, direction, content, message_type, timestamp, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (wx_message_id, contact_id, direction, content, message_type, timestamp, status, now),
            )
            msg_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        return msg_id

    def get_message(self, message_id: int) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute("SELECT * FROM messages WHERE id = ?", (message_id,)).fetchone()
        return dict(row) if row else None

    def get_message_by_wx_id(self, wx_message_id: str) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM messages WHERE wx_message_id = ?", (wx_message_id,)
        ).fetchone()
        return dict(row) if row else None

    def message_exists(self, wx_message_id: str) -> bool:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT 1 FROM messages WHERE wx_message_id = ?", (wx_message_id,)
        ).fetchone()
        return row is not None

    def update_message_status(self, message_id: int, status: str) -> None:
        with self.transaction() as conn:
            conn.execute(
                "UPDATE messages SET status = ? WHERE id = ?", (status, message_id)
            )

    def get_pending_messages(self, limit: int = 100) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT m.*, c.display_name, c.wx_id
               FROM messages m
               LEFT JOIN contacts c ON c.id = m.contact_id
               WHERE m.status IN ('received', 'processing')
               ORDER BY m.timestamp ASC
               LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_recent_messages(self, contact_id: int, limit: int = 20) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM messages WHERE contact_id = ? ORDER BY timestamp DESC LIMIT ?",
            (contact_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_unsent_messages(self) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            """SELECT m.*, c.display_name, c.wx_id
               FROM messages m
               LEFT JOIN contacts c ON c.id = m.contact_id
               WHERE m.status IN ('processing', 'sending')
               ORDER BY m.timestamp ASC""",
        ).fetchall()
        return [dict(r) for r in rows]

    # ── AI Replies ────────────────────────────────────────────

    def insert_ai_reply(
        self,
        message_id: int,
        response: str,
        model: str,
        latency_ms: int,
        status: str,
        prompt_hash: Optional[str] = None,
    ) -> int:
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO ai_replies
                   (message_id, prompt_hash, response, model, latency_ms, status, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (message_id, prompt_hash, response, model, latency_ms, status, now),
            )
            return conn.execute("SELECT last_insert_rowid()").fetchone()[0]

    def get_ai_replies(self, limit: int = 100) -> list[dict]:
        """Get recent AI replies with contact info."""
        with self._get_conn() as conn:
            rows = conn.execute("""
                SELECT ar.id, ar.message_id, ar.response as ai_reply, ar.model, ar.latency_ms,
                       ar.status, ar.created_at,
                       m.contact_id, m.content, c.display_name
                FROM ai_replies ar
                JOIN messages m ON ar.message_id = m.id
                JOIN contacts c ON m.contact_id = c.id
                ORDER BY ar.created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
        return [dict(r) for r in rows]

    # ── Conversations ─────────────────────────────────────────

    def upsert_conversation(
        self,
        contact_id: int,
        summary: Optional[str] = None,
        last_message_at: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO conversations (contact_id, summary, last_message_at, updated_at)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(contact_id) DO UPDATE SET
                     summary=excluded.summary,
                     last_message_at=excluded.last_message_at,
                     updated_at=excluded.updated_at""",
                (contact_id, summary, last_message_at or now, now),
            )

    def get_conversation(self, contact_id: int) -> Optional[dict]:
        conn = self._get_conn()
        row = conn.execute(
            "SELECT * FROM conversations WHERE contact_id = ?", (contact_id,)
        ).fetchone()
        return dict(row) if row else None

    # ── System Events ─────────────────────────────────────────

    def log_event(self, event_type: str, severity: str, message: str, metadata: Optional[dict] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            conn.execute(
                "INSERT INTO system_events (event_type, severity, message, metadata, created_at)"
                " VALUES (?, ?, ?, ?, ?)",
                (event_type, severity, message, json.dumps(metadata or {}), now),
            )

    def get_recent_events(self, limit: int = 50) -> list[dict]:
        conn = self._get_conn()
        rows = conn.execute(
            "SELECT * FROM system_events ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(r) for r in rows]

    # ── Heartbeats ────────────────────────────────────────────

    def update_heartbeat(self, service: str, status: str, metadata: Optional[dict] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO heartbeats (service, status, last_seen, metadata)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(service) DO UPDATE SET
                     status=excluded.status,
                     last_seen=excluded.last_seen,
                     metadata=excluded.metadata""",
                (service, status, now, json.dumps(metadata or {})),
            )

    def get_heartbeats(self) -> dict[str, dict]:
        conn = self._get_conn()
        rows = conn.execute("SELECT * FROM heartbeats").fetchall()
        return {r["service"]: dict(r) for r in rows}

    # ── Statistics ────────────────────────────────────────────

    def get_today_stats(self) -> dict:
        conn = self._get_conn()
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats = {}
        for label, condition in [
            ("received", f"direction='incoming' AND date(created_at) = '{today}'"),
            ("replied", f"direction='incoming' AND status IN ('processed', 'sent') AND date(created_at) = '{today}'"),
            ("blocked", f"direction='incoming' AND status = 'ignored' AND date(created_at) = '{today}'"),
            ("failed", f"direction='incoming' AND status = 'failed' AND date(created_at) = '{today}'"),
        ]:
            row = conn.execute(f"SELECT COUNT(*) FROM messages WHERE {condition}").fetchone()
            stats[label] = row[0]
        return stats

    def close(self) -> None:
        if hasattr(self._local, "conn") and self._local.conn:
            self._local.conn.close()
            self._local.conn = None
