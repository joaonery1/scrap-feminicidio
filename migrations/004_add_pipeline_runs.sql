CREATE TABLE IF NOT EXISTS pipeline_runs (
    id          BIGSERIAL PRIMARY KEY,
    started_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    casos_inseridos  INT NOT NULL DEFAULT 0,
    casos_backfill   INT NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'running',  -- running | success | error
    error_msg   TEXT
);
