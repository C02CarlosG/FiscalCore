-- ============================================================
-- Migración 021: periodo de trabajo en tabla empresas
-- Rango de fechas en que el contador trabajará la empresa:
--   fecha_inicio_periodo  → inicio del periodo
--   fecha_cierre_periodo  → cierre del periodo
--
-- Idempotente: ADD COLUMN IF NOT EXISTS
-- ============================================================

ALTER TABLE empresas
  ADD COLUMN IF NOT EXISTS fecha_inicio_periodo DATE,
  ADD COLUMN IF NOT EXISTS fecha_cierre_periodo DATE;

COMMENT ON COLUMN empresas.fecha_inicio_periodo
  IS 'Fecha de inicio del periodo de trabajo de la empresa';
COMMENT ON COLUMN empresas.fecha_cierre_periodo
  IS 'Fecha de cierre del periodo de trabajo de la empresa';
