-- ============================================================
-- Migración 007: tipo_match "heuristico" en conciliaciones
-- Idempotente: no modifica el esquema (ver nota).
-- ============================================================

-- NOTA: este archivo se re-ejecuta en cada arranque (db.init_db). Aquí se
-- redefinía conciliaciones_tipo_match_check con la lista de valores vigente en
-- su momento, más corta que la actual. Con filas que ya usan valores posteriores
-- (pendiente_rep, heuristico, complemento_pago_total, ...) el ADD CONSTRAINT
-- fallaba con CheckViolation y la app no podía reiniciar. La lista completa
-- vive únicamente en 010_complemento_tipos.sql; no volver a declararla aquí.

SELECT 1;  -- psycopg2 rechaza ejecutar un archivo sin sentencias
