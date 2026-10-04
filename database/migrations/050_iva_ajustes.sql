-- ============================================================
-- Migración 050: ajustes manuales del IVA por flujo (F5)
-- Idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS.
--
-- El contador puede "no considerar" un CFDI en el IVA o reasignar su efecto a otro
-- periodo. Es una decisión por CFDI y por dirección (trasladado o acreditable), siempre
-- auditada (tabla `auditoria`, acción `iva_ajuste`).
--   excluir   : el CFDI sale de las sumas del IVA; periodo_destino es NULL.
--   reasignar : el efecto del CFDI pasa a periodo_destino (YYYY-MM).
-- ============================================================
CREATE TABLE IF NOT EXISTS iva_ajustes (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    cfdi_uuid       VARCHAR(36) NOT NULL,                  -- en mayúsculas, como cfdi.uuid
    direccion       VARCHAR(12) NOT NULL CHECK (direccion IN ('trasladado', 'acreditable')),
    accion          VARCHAR(10) NOT NULL CHECK (accion IN ('excluir', 'reasignar')),
    periodo_destino CHAR(7),
    motivo          TEXT NOT NULL DEFAULT '',
    usuario_id      UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT iva_ajustes_destino_chk CHECK ((accion = 'reasignar') = (periodo_destino IS NOT NULL)),
    CONSTRAINT iva_ajustes_periodo_chk CHECK (periodo_destino IS NULL OR periodo_destino ~ '^20[0-9]{2}-(0[1-9]|1[0-2])$')
);

-- Un ajuste por (empresa, CFDI, dirección): reasignar y excluir son excluyentes.
CREATE UNIQUE INDEX IF NOT EXISTS uq_iva_ajustes
    ON iva_ajustes (empresa_id, cfdi_uuid, direccion);

CREATE INDEX IF NOT EXISTS idx_iva_ajustes_destino
    ON iva_ajustes (empresa_id, periodo_destino) WHERE periodo_destino IS NOT NULL;
