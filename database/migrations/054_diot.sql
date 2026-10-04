-- ============================================================
-- Migración 054: DIOT por flujo (F6.2)
-- Idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS y CHECK dentro de DO $$ … $$.
--
-- diot_terceros_periodo : tipo de tercero y de operación de un proveedor **en un periodo** (si no hay
--                         renglón aplica el default del catálogo `proveedores`).
-- diot_operaciones_cfdi : tipo de operación de **un CFDI** en un periodo; con esto un mismo tercero puede
--                         declararse con varias operaciones en el mismo periodo.
-- Las claves permitidas son las de proveedores (051) y deben confirmarse contra el instructivo del SAT.
-- Todo cambio se audita en `auditoria` (acciones diot_tercero_periodo y diot_operacion_cfdi).
-- ============================================================
CREATE TABLE IF NOT EXISTS diot_terceros_periodo (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    periodo         CHAR(7) NOT NULL CHECK (periodo ~ '^20[0-9]{2}-(0[1-9]|1[0-2])$'),
    proveedor_id    UUID NOT NULL REFERENCES proveedores(id) ON DELETE CASCADE,
    tipo_tercero    VARCHAR(2),
    tipo_operacion  VARCHAR(2),
    usuario_id      UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_diot_terceros_periodo ON diot_terceros_periodo (empresa_id, periodo, proveedor_id);

CREATE TABLE IF NOT EXISTS diot_operaciones_cfdi (
    id              UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id      UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    periodo         CHAR(7) NOT NULL CHECK (periodo ~ '^20[0-9]{2}-(0[1-9]|1[0-2])$'),
    cfdi_uuid       VARCHAR(36) NOT NULL,                        -- en mayúsculas, como cfdi.uuid
    tipo_operacion  VARCHAR(2) NOT NULL,
    usuario_id      UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_diot_operaciones_cfdi ON diot_operaciones_cfdi (empresa_id, periodo, cfdi_uuid);

DO $$ BEGIN
    ALTER TABLE diot_terceros_periodo ADD CONSTRAINT chk_diot_tp_tercero
        CHECK (tipo_tercero IS NULL OR tipo_tercero IN ('04', '05', '15'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE diot_terceros_periodo ADD CONSTRAINT chk_diot_tp_operacion
        CHECK (tipo_operacion IS NULL OR tipo_operacion IN ('02', '03', '06', '07', '08', '85', '87'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
DO $$ BEGIN
    ALTER TABLE diot_operaciones_cfdi ADD CONSTRAINT chk_diot_oc_operacion
        CHECK (tipo_operacion IN ('02', '03', '06', '07', '08', '85', '87'));
EXCEPTION WHEN duplicate_object THEN NULL; END $$;

-- Menor de la revisión de F6.1: la clave de país es ISO 3166-1 alfa-3 (mayúsculas)
DO $$ BEGIN
    ALTER TABLE proveedores ADD CONSTRAINT chk_proveedores_pais CHECK (pais IS NULL OR pais ~ '^[A-Z]{3}$');
EXCEPTION WHEN duplicate_object THEN NULL; END $$;
