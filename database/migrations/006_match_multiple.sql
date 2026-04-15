-- ============================================================
-- Migración 006: Matching 1:N y N:1 en conciliaciones
-- Idempotente: DROP + ADD CONSTRAINT
-- ============================================================

ALTER TABLE conciliaciones DROP CONSTRAINT IF EXISTS conciliaciones_tipo_match_check;
ALTER TABLE conciliaciones ADD CONSTRAINT conciliaciones_tipo_match_check
    CHECK (tipo_match IN (
        'exacto',
        'parcial',
        'sin_cfdi',
        'sin_movimiento',
        'complemento_pago',
        'agrupado',
        'parcial_multiple'
    ));
