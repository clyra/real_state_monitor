#!/usr/bin/env bash
# Inicia o servidor web do Real Estate Monitor.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

source .venv/bin/activate

PORT="${WEB_PORT:-5000}"
echo "Iniciando servidor em http://localhost:${PORT}"
echo "Use Ctrl+C para parar."

python -m real_estate_monitor.web
