#!/bin/bash
echo "=== WAA Status ==="
if pgrep -f "waa.*main" > /dev/null 2>&1; then
    PID=$(pgrep -f "waa.*main" | head -1)
    echo "WAA: RUNNING (pid $PID)"
    echo "Dashboard: http://127.0.0.1:8765"
else
    echo "WAA: NOT RUNNING"
fi
echo ""
curl -s http://127.0.0.1:8765/health 2>/dev/null | python -m json.tool 2>/dev/null || echo "  Dashboard unreachable"
echo ""
tail -n 20 "$HOME/.wechat-ai-agent/logs/waa_$(date +%Y-%m-%d).log" 2>/dev/null || echo "  No log file for today"
