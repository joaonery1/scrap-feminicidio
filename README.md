# Scrapshe — Monitor de Feminicídio em Sergipe

Coleta e visualiza casos confirmados de feminicídio e tentativas em Sergipe, cruzando dados de fontes públicas e redes sociais em tempo real.

## Fontes de dados

| Fonte | Tipo | Frequência |
|-------|------|------------|
| **SSP-SE** | API de notícias da Secretaria de Segurança Pública | A cada 2h |
| **G1 Sergipe** | Feed RSS | A cada 2h |
| **Infonet** | Feed RSS | A cada 2h |
| **SE Notícias** | Feed RSS de busca | A cada 2h |
| **Instagram** | Perfis `@gordinhodopovose` e `@dougtvnews` | A cada 2h |
| **Anuário FBSP 2025** | Dados históricos de feminicídio em Sergipe (2017–2024) | — |

## Arquitetura

```
scrapers/    — coletores em Go (SSP-SE, G1, Infonet, SE Notícias, Instagram)
pipeline/    — limpeza, deduplicação, extração de município via NLP, exportação CSV
dashboard/   — visualização Streamlit com dados históricos e ao vivo
migrations/  — SQL do banco de dados
scripts/     — utilitários (Instagram fetch, backfill histórico)
```

## Deploy (produção)

- **Dashboard:** Streamlit Community Cloud (`dashboard/app.py`)
- **Banco de dados:** Supabase (connection pooler, porta 6543)
- **Coleta automática:** GitHub Actions — roda a cada 2h, dois jobs: `scrapers` (Go) → `pipeline` (Python)

## Setup local

```bash
cp .env.example .env  # preencha as variáveis
pip install -r requirements.txt
go run ./scrapers/cmd/scrapshe   # roda os scrapers Go
python pipeline/run.py           # processa e exporta
streamlit run dashboard/app.py   # visualização
```

## Variáveis de ambiente

| Variável | Descrição |
|----------|-----------|
| `POSTGRES_HOST` | Host do banco (pooler Supabase em produção) |
| `POSTGRES_PORT` | Porta (6543 para pooler Supabase) |
| `POSTGRES_DB` | Nome do banco (`postgres`) |
| `POSTGRES_USER` | Usuário (`postgres.{project-ref}` no Supabase) |
| `POSTGRES_PASSWORD` | Senha do banco |
| `IG_SESSION_ID` | Cookie de sessão do Instagram (renovar quando expirar) |

Veja `.env.example` para referência completa.
