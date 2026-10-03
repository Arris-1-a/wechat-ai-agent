#!/usr/bin/env bash
# Stop WAA agent (kill by PID file)
set -euo pipefail

PID_FILE="$(dirname "$0")/../data/waa.pid"

if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
        kill "$PID"
        echo "WAA stopped (PID $PID)"
    else
        echo "WAA not running (stale PID file)"
    fi
    rm -f "$PID_FILE"
else
    echo "No PID file found. WAA may not be running."
fi
