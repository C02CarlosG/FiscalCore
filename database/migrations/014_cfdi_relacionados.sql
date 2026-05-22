-- ============================================================
-- Migración 014: CfdiRelacionados en tabla cfdi
-- Almacena los nodos CfdiRelacionados del XML (TipoRelacion + UUIDs)
-- Necesario para detectar anticipos (TipoRelacion=07) y notas de crédito
-- Idempotente: ADD COLUMN IF NOT EXISTS
-- ============================================================

ALTER TABLE cfdi
  ADD COLUMN IF NOT EXISTS cfdi_relacionados JSONB DEFAULT '[]'::jsonb;

-- Índice GIN para búsquedas eficientes sobre el JSONB
CREATE INDEX IF NOT EXISTS idx_cfdi_relacionados_gin
  ON cfdi USING GIN (cfdi_relacionados);
