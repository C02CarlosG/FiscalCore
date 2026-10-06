-- ============================================================
-- Migración 042: etiquetas y comentarios por CFDI (F3.6, carril A)
-- Idempotente: CREATE ... IF NOT EXISTS.
--
-- Las etiquetas pertenecen a la empresa (nombre único sin distinguir mayúsculas).
-- Etiquetas y comentarios se enlazan por cfdi_id: un reproceso del XML (que solo
-- reescribe el detalle extraído) no los toca. Al borrar una etiqueta o un CFDI se
-- borran en cascada sus asignaciones.
-- ============================================================

CREATE TABLE IF NOT EXISTS etiquetas (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id  UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    nombre      VARCHAR(40) NOT NULL CHECK (btrim(nombre) <> ''),
    color       VARCHAR(7) NOT NULL DEFAULT '#64748b' CHECK (color ~ '^#[0-9a-fA-F]{6}$'),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_etiquetas_empresa_nombre ON etiquetas (empresa_id, lower(nombre));

CREATE TABLE IF NOT EXISTS cfdi_etiquetas (
    cfdi_id      UUID NOT NULL REFERENCES cfdi(id) ON DELETE CASCADE,
    etiqueta_id  UUID NOT NULL REFERENCES etiquetas(id) ON DELETE CASCADE,
    usuario_id   UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (cfdi_id, etiqueta_id)
);
CREATE INDEX IF NOT EXISTS idx_cfdi_etiquetas_etiqueta ON cfdi_etiquetas (etiqueta_id, cfdi_id);

CREATE TABLE IF NOT EXISTS cfdi_comentarios (
    id          UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    cfdi_id     UUID NOT NULL REFERENCES cfdi(id) ON DELETE CASCADE,
    empresa_id  UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    usuario_id  UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    texto       TEXT NOT NULL CHECK (btrim(texto) <> '' AND char_length(texto) <= 2000),
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_cfdi_comentarios_cfdi ON cfdi_comentarios (cfdi_id, created_at);
