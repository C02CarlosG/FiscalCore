-- ============================================================
-- Migración 060: Documentos fiscales (F8, carril D)
-- Idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS.
--
-- Constancia de situación fiscal y opinión del cumplimiento (32-D) que el
-- contador sube en PDF por empresa. El PDF va en la base (BYTEA) y no en disco:
-- el contenedor de despliegue es efímero y así se borra junto con la empresa.
-- Se conserva el historial; el documento vigente es el de created_at más reciente.
-- ============================================================

CREATE TABLE IF NOT EXISTS documentos_fiscales (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id     UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    tipo           VARCHAR(20) NOT NULL CHECK (tipo IN ('constancia', 'opinion')),
    nombre_archivo VARCHAR(255) NOT NULL,
    contenido      BYTEA NOT NULL,
    tamano_bytes   INTEGER NOT NULL,
    sha256         CHAR(64) NOT NULL,
    rfc            VARCHAR(13) NOT NULL,
    fecha_emision  DATE,
    datos          JSONB NOT NULL DEFAULT '{}'::jsonb,
    usuario_id     UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- El mismo PDF dos veces para la misma empresa y tipo se rechaza (409).
    UNIQUE (empresa_id, tipo, sha256)
);

CREATE INDEX IF NOT EXISTS idx_documentos_fiscales_empresa
    ON documentos_fiscales (empresa_id, tipo, created_at DESC);

COMMENT ON TABLE documentos_fiscales IS
    'Constancia de situación fiscal y opinión del cumplimiento subidas en PDF por empresa (F8).';
