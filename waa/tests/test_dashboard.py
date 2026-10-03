"""Tests for dashboard and integration components."""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.database import Database


def test_dashboard_routes():
    """Test that dashboard endpoints return expected data."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        db.init()

        # Insert test data
        cid = db.upsert_contact("wxid_test", "Test User")
        msg_id = db.insert_message(
            contact_id=cid, direction="incoming",
            content="hello", message_type="text",
            timestamp="2026-01-01T00:00:00", status="received",
        )
        db.insert_ai_reply(
            message_id=msg_id, response="Hi there!",
            model="gpt-4o-mini", latency_ms=320,
            status="success",
        )
        db.log_event("message_sent", "INFO", "contact=wxid_test", {})

        # Import and create dashboard
        from app.dashboard import Dashboard
        dash = Dashboard(db)
        app = dash.app

        # Test health endpoint
        from fastapi.testclient import TestClient
        client = TestClient(app)

        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert "status" in data
        assert "uptime_seconds" in data
        assert "services" in data
        assert "timestamp" in data

        # Test stats endpoint
        resp = client.get("/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "today_received" in data
        assert "today_replied" in data
        assert "today_blocked" in data
        assert "today_failed" in data

        # Test events endpoint
        resp = client.get("/events")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        # Test replies endpoint
        resp = client.get("/replies")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

        # Test HTML dashboard
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
        assert "WAA Dashboard" in resp.text

        db.close()
        print("  dashboard: PASS")


def test_worker_pipeline():
    """Test MessageWorker with mocked components."""
    from unittest.mock import MagicMock, patch
    from app.worker import MessageWorker

    adapter = MagicMock()
    adapter.health_check.return_value = True
    adapter.is_running.return_value = True
    adapter.send_text.return_value = True

    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        db = Database(db_path)
        db.init()

        cid = db.upsert_contact("wxid_test", "Test User")
        msg_id = db.insert_message(
            contact_id=cid, direction="incoming",
            content="你好", message_type="text",
            timestamp="2026-01-01T00:00:00", status="received",
        )

        throttle = MagicMock()
        throttle.can_reply.return_value = True
        throttle.get_cooldown_remaining.return_value = 0.0

        # Patch AIChatAgent to return a fixed reply
        with patch("app.worker.AIChatAgent") as MockAgent:
            mock_agent = MagicMock()
            mock_agent.generate_reply.return_value = "你好！有什么可以帮助你的？"
            MockAgent.return_value = mock_agent

            worker = MessageWorker(adapter, db, throttle, poll_interval=60.0)
            worker._process_one({"id": msg_id, "wx_id": "wxid_test", "content": "你好"})

            assert adapter.send_text.called
            send_args = adapter.send_text.call_args
            assert send_args[0][0] == "wxid_test"
            assert "你好" in send_args[0][1]

            # Verify DB status updated
            msg = db.get_message(msg_id)
            assert msg["status"] == "sent"

        db.close()
        print("  worker_pipeline: PASS")


if __name__ == "__main__":
    print("Running WAA dashboard & worker tests...")
    test_dashboard_routes()
    test_worker_pipeline()
    print("All tests passed!")
