-- ============================================================
-- Migración 052: ajustes manuales del ISR base flujo (F7.1)
-- Idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS.
--
-- El contador puede "no considerar" un CFDI en el ISR. Es una decisión por CFDI y por lado
-- (ingreso o deducción), siempre auditada (tabla `auditoria`, acción `isr_ajuste`). Es
-- independiente de iva_ajustes (migración 050).
-- ============================================================
CREATE TABLE IF NOT EXISTS isr_ajustes (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id  UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    cfdi_uuid   VARCHAR(36) NOT NULL,                      -- en mayúsculas, como cfdi.uuid
    lado        VARCHAR(10) NOT NULL CHECK (lado IN ('ingreso', 'deduccion')),
    motivo      TEXT NOT NULL CHECK (length(btrim(motivo)) > 0),
    usuario_id  UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Un ajuste por (empresa, CFDI, lado)
CREATE UNIQUE INDEX IF NOT EXISTS uq_isr_ajustes ON isr_ajustes (empresa_id, cfdi_uuid, lado);
