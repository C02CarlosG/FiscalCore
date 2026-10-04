-- ============================================================
-- Migración 051: catálogo de proveedores de la empresa (F6.1)
-- Idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS.
--
-- Un renglón por tercero (proveedor) de la empresa. Se alimenta de los CFDI recibidos
-- (origen 'cfdi') o se captura a mano (origen 'manual'). tipo_tercero y tipo_operacion son
-- los valores por defecto para la DIOT; el catálogo oficial se confirma antes de F6.2, así
-- que se guardan como texto corto sin llave foránea.
-- ============================================================
CREATE TABLE IF NOT EXISTS proveedores (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    rfc             VARCHAR(13) NOT NULL,                  -- en mayúsculas
    nombre          TEXT NOT NULL DEFAULT '',
    nombre_editado  BOOLEAN NOT NULL DEFAULT FALSE,        -- el contador lo cambió: la alimentación ya no lo pisa
    tipo_tercero    VARCHAR(2),
    tipo_operacion  VARCHAR(2),
    pais            VARCHAR(60),                           -- extranjeros
    id_fiscal       VARCHAR(40),                           -- extranjeros
    origen          VARCHAR(10) NOT NULL DEFAULT 'cfdi' CHECK (origen IN ('cfdi', 'manual')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_proveedores_rfc ON proveedores (empresa_id, rfc);
CREATE INDEX IF NOT EXISTS idx_proveedores_nombre ON proveedores (empresa_id, nombre);
