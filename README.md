# Scrapshe — Monitor de Feminicídio em Sergipe

Coleta e visualiza casos confirmados de feminicídio e tentativas em Sergipe, cruzando dados de fontes públicas (SSP-SE, G1) e redes sociais (Instagram).

## Fontes de dados
- **SSP-SE** — API interna de notícias da Secretaria de Segurança Pública de Sergipe
- **G1/SE** — Feed RSS do G1 Sergipe
- **Instagram** — Perfil `@gordinhodopovose` via session cookie
- **Anuário FBSP 2025** — Dados históricos de feminicídio em Sergipe (2017–2024)

## Requisitos

- Python 3.10+
- PostgreSQL (local via Docker ou remoto via Supabase)

## Setup local

```bash
cp .env.example .env  # preencha as variáveis
docker compose up -d  # sobe PostgreSQL na porta 5433
pip install -r requirements.txt
python pipeline/run.py
streamlit run dashboard/app.py
```

## Deploy (produção)

- **Dashboard:** Streamlit Community Cloud (`dashboard/app.py`)
- **Banco de dados:** Supabase (connection pooler, porta 6543)
- **Coleta automática:** GitHub Actions (ver `docs/github-actions-pipeline.md`)

## Variáveis de ambiente

Veja `.env.example` para todas as variáveis necessárias.

## Estrutura

```
scrapers/    — coletores em Go (SSP-SE, G1, Instagram)
pipeline/    — limpeza, deduplicação, extração de município, exportação CSV
dashboard/   — visualização Streamlit com dados históricos e ao vivo
migrations/  — SQL do banco de dados
scripts/     — utilitários (Instagram fetch, cron setup)
docs/        — documentação interna e planos
```
