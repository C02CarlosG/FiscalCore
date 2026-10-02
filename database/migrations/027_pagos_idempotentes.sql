-- ============================================================
-- Migración 027: Pagos (REP) idempotentes y UUIDs normalizados
-- Idempotente: UPDATE/DELETE condicionados + CREATE UNIQUE INDEX IF NOT EXISTS.
--
-- Bug: pagos_relaciones no tenía restricción única, así que el
-- "ON CONFLICT DO NOTHING" de la ingesta nunca aplicaba. Re-subir el mismo
-- Complemento de Pago duplicaba la relación y volvía a sumar el importe a
-- cfdi.monto_cobrado, inflando lo cobrado y el IVA de PPD en la cédula.
-- Además los UUID se guardaban con la caja que trajera cada XML (timbre vs
-- IdDocumento del REP), y los cruces exactos fallaban cuando no coincidía.
-- ============================================================

-- 1. UUIDs en mayúsculas (la app ya los normaliza al parsear).
--    En cfdi.uuid hay UNIQUE: si ya existiera la versión en mayúsculas no se
--    toca la fila para no violar la restricción y tumbar el arranque.
UPDATE cfdi c
SET uuid = UPPER(c.uuid)
WHERE c.uuid <> UPPER(c.uuid)
  AND NOT EXISTS (SELECT 1 FROM cfdi d WHERE d.uuid = UPPER(c.uuid));

UPDATE pagos_cfdi
SET uuid_cfdi_pago = UPPER(uuid_cfdi_pago)
WHERE uuid_cfdi_pago <> UPPER(uuid_cfdi_pago);

UPDATE pagos_relaciones
SET cfdi_uuid = UPPER(cfdi_uuid)
WHERE cfdi_uuid <> UPPER(cfdi_uuid);

-- 2. Eliminar relaciones duplicadas por re-ingesta (se conserva una por
--    pago + CFDI + parcialidad).
DELETE FROM pagos_relaciones a
USING pagos_relaciones b
WHERE a.pago_id = b.pago_id
  AND a.cfdi_uuid = b.cfdi_uuid
  AND COALESCE(a.parcialidad, 0) = COALESCE(b.parcialidad, 0)
  AND a.id > b.id;

-- 3. Restricción única: a partir de aquí el ON CONFLICT DO NOTHING sí aplica.
--    (Sin CONCURRENTLY: el archivo corre en una transacción y la tabla es chica.)
CREATE UNIQUE INDEX IF NOT EXISTS uq_pagos_rel_pago_cfdi_parcialidad
    ON pagos_relaciones (pago_id, cfdi_uuid, COALESCE(parcialidad, 0));

-- 4. Recalcular lo cobrado de los CFDI con pagos registrados, derivándolo de
--    pagos_relaciones (corrige los montos inflados por re-ingestas previas).
--    Solo toca filas cuyo valor cambia, así que re-ejecutarlo no escribe nada.
WITH pagado AS (
    SELECT pc.empresa_id, pr.cfdi_uuid, SUM(pr.importe_pagado) AS pagado
    FROM pagos_relaciones pr
    JOIN pagos_cfdi pc ON pc.id = pr.pago_id
    GROUP BY pc.empresa_id, pr.cfdi_uuid
),
nuevo AS (
    SELECT c.id,
           LEAST(c.total, p.pagado) AS monto_cobrado,
           CASE
               WHEN p.pagado >= c.total THEN 'pagado_total'
               WHEN p.pagado > 0        THEN 'pagado_parcial'
               ELSE 'pendiente'
           END AS estado_pago
    FROM cfdi c
    JOIN pagado p ON p.empresa_id = c.empresa_id AND p.cfdi_uuid = c.uuid
)
UPDATE cfdi c
SET monto_cobrado = n.monto_cobrado,
    estado_pago   = n.estado_pago
FROM nuevo n
WHERE c.id = n.id
  AND (c.monto_cobrado IS DISTINCT FROM n.monto_cobrado
       OR c.estado_pago IS DISTINCT FROM n.estado_pago);
