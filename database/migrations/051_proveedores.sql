-- ============================================================
-- Migración 051: catálogo de proveedores de la empresa (F6.1)
-- Idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS y CHECK dentro de DO $$ … $$.
--
-- Un renglón por tercero (proveedor) de la empresa. Se alimenta de los CFDI recibidos
-- (origen 'cfdi') o se captura a mano (origen 'manual'). tipo_tercero y tipo_operacion son
-- los valores por defecto para la DIOT. Las claves permitidas (04/05/15 y 02/03/06/07/08/85/87)
-- DEBEN CONFIRMARSE contra el instructivo oficial del SAT (el entorno no lo puede consultar).
--
-- Los extranjeros comparten RFC genérico (XEXX010101000) y los de operaciones con público en general
-- XAXX010101000: por eso el RFC solo es único para los demás; un extranjero se identifica por su
-- ID fiscal y se edita por id.
-- ============================================================
CREATE TABLE IF NOT EXISTS proveedores (
    id                    UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id            UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    rfc                   VARCHAR(13) NOT NULL,                  -- en mayúsculas
    nombre                TEXT NOT NULL DEFAULT '',
    nombre_editado        BOOLEAN NOT NULL DEFAULT FALSE,        -- el contador lo cambió: la alimentación ya no lo pisa
    tipo_tercero          VARCHAR(2),
    tipo_operacion        VARCHAR(2),
    pais                  CHAR(3),                               -- clave ISO 3166-1 alfa-3 (extranjeros)
    jurisdiccion_detalle  TEXT,                                  -- detalle adicional de la jurisdicción (opcional)
    id_fiscal             VARCHAR(40),                           -- extranjeros
    efectos_fiscales      BOOLEAN,                               -- indicador de efectos fiscales en el extranjero
    origen                VARCHAR(10) NOT NULL DEFAULT 'cfdi' CHECK (origen IN ('cfdi', 'manual')),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- RFC único por empresa salvo los genéricos (varios extranjeros comparten XEXX010101000)
CREATE UNIQUE INDEX IF NOT EXISTS uq_proveedores_rfc
    ON proveedores (empresa_id, rfc) WHERE rfc NOT IN ('XEXX010101000', 'XAXX010101000');
-- Un extranjero se identifica por su ID fiscal
CREATE UNIQUE INDEX IF NOT EXISTS uq_proveedores_id_fiscal
    ON proveedores (empresa_id, id_fiscal) WHERE tipo_tercero = '05' AND id_fiscal IS NOT NULL;
-- La alimentación desde CFDI de un RFC genérico es idempotente por nombre
CREATE UNIQUE INDEX IF NOT EXISTS uq_proveedores_generico_cfdi
    ON proveedores (empresa_id, rfc, nombre) WHERE rfc IN ('XEXX010101000', 'XAXX010101000') AND origen = 'cfdi';
CREATE INDEX IF NOT EXISTS idx_proveedores_nombre ON proveedores (empresa_id, nombre);

DO $$ BEGIN
    ALTER TABLE proveedores ADD CONSTRAINT chk_proveedores_tipo_tercero
        CHECK (tipo_tercero IS NULL OR tipo_tercero IN ('04', '05', '15'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE proveedores ADD CONSTRAINT chk_proveedores_tipo_operacion
        CHECK (tipo_operacion IS NULL OR tipo_operacion IN ('02', '03', '06', '07', '08', '85', '87'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE proveedores ADD CONSTRAINT chk_proveedores_rfc_mayusculas CHECK (rfc = UPPER(rfc));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
