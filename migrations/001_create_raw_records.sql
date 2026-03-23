CREATE TABLE IF NOT EXISTS raw_records (
    id            BIGSERIAL PRIMARY KEY,
    source        TEXT NOT NULL,          -- 'sspse' | 'g1' | 'instagram'
    url           TEXT NOT NULL UNIQUE,   -- chave de deduplicação
    title         TEXT,
    body          TEXT,
    published_at  TIMESTAMPTZ,
    fetched_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    processed     BOOLEAN NOT NULL DEFAULT FALSE
);

CREATE INDEX IF NOT EXISTS idx_raw_records_processed ON raw_records (processed) WHERE processed = FALSE;
CREATE INDEX IF NOT EXISTS idx_raw_records_source ON raw_records (source);
