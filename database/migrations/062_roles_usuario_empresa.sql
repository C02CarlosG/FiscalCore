-- ============================================================
-- Migración 062: Roles por empresa (U1, carril D)
-- Idempotente: UPDATE condicionados y CHECK creado solo si no existe.
--
-- usuario_empresas.rol pasa a tener dos valores: 'administrador' (gestiona los
-- usuarios de la empresa) y 'contador'. Hasta hoy todos los vínculos quedaban en
-- 'contador' por defecto, así que el creador de cada empresa (su vínculo más
-- antiguo) se marca como administrador si la empresa no tiene ninguno.
-- ============================================================

-- 1. Cualquier valor distinto se normaliza a 'contador'.
UPDATE usuario_empresas
SET rol = 'contador'
WHERE rol NOT IN ('administrador', 'contador');

-- 2. El vínculo más antiguo de cada empresa sin administrador pasa a serlo.
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

-- 3. Solo los dos roles conocidos.
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint WHERE conname = 'chk_usuario_empresas_rol'
    ) THEN
        ALTER TABLE usuario_empresas
            ADD CONSTRAINT chk_usuario_empresas_rol CHECK (rol IN ('administrador', 'contador'));
    END IF;
END $$;
