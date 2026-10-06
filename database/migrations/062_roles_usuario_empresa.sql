-- ============================================================
-- Migración 062: Roles por empresa e invitaciones (U1, carril D)
-- Idempotente: UPDATE condicionados, CREATE ... IF NOT EXISTS y CHECK creado
-- solo si no existe.
--
-- usuario_empresas.rol pasa a tener dos valores: 'administrador' (gestiona los
-- usuarios de la empresa) y 'contador'. Hasta hoy todos los vínculos quedaban en
-- 'contador' por defecto, así que el creador de cada empresa (su vínculo más
-- antiguo) se marca como administrador si la empresa no tiene ninguno.
--
-- El acceso de otra persona a una empresa se da por invitación: el administrador
-- invita un correo y la persona la acepta desde su perfil. Nadie queda vinculado
-- sin su consentimiento y la respuesta no revela si el correo tiene cuenta.
-- ============================================================

-- 1. Las variantes de administrador se conservan como administrador.
UPDATE usuario_empresas
SET rol = 'administrador'
WHERE rol <> 'administrador' AND lower(btrim(rol)) IN ('administrador', 'admin');

-- 2. Cualquier otro valor se normaliza a 'contador'.
UPDATE usuario_empresas
SET rol = 'contador'
WHERE rol NOT IN ('administrador', 'contador');

-- 3. El vínculo más antiguo de cada empresa sin administrador pasa a serlo.
UPDATE usuario_empresas ue
SET rol = 'administrador'
FROM (
    SELECT DISTINCT ON (empresa_id) empresa_id, usuario_id
    FROM usuario_empresas
    ORDER BY empresa_id, created_at ASC NULLS LAST, usuario_id
) primero
WHERE ue.empresa_id = primero.empresa_id
  AND ue.usuario_id = primero.usuario_id
  AND NOT EXISTS (
      SELECT 1 FROM usuario_empresas otro
      WHERE otro.empresa_id = ue.empresa_id AND otro.rol = 'administrador'
  );

-- 4. Solo los dos roles conocidos.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'chk_usuario_empresas_rol'
          AND conrelid = 'usuario_empresas'::regclass
    ) THEN
        ALTER TABLE usuario_empresas
            ADD CONSTRAINT chk_usuario_empresas_rol CHECK (rol IN ('administrador', 'contador'));
    END IF;
END $$;

-- 5. Invitaciones por correo (en minúsculas) con doble confirmación:
--      pendiente ──(la persona acepta)──▶ aceptada_pendiente ──(un administrador aprueba)──▶ aprobada
--         │                                    └──(un administrador rechaza)──▶ rechazada_admin
--         ├──(la persona rechaza)──▶ rechazada
--         └──(un administrador cancela)──▶ cancelada
--    Solo al aprobar se crea el vínculo en usuario_empresas. expires_at vence la
--    etapa en curso: 7 días para aceptar y, ya aceptada, 7 días para aprobar.
--    Una sola invitación abierta (pendiente o aceptada_pendiente) por empresa y correo.
CREATE TABLE IF NOT EXISTS invitaciones_empresa (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id     UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    email          VARCHAR(255) NOT NULL CHECK (email = lower(btrim(email))),
    rol            VARCHAR(20) NOT NULL CHECK (rol IN ('administrador', 'contador')),
    estado         VARCHAR(20) NOT NULL DEFAULT 'pendiente'
                   CHECK (estado IN ('pendiente', 'aceptada_pendiente', 'aprobada',
                                     'rechazada', 'rechazada_admin', 'cancelada')),
    invitada_por   UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at     TIMESTAMPTZ NOT NULL DEFAULT NOW() + INTERVAL '7 days',
    -- La persona invitada: quién aceptó o rechazó y cuándo.
    respondida_por UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    respondida_at  TIMESTAMPTZ,
    -- El administrador: quién aprobó, rechazó o canceló y cuándo.
    resuelta_por   UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    resuelta_at    TIMESTAMPTZ
);

CREATE UNIQUE INDEX IF NOT EXISTS uq_invitaciones_abierta
    ON invitaciones_empresa (empresa_id, email) WHERE estado IN ('pendiente', 'aceptada_pendiente');
CREATE INDEX IF NOT EXISTS idx_invitaciones_email_abierta
    ON invitaciones_empresa (email) WHERE estado IN ('pendiente', 'aceptada_pendiente');
