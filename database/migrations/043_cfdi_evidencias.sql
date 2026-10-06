-- ============================================================
-- Migración 043: evidencias (archivos adjuntos) por CFDI (F3.6, carril A)
-- Idempotente: CREATE ... IF NOT EXISTS.
--
-- El archivo vive en la base (bytea): el despliegue no garantiza disco persistente
-- y el respaldo de la base ya lo incluye. El tope (5 MB por archivo, 20 por CFDI)
-- se valida en el servidor; aquí el CHECK es la última defensa.
-- ============================================================

CREATE TABLE IF NOT EXISTS cfdi_evidencias (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cfdi_id     UUID NOT NULL REFERENCES cfdi(id) ON DELETE CASCADE,
    empresa_id  UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id  UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    nombre      VARCHAR(120) NOT NULL,
    tipo_mime   VARCHAR(100) NOT NULL,
    tamano      INTEGER NOT NULL CHECK (tamano > 0 AND tamano <= 5242880),
    sha256      CHAR(64) NOT NULL,
    contenido   BYTEA NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cfdi_evidencias_cfdi ON cfdi_evidencias (cfdi_id, created_at);
