-- ============================================================
-- Migración 023: categorización de movimientos bancarios
-- - Catálogo de subcategorías por empresa
-- - Reglas (base por palabra clave + aprendidas por historial)
-- - Columnas de categoría/RFC manual en movimientos_bancarios
--
-- Idempotente: ADD COLUMN/CREATE TABLE/CREATE INDEX IF NOT EXISTS
-- ============================================================

CREATE TABLE IF NOT EXISTS categorias_movimiento (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id  UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    nombre      VARCHAR(80) NOT NULL,
    tipo        VARCHAR(10) NOT NULL DEFAULT 'ambos'
                CHECK (tipo IN ('deposito','retiro','ambos')),
    color       VARCHAR(9) DEFAULT '#6B7280',
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (empresa_id, nombre)
);

CREATE INDEX IF NOT EXISTS idx_catmov_empresa ON categorias_movimiento (empresa_id);

CREATE TABLE IF NOT EXISTS reglas_categorizacion (
    id           UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id   UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    palabra_clave VARCHAR(255) NOT NULL,
    tipo_match   VARCHAR(10) NOT NULL DEFAULT 'concepto'
                 CHECK (tipo_match IN ('concepto','rfc')),
    categoria_id UUID NOT NULL REFERENCES categorias_movimiento(id) ON DELETE CASCADE,
    origen       VARCHAR(10) NOT NULL DEFAULT 'regla'
                 CHECK (origen IN ('regla','historial')),
    peso         INT NOT NULL DEFAULT 1,
    tipo         VARCHAR(10) NOT NULL DEFAULT 'ambos'
                 CHECK (tipo IN ('deposito','retiro','ambos')),
    created_at   TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (empresa_id, palabra_clave, tipo_match)
);

CREATE INDEX IF NOT EXISTS idx_regla_empresa ON reglas_categorizacion (empresa_id);

ALTER TABLE movimientos_bancarios
  ADD COLUMN IF NOT EXISTS categoria_id         UUID REFERENCES categorias_movimiento(id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS categoria_confirmada BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS rfc_manual           BOOLEAN DEFAULT FALSE;

COMMENT ON TABLE categorias_movimiento IS 'Catálogo de subcategorías de movimientos por empresa';
COMMENT ON TABLE reglas_categorizacion IS 'Reglas de sugerencia: base por palabra clave e historial confirmado';
COMMENT ON COLUMN movimientos_bancarios.categoria_confirmada IS 'TRUE si el usuario confirmó la subcategoría (vs solo sugerida)';
COMMENT ON COLUMN movimientos_bancarios.rfc_manual IS 'TRUE si rfc_detectado fue capturado manualmente';
