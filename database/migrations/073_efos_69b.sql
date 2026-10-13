-- 073: lista 69-B del SAT (spec 2026-10-13-efos-69b-design). Idempotente.
-- efos_importaciones: bitácora de cada intento (también los fallidos y los "sin cambios").
-- efos_lista: filas de la última importación correcta (se reemplaza completa en una transacción).
-- efos_vigente: por RFC, la fila con mayor No (el SAT enumera cronológicamente: la última es la situación vigente).

CREATE TABLE IF NOT EXISTS efos_importaciones (
    id            BIGSERIAL PRIMARY KEY,
    origen        TEXT NOT NULL CHECK (origen IN ('automatica', 'manual')),
    usuario_id    UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    fecha_archivo DATE,
    sha256        TEXT,
    filas         INT NOT NULL DEFAULT 0,
    rfc_unicos    INT NOT NULL DEFAULT 0,
    estado        TEXT NOT NULL CHECK (estado IN ('correcta', 'fallida', 'sin_cambios')),
    mensaje       TEXT,
    creado_en     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_efos_importaciones_reciente ON efos_importaciones (estado, creado_en DESC);

CREATE TABLE IF NOT EXISTS efos_lista (
    importacion_id        BIGINT NOT NULL REFERENCES efos_importaciones(id),
    no_sat                INT NOT NULL,
    rfc                   VARCHAR(13) NOT NULL,
    nombre                TEXT NOT NULL DEFAULT '',
    situacion             TEXT NOT NULL CHECK (situacion IN ('Presunto', 'Desvirtuado', 'Definitivo', 'Sentencia Favorable')),
    fecha_presunto_sat    DATE,
    fecha_presunto_dof    DATE,
    fecha_desvirtuado_sat DATE,
    fecha_desvirtuado_dof DATE,
    fecha_definitivo_sat  DATE,
    fecha_definitivo_dof  DATE,
    fecha_sentencia_sat   DATE,
    fecha_sentencia_dof   DATE,
    oficios               JSONB NOT NULL DEFAULT '{}'::jsonb,
    PRIMARY KEY (importacion_id, no_sat)
);

CREATE INDEX IF NOT EXISTS idx_efos_lista_rfc ON efos_lista (rfc);

CREATE OR REPLACE VIEW efos_vigente AS
SELECT DISTINCT ON (l.rfc) l.*
FROM efos_lista l
ORDER BY l.rfc, l.no_sat DESC;
