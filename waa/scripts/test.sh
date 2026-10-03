#!/usr/bin/env bash
# Run WAA tests
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ ! -f ".venv/bin/python3" ]; then
    echo "Error: .venv not found. Run ./scripts/install.sh first."
    exit 1
fi

echo "Running WAA tests..."
.venv/bin/python -m pytest waa/tests/ -v --tb=short
