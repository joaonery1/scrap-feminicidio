-- tipo: consumado | tentativa | desconhecido
ALTER TABLE casos ADD COLUMN IF NOT EXISTS tipo TEXT NOT NULL DEFAULT 'desconhecido';

-- caso_grupo_id: aponta para o caso principal quando dois registros cobrem o mesmo crime
ALTER TABLE casos ADD COLUMN IF NOT EXISTS caso_grupo_id BIGINT REFERENCES casos(id);

CREATE INDEX IF NOT EXISTS idx_casos_tipo ON casos (tipo);
CREATE INDEX IF NOT EXISTS idx_casos_grupo ON casos (caso_grupo_id) WHERE caso_grupo_id IS NOT NULL;
