-- ============================================================
-- Migración 009: Estados PPD en conciliaciones y cfdi
-- Idempotente: DROP + ADD CONSTRAINT / ALTER COLUMN
-- ============================================================

-- 1. (tipo_match: pendiente_rep / pagado_parcial — ahora declarado en la 010)
-- NOTA: este archivo se re-ejecuta en cada arranque (db.init_db). Aquí se
-- redefinía conciliaciones_tipo_match_check con la lista de valores vigente en
-- su momento, más corta que la actual. Con filas que ya usan valores posteriores
-- (pendiente_rep, heuristico, complemento_pago_total, ...) el ADD CONSTRAINT
-- fallaba con CheckViolation y la app no podía reiniciar. La lista completa
-- vive únicamente en 010_complemento_tipos.sql; no volver a declararla aquí.

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
