# Real Estate Monitor

Sistema de monitoramento de anúncios de aluguel de imóveis. Raspa múltiplas imobiliárias, detecta novos anúncios, alterações de preço e remoções, e exibe tudo em uma interface web local.

## Índice

- [Pré-requisitos](#pré-requisitos)
- [Instalação](#instalação)
- [Configuração](#configuração)
- [Banco de dados](#banco-de-dados)
- [Scraping](#scraping)
- [Interface web](#interface-web)
- [Referência de comandos](#referência-de-comandos)
- [Agendamento automático](#agendamento-automático)
- [Adicionar novas fontes](#adicionar-novas-fontes)
- [Testes](#testes)

---

## Pré-requisitos

- Python 3.12+
- pip

---

## Instalação

```bash
# 1. Criar e ativar virtualenv
python3 -m venv .venv
source .venv/bin/activate

# 2. Instalar dependências
pip install -e ".[dev]"

# 3. Instalar o browser Chromium usado pelo Playwright
playwright install chromium
```

Alternativamente, use o script de setup que faz tudo isso automaticamente:

```bash
bash scripts/setup.sh
```

---

## Configuração

### Variáveis de ambiente

Copie o arquivo de exemplo e ajuste os valores:

```bash
cp .env.example .env
```

| Variável           | Padrão                             | Descrição                                 |
|--------------------|------------------------------------|-------------------------------------------|
| `WEB_PORT`         | `5000`                             | Porta do servidor web                     |
| `WEB_HOST`         | `0.0.0.0`                          | Host do servidor web                      |
| `WEB_DEBUG`        | `true`                             | Modo debug do Flask                       |
| `WEB_USER`         | `change_me`                        | Usuário para login na interface web       |
| `WEB_PASSWORD`     | `change_me`                        | Senha para login na interface web         |
| `DATABASE_URL`     | `sqlite:///real_estate_monitor.db` | URL do banco de dados                     |
| `FLASK_SECRET_KEY` | `dev-secret-key-change-in-prod`    | Chave secreta para sessões Flask          |

**Importante:** troque `WEB_USER` e `WEB_PASSWORD` antes de expor o sistema em uma rede.

### Fontes de dados (`configs/sources.yaml`)

Cada fonte de imobiliária é definida em `configs/sources.yaml`. Exemplo de estrutura:

```yaml
sources:
  - id: minha_imobiliaria          # identificador único (estável — não alterar após criação)
    name: "Minha Imobiliária"
    url_template: "https://exemplo.com/alugar/{city}?min={min_price}&max={max_price}"
    filters:
      city: curitiba
      min_price: 2000
      max_price: 4500
    adapter: "playwright_bs"
    enabled: true
    config:
      headless: true
      wait_selector: ".card-imovel"     # seletor CSS que indica que a página carregou
      wait_timeout: 15000               # ms para aguardar o seletor aparecer
      listing_selector: ".card-imovel"  # seletor CSS de cada card de anúncio
      pagination_type: "scroll"         # "scroll", "click" ou "none"
      pagination:
        max_pages: 10
        scroll_pause: 2.0               # segundos entre scrolls (modo scroll)
        # next_button: ".btn-proxima"   # seletor do botão próxima página (modo click)
        # wait_after_click: 3.0         # segundos após clicar em próxima (modo click)
      removal_grace_period: 2           # scrapes consecutivos sem o imóvel antes de marcar como removido
      scrape_health_threshold: 0.6      # aborta o diff se retornar < 60% do total esperado
      fields:
        title: ".titulo-card"
        price: ".preco"
        address: ".endereco"
        url: "a.link-card"              # deixe "" se o card inteiro for um <a>
        bedrooms: ".quartos"
        bathrooms: ".banheiros"
        parking: ".vagas"
        area: ".area"
        description: ""                 # deixe "" se não disponível
        image_url: "img.foto"
```

Para descobrir os seletores CSS de um novo site, use o comando `inspect-source` (ver [Adicionar novas fontes](#adicionar-novas-fontes)).

---

## Banco de dados

Na primeira execução, inicialize o banco:

```bash
real-estate-monitor init-db
```

Após atualizações do sistema que modifiquem o schema, aplique as migrações:

```bash
real-estate-monitor migrate-db
```

O banco SQLite é criado em `real_estate_monitor.db` (ou no caminho definido por `DATABASE_URL`).

---

## Scraping

### Executar uma fonte específica

```bash
real-estate-monitor run-source <source_id>
```

O `source_id` é o número exibido pelo comando `list-sources`:

```bash
real-estate-monitor list-sources
# [2] JLA Imóveis - https://...
# [3] UNA Imóveis - https://...
```

### Executar todas as fontes habilitadas

```bash
real-estate-monitor run-all
```

### Testar scraping sem salvar no banco (dry run)

```bash
real-estate-monitor dry-run-source <source_id>
```

### Detectar duplicatas entre fontes

Após rodar o scraping, detecte imóveis anunciados por múltiplas imobiliárias:

```bash
real-estate-monitor find-duplicates
```

Os pares encontrados ficam disponíveis na interface web em **Duplicatas** para revisão manual.

### Script de scraping completo

Para rodar scraping + detecção de duplicatas em um único comando:

```bash
bash scripts/scrape.sh
```

---

## Interface web

Inicie o servidor web local:

```bash
bash scripts/start-web.sh
```

Ou diretamente:

```bash
python -m real_estate_monitor.web
```

Acesse em [http://localhost:5000](http://localhost:5000) (ou a porta configurada em `WEB_PORT`).

**Páginas disponíveis:**

| Página     | URL           | Descrição                                                  |
|------------|---------------|------------------------------------------------------------|
| Dashboard  | `/`           | Eventos recentes não verificados, contadores gerais        |
| Imóveis    | `/listings`   | Lista de todos os imóveis ativos, com filtro por fonte     |
| Favoritos  | `/favorites`  | Imóveis marcados como favoritos                            |
| Eventos    | `/events`     | Histórico de eventos (NEW, PRICE_CHANGED, REMOVED, etc.)  |
| Duplicatas | `/duplicates` | Pares de imóveis duplicados aguardando revisão             |

---

## Referência de comandos

Todos os comandos são acessíveis via `real-estate-monitor` (ou `python -m real_estate_monitor.cli`):

### Banco de dados

```bash
real-estate-monitor init-db        # cria as tabelas (primeira vez)
real-estate-monitor migrate-db     # aplica migrações de schema
```

### Fontes

```bash
real-estate-monitor list-sources               # lista todas as fontes configuradas
real-estate-monitor run-source <id>            # raspa uma fonte específica
real-estate-monitor run-all                    # raspa todas as fontes habilitadas
real-estate-monitor dry-run-source <id>        # scraping sem persistir no banco
real-estate-monitor reset-source <id>          # apaga todos os dados de uma fonte
real-estate-monitor reset-all                  # apaga todos os dados de todas as fontes
```

### Eventos e imóveis

```bash
real-estate-monitor show-events                     # últimos 20 eventos
real-estate-monitor show-events --limit 100         # últimos 100 eventos
real-estate-monitor show-events --verified no       # apenas não verificados
real-estate-monitor show-events --source <id>       # filtrar por fonte
real-estate-monitor show-event-details <event_id>   # detalhes de um evento específico
```

### Favoritos

```bash
real-estate-monitor list-favorites                  # lista imóveis favoritos
real-estate-monitor favorite-listing <listing_id>   # marcar como favorito
real-estate-monitor unfavorite-listing <listing_id> # remover dos favoritos
```

### Duplicatas

```bash
real-estate-monitor find-duplicates                 # detectar duplicatas entre fontes
```

### Desenvolvimento

```bash
real-estate-monitor inspect-source <url>                        # analisa uma página e sugere seletores CSS
real-estate-monitor inspect-source <url> --selector ".card"     # inspeciona campos dentro de um seletor específico
```

---

## Agendamento automático

Para rodar o scraping automaticamente, adicione uma entrada no crontab:

```bash
crontab -e
```

Exemplo — rodar todos os dias às 8h, 14h e 20h:

```cron
0 8,14,20 * * * /caminho/para/procura_aluguel/scripts/scrape.sh >> /caminho/para/procura_aluguel/logs/scrape.log 2>&1
```

O script `scripts/scrape.sh` ativa o virtualenv, roda todas as fontes e detecta duplicatas. Os logs são salvos em `logs/scrape.log`.

Para adicionar o cron automaticamente com o caminho correto:

```bash
bash scripts/install-cron.sh
```

---

## Adicionar novas fontes

### 1. Identificar os seletores CSS

Use o comando `inspect-source` para analisar a página da imobiliária:

```bash
real-estate-monitor inspect-source "https://nova-imobiliaria.com.br/alugar/curitiba"
```

Isso exibe os seletores CSS mais frequentes na página. Depois, especifique o container de cada anúncio para ver os campos disponíveis:

```bash
real-estate-monitor inspect-source "https://nova-imobiliaria.com.br/alugar/curitiba" \
  --selector ".card-imovel"
```

### 2. Adicionar ao YAML

Adicione a nova fonte em `configs/sources.yaml` com os seletores identificados.

### 3. Testar com dry run

```bash
real-estate-monitor dry-run-source <id>
```

Confirme que título, preço, endereço e URL estão sendo capturados corretamente.

### 4. Rodar de verdade

```bash
real-estate-monitor run-source <id>
```

---

## Testes

```bash
pytest tests/ -v
```

---

## Estrutura do projeto

```
procura_aluguel/
├── configs/
│   └── sources.yaml                  # configuração das fontes de imobiliárias
├── real_estate_monitor/
│   ├── cli.py                        # ponto de entrada do CLI (Typer)
│   ├── database.py                   # engine e sessão SQLAlchemy
│   ├── adapters/
│   │   └── playwright_bs_adapter.py  # adapter de scraping (Playwright + BS4)
│   ├── configs/
│   │   └── config_loader.py          # carrega e sincroniza YAML → banco
│   ├── models/
│   │   └── models.py                 # modelos ORM (Source, Listing, ListingEvent, ListingDuplicate)
│   ├── schemas/
│   │   └── schemas.py                # schemas Pydantic (SourceConfig, NormalizedListing)
│   ├── services/
│   │   ├── runner.py                 # orquestração do scraping
│   │   ├── diff_service.py           # detecção de novos/alterados/removidos
│   │   ├── duplicate_service.py      # detecção de duplicatas entre fontes
│   │   ├── browser.py                # wrapper do Playwright
│   │   ├── money_parser.py           # parser de valores monetários brasileiros
│   │   └── ...
│   └── web/
│       ├── __init__.py               # factory do app Flask
│       ├── routes.py                 # rotas da interface web
│       └── templates/                # templates Jinja2
├── scripts/
│   ├── setup.sh                      # instalação inicial
│   ├── scrape.sh                     # scraping completo (para cron)
│   ├── start-web.sh                  # inicia o servidor web
│   └── install-cron.sh               # instala o cron de scraping automático
├── tests/
├── snapshots/                        # snapshots HTML salvos por fonte
├── logs/                             # logs de execução (criado automaticamente)
├── .env.example                      # variáveis de ambiente de exemplo
└── pyproject.toml
```
