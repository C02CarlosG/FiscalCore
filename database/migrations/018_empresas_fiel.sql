-- 018_empresas_fiel.sql
-- Almacenamiento cifrado de credenciales FIEL por empresa (idempotente)

CREATE TABLE IF NOT EXISTS empresas_fiel (
    id              UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    empresa_id      UUID NOT NULL UNIQUE REFERENCES empresas(id) ON DELETE CASCADE,
    cer_cifrado     TEXT NOT NULL,
    key_cifrado     TEXT NOT NULL,
    pwd_cifrado     TEXT NOT NULL,
    rfc_certificado VARCHAR(13),
    vigencia_fin    DATE,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
