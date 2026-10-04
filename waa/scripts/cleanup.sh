#!/bin/bash
set -e
echo "Cleaning up WAA..."
find "$HOME/.wechat-ai-agent/logs" -name "waa_*.log" -mtime +7 -delete 2>/dev/null && echo "  Old logs cleaned"
echo "Cleanup complete."
