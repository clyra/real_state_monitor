#!/usr/bin/env bash
# Instalação inicial do Real Estate Monitor.
# Execute uma vez após clonar o repositório.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

cd "$PROJECT_DIR"

echo "==> Criando virtualenv..."
if [ ! -d ".venv" ]; then
    python3 -m venv .venv
fi

echo "==> Ativando virtualenv..."
source .venv/bin/activate

echo "==> Instalando dependências..."
pip install -e ".[dev]" --quiet

echo "==> Instalando Chromium (Playwright)..."
playwright install chromium

echo "==> Configurando .env..."
if [ ! -f ".env" ]; then
    cp .env.example .env
    echo "    Arquivo .env criado. Edite-o e defina WEB_USER e WEB_PASSWORD antes de continuar."
else
    echo "    .env já existe, mantendo o existente."
fi

echo "==> Inicializando banco de dados..."
real-estate-monitor init-db

echo ""
echo "Setup concluído. Próximos passos:"
echo "  1. Edite .env e defina WEB_USER e WEB_PASSWORD"
echo "  2. Execute 'bash scripts/scrape.sh' para importar os imóveis"
echo "  3. Execute 'bash scripts/start-web.sh' para abrir a interface web"
