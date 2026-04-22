-- ============================================================
-- Migración 017: columna impuestos_declarar en tabla empresas
-- Impuestos que el contador seleccionó declarar mensualmente
-- para esta empresa.
--
-- Estructura: Array JSON de claves como "iva", "isr", "ieps",
-- "ret_iva", "ret_isr", "diot"
--
-- Idempotente: ADD COLUMN IF NOT EXISTS
-- ============================================================

ALTER TABLE empresas
  ADD COLUMN IF NOT EXISTS impuestos_declarar JSONB DEFAULT '[]'::jsonb;

COMMENT ON COLUMN empresas.impuestos_declarar
  IS 'Array de claves impuestos a declarar: ["iva","isr","ieps","ret_iva","ret_isr","diot"]';
