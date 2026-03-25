-- relacao: relação agressor-vítima
ALTER TABLE casos ADD COLUMN IF NOT EXISTS relacao TEXT NOT NULL DEFAULT 'desconhecido';

CREATE INDEX IF NOT EXISTS idx_casos_relacao ON casos (relacao);
