#!/usr/bin/env bash
# Instala o cron para rodar o scraping automaticamente.
# Padrão: 8h, 14h e 20h todos os dias.
# Execute uma vez para configurar o agendamento.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SCRAPE_SCRIPT="$SCRIPT_DIR/scrape.sh"
LOG_FILE="$PROJECT_DIR/logs/scrape.log"

CRON_ENTRY="0 8,14,20 * * * $SCRAPE_SCRIPT >> $LOG_FILE 2>&1"

# Verifica se a entrada já existe
if crontab -l 2>/dev/null | grep -qF "$SCRAPE_SCRIPT"; then
    echo "Cron já configurado para $SCRAPE_SCRIPT"
    echo "Entrada atual:"
    crontab -l | grep "$SCRAPE_SCRIPT"
    exit 0
fi

# Adiciona a entrada ao crontab existente
(crontab -l 2>/dev/null; echo "$CRON_ENTRY") | crontab -

echo "Cron instalado com sucesso:"
echo "  $CRON_ENTRY"
echo ""
echo "O scraping rodará todos os dias às 8h, 14h e 20h."
echo "Logs em: $LOG_FILE"
echo ""
echo "Para remover, edite com: crontab -e"
