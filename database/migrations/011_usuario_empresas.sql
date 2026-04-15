-- 011_usuario_empresas.sql
-- Modelo usuario-céntrico: 1 contador → N empresas
-- Idempotente (safe para re-ejecutar en Railway startup)

-- Tabla de relación M:N usuario ↔ empresa
CREATE TABLE IF NOT EXISTS usuario_empresas (
    usuario_id UUID NOT NULL REFERENCES usuarios(id) ON DELETE CASCADE,
    empresa_id UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    rol        VARCHAR(50) NOT NULL DEFAULT 'contador',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (usuario_id, empresa_id)
);

CREATE INDEX IF NOT EXISTS idx_ue_usuario ON usuario_empresas(usuario_id);
CREATE INDEX IF NOT EXISTS idx_ue_empresa ON usuario_empresas(empresa_id);

-- Migrar relaciones existentes (usuarios con empresa_id ya asignado)
INSERT INTO usuario_empresas (usuario_id, empresa_id)
SELECT id, empresa_id
FROM usuarios
WHERE empresa_id IS NOT NULL
ON CONFLICT DO NOTHING;

-- Hacer empresa_id nullable en usuarios (ya no es la fuente de verdad)
ALTER TABLE usuarios ALTER COLUMN empresa_id DROP NOT NULL;
