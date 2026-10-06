-- ============================================================
-- Migración 041: orden del nodo y forma de pago en pagos_cfdi (carril A, F3.5b)
-- Idempotente: ADD COLUMN IF NOT EXISTS / DROP CONSTRAINT IF EXISTS /
-- CREATE UNIQUE INDEX IF NOT EXISTS.
--
-- La llave de pagos_cfdi era (cfdi_id, fecha_pago, monto): dos pago20:Pago del mismo
-- REP con la misma fecha y monto compartían fila y los documentos relacionados
-- idénticos de uno y otro colapsaban (el IVA cobrado de uno se perdía). Ahora cada
-- nodo del XML tiene su fila, identificada por su orden (nodo 1, 2, ...).
--
-- nodo = 0 significa "fila anterior a esta migración, sin asignar": no entra al índice
-- único, así que los REP ya guardados no chocan. cfdi_store las reclama por fecha y
-- monto al reprocesar (DETALLE_VERSION 3) y les pone su nodo real.
--
-- forma_pago es FormaDePagoP de cada pago (c_FormaPago): V1 (efectivo pagado vía REP
-- en no bancarizado) y F5.4 (exclusión del acreditable por efectivo) la necesitan.
-- NULL = el XML no la trae. Se guarda cruda: el catálogo puede crecer.
-- ============================================================

ALTER TABLE pagos_cfdi
  ADD COLUMN IF NOT EXISTS nodo       SMALLINT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS forma_pago VARCHAR(20);

-- La llave anterior ya no vale: dos nodos legítimos pueden coincidir en fecha y monto.
-- (Nombre que Postgres le puso a UNIQUE (cfdi_id, fecha_pago, monto) en la 004.)
ALTER TABLE pagos_cfdi DROP CONSTRAINT IF EXISTS pagos_cfdi_cfdi_id_fecha_pago_monto_key;

CREATE UNIQUE INDEX IF NOT EXISTS uq_pagos_cfdi_nodo
    ON pagos_cfdi (cfdi_id, nodo) WHERE nodo > 0;
