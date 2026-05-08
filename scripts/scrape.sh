#!/usr/bin/env bash
# Roda o scraping de todas as fontes habilitadas e detecta duplicatas.
# Adequado para execução manual ou via cron.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

source .venv/bin/activate

mkdir -p logs

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Iniciando scraping..."

real-estate-monitor run-all

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Detectando duplicatas..."

real-estate-monitor find-duplicates

echo "[$(date '+%Y-%m-%d %H:%M:%S')] Concluído."
