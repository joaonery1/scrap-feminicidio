# Scrapshe — Monitor de Feminicídio em Aracaju/SE

## Requisitos
- Docker + Docker Compose
- Go 1.21+
- Python 3.11+

## Setup
1. `cp .env.example .env` e preencha as variáveis
2. `docker compose up -d` — sobe PostgreSQL (porta 5433)
3. Compile os scrapers: `cd scrapers && go build -o bin/scrapshe ./cmd/scrapshe`
4. Instale dependências Python: `pip install -r pipeline/requirements.txt -r dashboard/requirements.txt`
5. Instale modelo spaCy: `python -m spacy download pt_core_news_sm`

## Uso

```bash
# Coleta de dados
./scrapers/bin/scrapshe

# Pipeline de limpeza + exportação CSV
python3 pipeline/run.py

# Dashboard
streamlit run dashboard/app.py
```

## Agendamento automático

```bash
bash scripts/setup_cron.sh $(pwd)
```

## Estrutura
- `scrapers/` — coletores em Go (SSP-SE, G1, Instagram, Dados.gov.br)
- `pipeline/` — limpeza, NLP, exportação CSV (Python)
- `dashboard/` — visualização Streamlit
- `migrations/` — SQL do banco de dados
