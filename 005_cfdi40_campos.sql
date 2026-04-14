-- ============================================================
-- Migración 005: Campos requeridos CFDI 4.0
-- Idempotente: ADD COLUMN IF NOT EXISTS
-- Sin CHECK constraints — catálogos SAT pueden cambiar
-- ============================================================

ALTER TABLE cfdi ADD COLUMN IF NOT EXISTS exportacion               VARCHAR(2);
ALTER TABLE cfdi ADD COLUMN IF NOT EXISTS lugar_expedicion          VARCHAR(5);
ALTER TABLE cfdi ADD COLUMN IF NOT EXISTS domicilio_fiscal_receptor VARCHAR(5);
ALTER TABLE cfdi ADD COLUMN IF NOT EXISTS regimen_fiscal_receptor   VARCHAR(3);
