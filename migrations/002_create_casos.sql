CREATE TABLE IF NOT EXISTS casos (
    id            BIGSERIAL PRIMARY KEY,
    raw_id        BIGINT REFERENCES raw_records(id),
    source        TEXT NOT NULL,
    url           TEXT NOT NULL,
    title         TEXT,
    body_trecho   TEXT,                  -- primeiros 500 chars
    published_at  DATE,                  -- normalizado para DATE
    bairro        TEXT,                  -- extraído pelo NLP (pode ser NULL)
    dedup_hash    TEXT UNIQUE,           -- SHA-256(published_at + body[:100])
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_casos_published ON casos (published_at);
CREATE INDEX IF NOT EXISTS idx_casos_bairro ON casos (bairro) WHERE bairro IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_casos_source ON casos (source);
