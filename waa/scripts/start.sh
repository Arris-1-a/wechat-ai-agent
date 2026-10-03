#!/usr/bin/env bash
# Start WAA agent
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ ! -f ".venv/bin/python3" ]; then
    echo "Error: .venv not found. Run ./scripts/install.sh first."
    exit 1
fi

exec .venv/bin/python3 -m app.main "$@"
