-- ============================================================
-- MIGRACIÓN 002: Usuarios + columnas adicionales en empresas
-- ============================================================

CREATE TABLE IF NOT EXISTS usuarios (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    email           VARCHAR(255) NOT NULL UNIQUE,
    password_hash   VARCHAR(255) NOT NULL,
    nombre          VARCHAR(255),
    activo          BOOLEAN DEFAULT TRUE,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_usuarios_email   ON usuarios (email);
CREATE INDEX IF NOT EXISTS idx_usuarios_empresa ON usuarios (empresa_id);

ALTER TABLE empresas
    ADD COLUMN IF NOT EXISTS constancia_path  VARCHAR(500),
    ADD COLUMN IF NOT EXISTS obligaciones      JSONB,
    ADD COLUMN IF NOT EXISTS cp_fiscal         VARCHAR(10),
    ADD COLUMN IF NOT EXISTS curp              VARCHAR(18);
