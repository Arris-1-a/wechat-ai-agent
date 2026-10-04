"""FastAPI dashboard with settings management API."""
from __future__ import annotations

import logging
import threading
import time
from datetime import datetime, timezone

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from app.config import settings
from app.database import Database
from app.logging_config import logger
from app.wechat import create_adapter

logger = logging.getLogger("waa.dashboard")


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


class SettingsUpdate(BaseModel):
    auto_reply_enabled: bool | None = None
    safe_mode: bool | None = None
    high_risk_mode: str | None = None
    reply_min_delay: int | None = None
    reply_max_delay: int | None = None
    max_reply_length: int | None = None


class PersonaUpdate(BaseModel):
    name: str | None = None
    personality: str | None = None
    tone: str | None = None
    language: str | None = None
    rules: list[str] | None = None
    blacklist_topics: list[str] | None = None
    max_reply_chars: int | None = None


class Dashboard:
    """FastAPI dashboard for WAA."""

    def __init__(self, db: Database):
        self._db = db
        self._app = FastAPI(title="WAA Dashboard", version="0.2.0")
        self._start_time = time.time()
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
            except Exception:
                services["wechat"] = "unavailable"
                services["wechat_running"] = "unknown"

            from app.state import state
            return HealthResponse(
                status="healthy" if state.agent_running and state.auto_reply_enabled else "degraded",
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
            return [EventItem(**e) for e in self._db.get_recent_events(limit=limit)]

        @app.get("/contacts")
        async def get_contacts():
            return self._db.list_contacts()

        @app.get("/replies")
        async def get_replies(limit: int = 100):
            return self._db.get_ai_replies(limit=limit)

        @app.get("/settings")
        async def get_settings():
            from app.state import state
            return {
                "auto_reply_enabled": state.auto_reply_enabled,
                "safe_mode": state.safe_mode,
                "high_risk_mode": settings.high_risk_mode,
                "reply_min_delay": settings.reply_min_delay,
                "reply_max_delay": settings.reply_max_delay,
                "max_reply_length": settings.max_reply_length,
            }

        @app.post("/settings")
        async def update_settings(body: SettingsUpdate):
            from app.state import state
            updated = {}
            if body.auto_reply_enabled is not None:
                state.auto_reply_enabled = body.auto_reply_enabled
                updated["auto_reply_enabled"] = state.auto_reply_enabled
            if body.safe_mode is not None:
                state.safe_mode = body.safe_mode
                updated["safe_mode"] = state.safe_mode
            if body.high_risk_mode is not None:
                settings.high_risk_mode = body.high_risk_mode
                updated["high_risk_mode"] = settings.high_risk_mode
            self._db.log_event("settings_updated", "INFO", f"Updated: {list(updated.keys())}")
            return {"status": "ok", "updated": updated}

        @app.get("/persona")
        async def get_persona():
            return settings.persona.to_dict()

        @app.put("/persona")
        async def update_persona(body: PersonaUpdate):
            updates = body.model_dump(exclude_none=True)
            if updates:
                settings.persona.update(updates)
                self._db.log_event("persona_updated", "INFO", "Persona updated")
                return {"status": "ok", "version": settings.persona.save_version()}
            return {"status": "ok", "data": settings.persona.to_dict()}

        @app.get("/system-state")
        async def system_state():
            from app.state import state
            return {
                "agent_running": state.agent_running,
                "auto_reply_enabled": state.auto_reply_enabled,
                "safe_mode": state.safe_mode,
                "wechat_status": state.wechat_status,
                "ai_status": state.ai_status,
            }

        @app.post("/emergency-stop")
        async def emergency_stop():
            from app.state import state
            state.emergency_stop()
            self._db.log_event("emergency_stop", "WARNING", "Emergency stop activated")
            return {"status": "ok", "message": "Auto-reply disabled"}

        @app.get("/", response_class=HTMLResponse)
        async def dashboard_html():
            return _HTML_PAGE

    @property
    def app(self) -> FastAPI:
        return self._app

    def start_server(self) -> None:
        import uvicorn
        config = uvicorn.Config(
            self._app,
            host=settings.dashboard_host,
            port=settings.dashboard_port,
            log_level="warning",
        )
        server = uvicorn.Server(config)
        thread = threading.Thread(target=server.run, daemon=True, name="dashboard")
        thread.start()
        logger.info("Dashboard started on %s:%d", settings.dashboard_host, settings.dashboard_port)


_HTML_PAGE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>WAA Dashboard</title>
<style>
  * { margin: 0; padding: 0; box-sizing: border-box; }
  body { font-family: -apple-system, BlinkMacSystemFont, sans-serif; background: #0a0a0a; color: #e0e0e0; padding: 24px; }
  h1 { font-size: 22px; color: #b48c3c; margin-bottom: 20px; }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; margin-bottom: 24px; }
  .card { background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 12px; padding: 20px; }
  .card h2 { font-size: 13px; color: #888; text-transform: uppercase; margin-bottom: 12px; }
  .row { display: flex; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #222; font-size: 14px; }
  .label { color: #888; }
  .value { font-weight: 500; }
  .ok { color: #4ade80; }
  .warn { color: #fbbf24; }
  .err { color: #f87171; }
  .event { padding: 8px 0; border-bottom: 1px solid #222; font-size: 13px; }
  .severity { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 11px; margin-right: 8px; }
  .sev-info { background: #1e3a5f; color: #60a5fa; }
  .sev-warn { background: #5c3a1e; color: #fbbf24; }
  .sev-error { background: #5c1e1e; color: #f87171; }
  #uptime { color: #666; font-size: 12px; margin-bottom: 20px; }
  .refresh-btn { background: #b48c3c; color: #000; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; margin-right: 8px; }
  .stop-btn { background: #dc2626; color: #fff; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-weight: 600; }
  .toggle { display: flex; align-items: center; gap: 8px; }
</style>
</head>
<body>
<h1>WAA — WeChat AI Auto Reply Agent</h1>
<div id="uptime">Loading...</div>
<div class="grid">
  <div class="card">
    <h2>System State</h2>
    <div id="system-state"></div>
  </div>
  <div class="card">
    <h2>Today's Stats</h2>
    <div id="stats"></div>
  </div>
  <div class="card">
    <h2>Controls</h2>
    <div id="controls"></div>
  </div>
</div>
<div class="grid">
  <div class="card">
    <h2>Services</h2>
    <div id="services"></div>
  </div>
  <div class="card">
    <h2>Recent Events</h2>
    <div id="events"></div>
  </div>
</div>
<button class="refresh-btn" onclick="loadData()">Refresh</button>
<button class="stop-btn" onclick="emergencyStop()">Emergency Stop</button>
<script>
async function api(path, opts) { const r = await fetch(path, opts || {}); return r.json(); }
async function loadData() {
  const [health, stats, events, sysState] = await Promise.all([
    api('/health'), api('/stats'), api('/events?limit=8'), api('/system-state')
  ]);
  document.getElementById('uptime').textContent =
    'Uptime: ' + Math.floor(health.uptime_seconds) + 's · ' + health.timestamp;
  document.getElementById('system-state').innerHTML = [
    ['Agent', sysState.agent_running ? 'RUNNING' : 'STOPPED'],
    ['Auto Reply', sysState.auto_reply_enabled ? 'ENABLED' : 'DISABLED'],
    ['Safe Mode', sysState.safe_mode ? 'ON' : 'OFF'],
    ['WeChat', sysState.wechat_status || 'unknown'],
    ['AI', sysState.ai_status || 'unknown'],
  ].map(([l,v]) => '<div class="row"><span class="label">'+l+'</span><span class="value '+(v==='RUNNING'||v==='ENABLED'?'ok':v==='STOPPED'||v==='DISABLED'?'err':'warn')+'">'+v+'</span></div>').join('');
  document.getElementById('stats').innerHTML = [
    ['Received', stats.today_received], ['Replied', stats.today_replied],
    ['Blocked', stats.today_blocked], ['Failed', stats.today_failed],
  ].map(([l,v]) => '<div class="row"><span class="label">'+l+'</span><span class="value">'+v+'</span></div>').join('');
  document.getElementById('controls').innerHTML =
    '<div class="toggle"><label>Auto Reply</label><input type="checkbox" '+ (sysState.auto_reply_enabled?'checked':'') +' onchange="toggleSetting(\'auto_reply_enabled\',this.checked)"></div>' +
    '<div class="toggle"><label>Safe Mode</label><input type="checkbox" '+ (sysState.safe_mode?'checked':'') +' onchange="toggleSetting(\'safe_mode\',this.checked)"></div>';
  document.getElementById('services').innerHTML = Object.entries(health.services).map(([k,v]) =>
    '<div class="row"><span class="label">'+k+'</span><span class="value '+(v==='healthy'?'ok':v==='unhealthy'?'err':'warn')+'">'+v+'</span></div>'
  ).join('') || '<div style="color:#555">No services</div>';
  document.getElementById('events').innerHTML = events.map(e => {
    const cls = e.severity==='WARNING'?'sev-warn':e.severity==='ERROR'?'sev-error':'sev-info';
    return '<div class="event"><span class="severity '+cls+'">'+e.severity+'</span>'+e.message+'</div>';
  }).join('') || '<div style="color:#555">No events</div>';
}
async function toggleSetting(key, value) {
  await api('/settings', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({[key]: value})});
  loadData();
}
async function emergencyStop() {
  if (!confirm('Activate emergency stop?')) return;
  await api('/emergency-stop', {method:'POST'});
  loadData();
}
loadData();
setInterval(loadData, 10000);
</script>
</body>
</html>"""
