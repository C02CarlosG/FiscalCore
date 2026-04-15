-- ============================================================
-- Migración 008: columna confianza en conciliaciones
-- Idempotente: ADD COLUMN IF NOT EXISTS
-- ============================================================

ALTER TABLE conciliaciones
    ADD COLUMN IF NOT EXISTS confianza VARCHAR(5)  -- 'alta' | 'media' | 'baja' | NULL
    CHECK (confianza IS NULL OR confianza IN ('alta', 'media', 'baja'));
