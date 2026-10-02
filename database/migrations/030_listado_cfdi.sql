-- ============================================================
-- Migración 030: Listado de CFDI
-- Idempotente: CREATE INDEX / CREATE TABLE IF NOT EXISTS.
--
-- El listado filtra siempre por empresa + RFC (emisor o receptor) + rango de
-- fecha; los índices de una sola columna de la 001 no lo cubren.
-- ============================================================

-- 1. Índices del listado (emitidos y recibidos).
CREATE INDEX IF NOT EXISTS idx_cfdi_emp_emisor_fecha
    ON cfdi (empresa_id, rfc_emisor, fecha_emision);
CREATE INDEX IF NOT EXISTS idx_cfdi_emp_receptor_fecha
    ON cfdi (empresa_id, rfc_receptor, fecha_emision);

-- 2. Los totales suman IEPS e ISR trasladado desde cfdi_impuestos; casi todas
--    sus filas son IVA (002), así que el índice parcial es pequeño.
CREATE INDEX IF NOT EXISTS idx_cfdi_impuestos_no_iva
    ON cfdi_impuestos (cfdi_id) WHERE impuesto <> '002';

-- 3. Orden y visibilidad de columnas por usuario y por tabla ("vista").
CREATE TABLE IF NOT EXISTS preferencias_tabla (
    usuario_id  UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    vista       VARCHAR(80) NOT NULL,
    config      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (usuario_id, vista)
);
