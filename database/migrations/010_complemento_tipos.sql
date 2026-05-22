-- ============================================================
-- Migración 010: Tipos específicos de match por Complemento de Pago
-- Idempotente: DROP + ADD CONSTRAINT
-- ============================================================

-- 1. Extender tipo_match con complemento_pago_total y complemento_pago_parcial
--    Se conserva complemento_pago (legacy) para registros históricos.
ALTER TABLE conciliaciones DROP CONSTRAINT IF EXISTS conciliaciones_tipo_match_check;
ALTER TABLE conciliaciones ADD CONSTRAINT conciliaciones_tipo_match_check
    CHECK (tipo_match IN (
        'exacto',
        'parcial',
        'sin_cfdi',
        'sin_movimiento',
        'complemento_pago',            -- legacy (registros anteriores a 010)
        'complemento_pago_total',      -- REP liquida completamente el CFDI
        'complemento_pago_parcial',    -- REP cubre parcialmente (parcialidad)
        'agrupado',
        'parcial_multiple',
        'heuristico',
        'pendiente_rep',               -- CFDI PPD sin REP emitido (flujo normal)
        'pagado_parcial'               -- REP emitido, saldo insoluto > $0.05
    ));

-- 2. Añadir columna pago_id en conciliaciones para trazabilidad banco → REP → CFDI
ALTER TABLE conciliaciones
    ADD COLUMN IF NOT EXISTS pago_id UUID REFERENCES pagos_cfdi(id) ON DELETE SET NULL;

ALTER TABLE conciliaciones
    ADD COLUMN IF NOT EXISTS saldo_insoluto NUMERIC(18,2) DEFAULT 0;

CREATE INDEX IF NOT EXISTS idx_conciliaciones_pago ON conciliaciones (pago_id)
    WHERE pago_id IS NOT NULL;
