-- ============================================================
-- Migración 013: Perfil extendido del contador (usuario)
-- Idempotente: ADD COLUMN IF NOT EXISTS
-- ============================================================

ALTER TABLE usuarios
  ADD COLUMN IF NOT EXISTS telefono            VARCHAR(20),
  ADD COLUMN IF NOT EXISTS rfc                 VARCHAR(13),
  ADD COLUMN IF NOT EXISTS nombre_despacho     VARCHAR(255),
  ADD COLUMN IF NOT EXISTS cedula_profesional  VARCHAR(30),
  ADD COLUMN IF NOT EXISTS updated_at          TIMESTAMPTZ DEFAULT NOW();
