#!/usr/bin/env bash
# Install WAA dependencies
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

echo "Installing dependencies..."
.venv/bin/pip install -r requirements.txt

echo ""
echo "Setup complete."
echo "Next steps:"
echo "  1. Grant Accessibility permission: System Settings → Privacy & Security → Accessibility"
echo "  2. Copy .env.example to .env and configure LLM_API_KEY"
echo "  3. Run: ./scripts/waa.py --health"
