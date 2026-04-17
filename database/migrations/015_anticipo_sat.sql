-- ============================================================
-- Migración 015: columna es_anticipo_sat en tabla cfdi
-- Paso 1 SAT oficial: un CFDI de ingreso es anticipo cuando tiene
--   ClaveProdServ=84111506 + MetodoPago=PUE + sin CfdiRelacionados
-- El valor se calcula en el parser al momento de la carga.
-- Idempotente: ADD COLUMN IF NOT EXISTS
-- ============================================================

ALTER TABLE cfdi
  ADD COLUMN IF NOT EXISTS es_anticipo_sat BOOLEAN NOT NULL DEFAULT FALSE;
