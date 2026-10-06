-- 065_suscripciones_historial.sql
-- M7.2 (carril D): historial de asignaciones de plan por cuenta. Cada asignación del
-- administrador de la plataforma agrega una fila en la misma transacción que actualiza
-- `suscripciones` (la auditoría es de mejor esfuerzo y no sirve como historial).
-- Idempotente: CREATE ... IF NOT EXISTS y la siembra solo para cuentas sin historial.

CREATE TABLE IF NOT EXISTS suscripciones_historial (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    usuario_id     UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    plan_clave     VARCHAR(30) NOT NULL REFERENCES planes(clave),
    estado         VARCHAR(20) NOT NULL
                   CHECK (estado IN ('activa', 'suspendida', 'cancelada')),
    vigente_hasta  DATE,
    notas          TEXT,
    asignada_por   UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    creada_en      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_suscripciones_historial_usuario
    ON suscripciones_historial (usuario_id, creada_en DESC);

-- La asignación vigente de quien ya tenía suscripción antes de esta migración pasa a
-- ser su primera fila de historial.
INSERT INTO suscripciones_historial (usuario_id, plan_clave, estado, vigente_hasta, notas, asignada_por, creada_en)
SELECT s.usuario_id, s.plan_clave, s.estado, s.vigente_hasta, s.notas, s.asignada_por, s.updated_at
FROM suscripciones s
WHERE NOT EXISTS (SELECT 1 FROM suscripciones_historial h WHERE h.usuario_id = s.usuario_id);
