#!/bin/bash
set -e
echo "=== WAA Doctor ==="
python -c "import sys; print(f'Python: {sys.version}')"
python -c "import sqlite3; print(f'SQLite: OK ({sqlite3.sqlite_version})')"
python -c "import yaml; print(f'PyYAML: OK ({yaml.__version__})')" || echo "PyYAML: MISSING"
python -c "import fastapi; print(f'fastapi: OK ({fastapi.__version__})')" || echo "fastapi: MISSING"
python -c "import uvicorn; print(f'uvicorn: OK ({uvicorn.__version__})')" || echo "uvicorn: MISSING"
ps aux | grep -i "[w]echat" > /dev/null && echo "WeChat: RUNNING" || echo "WeChat: NOT RUNNING"
pgrep -f "waa.*main" > /dev/null 2>&1 && echo "WAA: RUNNING (pid=$(pgrep -f 'waa.*main' | head -1))" || echo "WAA: NOT RUNNING"
echo "=== Checks complete ==="
