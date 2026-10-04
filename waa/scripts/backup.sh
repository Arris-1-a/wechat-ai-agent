#!/bin/bash
set -e
BACKUP_DIR="$HOME/.wechat-ai-agent/backups"
mkdir -p "$BACKUP_DIR"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
DB="$HOME/.wechat-ai-agent/data/waa.db"
cp "$DB" "$BACKUP_DIR/waa.db.$TIMESTAMP" 2>/dev/null && echo "  DB backup: OK" || echo "  DB backup: skipped"
echo "Backups in: $BACKUP_DIR"
ls -la "$BACKUP_DIR" 2>/dev/null | tail -5
