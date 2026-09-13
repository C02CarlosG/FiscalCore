-- 026_auditoria.sql
-- Tabla de auditoría: registra eventos sensibles (subida de CFDI, carga/uso de
-- FIEL, cambios administrativos, generación de reportes fiscales) para dar
-- trazabilidad de quién hizo qué y cuándo.
-- Idempotente: segura para ejecutar múltiples veces.

CREATE TABLE IF NOT EXISTS auditoria (
    id         UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    empresa_id UUID REFERENCES empresas(id) ON DELETE SET NULL,
    accion     VARCHAR(50) NOT NULL,
    entidad    VARCHAR(50),
    entidad_id VARCHAR(100),
    metadata   JSONB,
    creado_en  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE auditoria IS
    'Log de auditoría de eventos sensibles (subida CFDI, FIEL, cambios admin, reportes generados). Solo inserts, nunca updates/deletes desde la app.';

CREATE INDEX IF NOT EXISTS idx_auditoria_empresa ON auditoria(empresa_id, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_usuario ON auditoria(usuario_id, creado_en DESC);
CREATE INDEX IF NOT EXISTS idx_auditoria_accion  ON auditoria(accion);
