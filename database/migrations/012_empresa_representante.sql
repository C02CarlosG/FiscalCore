-- ============================================================
-- Migración 012: Representante legal en empresas
-- Aplica para Personas Morales (RFC de 12 caracteres)
-- Idempotente: ADD COLUMN IF NOT EXISTS
-- ============================================================

ALTER TABLE empresas
  ADD COLUMN IF NOT EXISTS representante_legal VARCHAR(255),
  ADD COLUMN IF NOT EXISTS rfc_representante   VARCHAR(13);
