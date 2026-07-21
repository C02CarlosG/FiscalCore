-- ============================================================
-- Migración 025: Ampliar columna tipo_match (VARCHAR(20) -> VARCHAR(30))
-- Idempotente: ALTER COLUMN TYPE con el mismo ancho no falla si se reaplica.
--
-- Bug: las migraciones 009/010 extendieron el CHECK de tipo_match para
-- permitir 'complemento_pago_total' (23 chars) y 'complemento_pago_parcial'
-- (25 chars), pero la columna seguía en VARCHAR(20) desde la 001. Insertar
-- cualquiera de esos dos valores lanza StringDataRightTruncation y tumba
-- todo el batch de conciliación (ingesta.py) con un 500 — reproducido en
-- vivo durante la validación E2E de la Fase C (Día 26-27, 2026-07-21).
-- ============================================================

ALTER TABLE conciliaciones ALTER COLUMN tipo_match TYPE VARCHAR(30);
