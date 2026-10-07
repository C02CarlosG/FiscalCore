-- 067_reinicios_empresa.sql
-- «Reiniciar datos» (carril D): cada previsualización deja un token de un solo uso
-- (solo su SHA-256) y, al confirmarse, los conteos borrados. Sirve de historial.
-- Idempotente: CREATE ... IF NOT EXISTS.

CREATE TABLE IF NOT EXISTS reinicios_empresa (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id      UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    token_sha256    CHAR(64) NOT NULL UNIQUE,
    alcance         VARCHAR(10) NOT NULL DEFAULT 'todo' CHECK (alcance IN ('todo')),
    conteos         JSONB NOT NULL,
    expira_en       TIMESTAMPTZ NOT NULL,
    usado_en        TIMESTAMPTZ,
    borrados        JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_reinicios_empresa ON reinicios_empresa (empresa_id, created_at DESC);
