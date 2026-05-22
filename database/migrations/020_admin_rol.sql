-- 020_admin_rol.sql
-- Añade columna rol a usuarios (admin | contador). Idempotente.

ALTER TABLE usuarios
    ADD COLUMN IF NOT EXISTS rol VARCHAR(50) NOT NULL DEFAULT 'contador';

ALTER TABLE usuarios
    DROP CONSTRAINT IF EXISTS chk_usuarios_rol;

ALTER TABLE usuarios
    ADD CONSTRAINT chk_usuarios_rol CHECK (rol IN ('admin', 'contador'));
