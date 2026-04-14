-- ============================================================
-- Migración 009: Estados PPD en conciliaciones y cfdi
-- Idempotente: DROP + ADD CONSTRAINT / ALTER COLUMN
-- ============================================================

-- 1. Ampliar tipo_match para incluir flujo PPD con REP
ALTER TABLE conciliaciones DROP CONSTRAINT IF EXISTS conciliaciones_tipo_match_check;
ALTER TABLE conciliaciones ADD CONSTRAINT conciliaciones_tipo_match_check
    CHECK (tipo_match IN (
        'exacto',
        'parcial',
        'sin_cfdi',
        'sin_movimiento',
        'complemento_pago',
        'agrupado',
        'parcial_multiple',
        'heuristico',
        'pendiente_rep',   -- CFDI PPD aguarda REP (flujo normal, no es riesgo)
        'pagado_parcial'   -- REP emitido pero saldo insoluto > $0.05
    ));

-- 2. Ampliar estado_pago en cfdi para incluir pendiente_rep
--    (el valor 'pendiente' legacy se mantiene por compatibilidad)
ALTER TABLE cfdi DROP CONSTRAINT IF EXISTS cfdi_estado_pago_check;
ALTER TABLE cfdi ADD CONSTRAINT cfdi_estado_pago_check
    CHECK (estado_pago IN (
        'pendiente',       -- estado inicial / legacy
        'pendiente_rep',   -- PPD sin REP emitido aún
        'pagado_parcial',  -- REP cubre parte del saldo
        'pagado_total'     -- REP cubre el total (saldo insoluto ≤ $0.05)
    ));
