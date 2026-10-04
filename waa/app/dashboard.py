"""FastAPI dashboard for WAA monitoring."""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from typing import Any, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.database import Database
from app.logging_config import logger
from app.wechat import create_adapter

logger = logging.getLogger("waa.dashboard")


# ── Request/Response Models ─────────────────────────────────────────────────

class HealthResponse(BaseModel):
    status: str
    uptime_seconds: float
    services: dict[str, str]
    timestamp: str


class StatsResponse(BaseModel):
    today_received: int
    today_replied: int
    today_blocked: int
    today_failed: int
    total_contacts: int
    total_messages: int


class EventItem(BaseModel):
    event_type: str
    severity: str
    message: str
    created_at: str


class ChatItem(BaseModel):
    contact_id: str
    display_name: str
    last_message: Optional[str] = None
    message_count: int = 0


class ReplyItem(BaseModel):
    contact_id: str
    display_name: str
    original_message: str
    ai_reply: str
    model: str
    latency_ms: Optional[int] = None
    created_at: str


# ── Dashboard App ─────────────────────────────────────────────────────────────

class Dashboard:
    """FastAPI dashboard for WAA."""

    def __init__(self, db: Database):
        self._db = db
        self._app = FastAPI(title="WAA Dashboard", version="0.1.0")
        self._start_time = time.time()
        self._lock = threading.Lock()
        self._register_routes()

    def _register_routes(self) -> None:
        app = self._app

        @app.get("/health", response_model=HealthResponse)
        async def health():
            services = {}
            try:
                adapter = create_adapter()
                services["wechat"] = "healthy" if adapter.health_check() else "unhealthy"
                services["wechat_running"] = "yes" if adapter.is_running() else "no"
            except NotImplementedError:
                services["wechat"] = "unavailable"
                services["wechat_running"] = "unknown"
            except Exception:
                services["wechat"] = "error"
                services["wechat_running"] = "unknown"

            try:
                heartbeats = self._db.get_heartbeats()
                for svc, data in heartbeats.items():
                    status = data.get("status", "unknown")
                    if status not in services:
                        services[svc] = status
            except Exception:
                pass

            return HealthResponse(
                status="healthy" if all(v == "healthy" for v in services.values() if v in ("healthy", "unhealthy")) else "degraded",
                uptime_seconds=time.time() - self._start_time,
                services=services,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )

        @app.get("/stats", response_model=StatsResponse)
        async def stats():
            today = self._db.get_today_stats()
            return StatsResponse(
                today_received=today.get("received", 0),
                today_replied=today.get("replied", 0),
                today_blocked=today.get("blocked", 0),
                today_failed=today.get("failed", 0),
                total_contacts=len(self._db.list_contacts()),
                total_messages=sum(today.values()),
            )

        @app.get("/events", response_model=list[EventItem])
        async def events(limit: int = 50):
            evts = self._db.get_recent_events(limit=limit)
            return [EventItem(**e) for e in evts]

        @app.get("/contacts", response_model=list[ChatItem])
        async def contacts():
            contact_list = self._db.list_contacts(enabled_only=False)
            result = []
            for c in contact_list:
                cid = c["id"]
                wx_id = c.get("wx_id", "")
                name = c.get("display_name", "")
                recent = self._db.get_recent_messages(cid, limit=1)
                last_msg = recent[0]["content"][:80] if recent else None
                msg_count = self._db.get_today_stats()
                result.append(ChatItem(
                    contact_id=wx_id,
                    display_name=name,
                    last_message=last_msg,
                    message_count=0,
                ))
            return result

        @app.get("/replies", response_model=list[ReplyItem])
        async def replies(limit: int = 20):
            conn = self._db._get_conn()
            rows = conn.execute("""
                SELECT r.id, r.model, r.latency_ms, r.response, r.status, r.created_at,
                       m.content as original, m.direction,
                       c.wx_id, c.display_name
                FROM ai_replies r
                JOIN messages m ON m.id = r.message_id
                JOIN contacts c ON c.id = m.contact_id
                ORDER BY r.created_at DESC
                LIMIT ?
            """, (limit,)).fetchall()
            return [ReplyItem(
                contact_id=r["wx_id"],
                display_name=r["display_name"],
                original_message=r["original"] or "",
                ai_reply=r["response"] or "",
                model=r["model"] or "unknown",
                latency_ms=r["latency_ms"],
                created_at=r["created_at"],
            ) for r in rows]

        @app.get("/", response_class=HTMLResponse)
        async def dashboard_html():
            return _HTML_PAGE

    @property
    def app(self) -> FastAPI:
        return self._app

    def start_server(self) -> None:
        """Start the dashboard server in a background thread."""
        import uvicorn
        config = uvicorn.Config(
            self._app,
            host=settings.dashboard_host,
            port=settings.dashboard_port,
            log_level="warning",
            loop="asyncio",
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True, name="dashboard")
        thread.start()
        logger.info("Dashboard started on http://%s:%d", settings.dashboard_host, settings.dashboard_port)


# ── HTML Dashboard Page ───────────────────────────────────────────────────────

_HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WAA Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0a0a0a; color: #e0e0e0; padding: 24px; }
  h1 { font-size: 22px; font-weight: 600; color: #b48c3c; margin-bottom: 20px; letter-spacing: 0.05em; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; padding: 20px; }
  .card h2 { font-size: 13px; color: #888; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 12px; }
  .stat { font-size: 36px; font-weight: 700; color: #b48c3c; }
  .stat.small { font-size: 24px; }
  .row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #222; font-size: 14px; }
  .row:last-child { border-bottom: none; }
  .label { color: #888; }
  .value { color: #e0e0e0; font-weight: 500; }
  .ok { color: #4ade80; }
  .warn { color: #fbbf24; }
  .err { color: #f87171; }
  .event { padding: 8px 0; border-bottom: 1px solid #222; font-size: 13px; }
  .event:last-child { border-bottom: none; }
  .severity { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; font-weight: 600; margin-right: 8px; }
  .sev-info { background: #1e3a5f; color: #60a5fa; }
  .sev-warn { background: #5c3a1e; color: #fbbf24; }
  .sev-error { background: #5c1e1e; color: #f87171; }
  .reply { background: #111; border-radius: 8px; padding: 12px; margin-bottom: 10px; font-size: 13px; }
  .reply .contact { color: #b48c3c; font-weight: 600; margin-bottom: 4px; }
  .reply .msg { color: #ccc; margin-bottom: 4px; }
  .reply .reply-text { color: #4ade80; }
  .reply .meta { color: #666; font-size: 11px; margin-top: 4px; }
  #uptime { color: #666; font-size: 12px; margin-bottom: 20px; }
  .refresh-btn { background: #b48c3c; color: #000; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 13px; font-weight: 600; }
  .refresh-btn:hover { background: #d4a843; }
</style>
</head>
<body>
<h1>WAA — WeChat AI Auto Reply Agent</h1>
<div id="uptime">Loading...</div>
<div class="grid">
  <div class="card">
    <h2>Services</h2>
    <div id="services"></div>
  </div>
  <div class="card">
    <h2>Today's Stats</h2>
    <div id="stats"></div>
  </div>
  <div class="card">
    <h2>Recent Events</h2>
    <div id="events"></div>
  </div>
</div>
<div class="grid">
  <div class="card" style="grid-column: span 2;">
    <h2>Recent Replies</h2>
    <div id="replies"></div>
  </div>
</div>
<button class="refresh-btn" onclick="loadData()">Refresh</button>
<script>
async function api(path) { const r = await fetch(path); return r.json(); }
async function loadData() {
  try {
    const [health, stats, events, replies] = await Promise.all([
      api('/health'), api('/stats'), api('/events?limit=8'), api('/replies?limit=5')
    ]);
    document.getElementById('uptime').textContent =
      'Uptime: ' + Math.floor(health.uptime_seconds) + 's · ' + health.timestamp;
    const svcEl = document.getElementById('services');
    svcEl.innerHTML = Object.entries(health.services).map(([k,v]) => {
      const cls = v === 'healthy' ? 'ok' : v === 'unhealthy' ? 'err' : 'warn';
      return '<div class="row"><span class="label">' + k + '</span><span class="value ' + cls + '">' + v + '</span></div>';
    }).join('');
    const stEl = document.getElementById('stats');
    stEl.innerHTML = [
      ['Received', stats.today_received], ['Replied', stats.today_replied],
      ['Blocked', stats.today_blocked], ['Failed', stats.today_failed],
      ['Contacts', stats.total_contacts],
    ].map(([l,v]) => '<div class="row"><span class="label">' + l + '</span><span class="value">' + v + '</span></div>').join('');
    const evEl = document.getElementById('events');
    evEl.innerHTML = events.map(e => {
      const sevCls = e.severity === 'WARNING' ? 'sev-warn' : e.severity === 'ERROR' ? 'sev-error' : 'sev-info';
      return '<div class="event"><span class="severity ' + sevCls + '">' + e.severity + '</span>' + e.message + '<br><span style="color:#555;font-size:11px">' + e.created_at + '</span></div>';
    }).join('') || '<div style="color:#555">No events</div>';
    const rpEl = document.getElementById('replies');
    rpEl.innerHTML = replies.map(r => '<div class="reply"><div class="contact">' + r.display_name + ' (' + r.contact_id + ')</div><div class="msg">→ ' + (r.original_message || '?') + '</div><div class="reply-text">↩ ' + (r.ai_reply || '(no reply)') + '</div><div class="meta">' + r.model + (r.latency_ms ? ' · ' + r.latency_ms + 'ms' : '') + '</div></div>').join('') || '<div style="color:#555">No replies yet</div>';
  } catch(e) { console.error(e); }
}
loadData();
setInterval(loadData, 10000);
</script>
</body>
</html>"""
