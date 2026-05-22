-- ============================================================
-- Migración 019: Tabla de patrones de riesgos fiscales
-- Habilita búsqueda híbrida (similitud textual + filtros)
-- para aprendizaje de resoluciones históricas.
-- ============================================================

CREATE TABLE IF NOT EXISTS risk_patterns (
    id               UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id       UUID REFERENCES empresas(id) ON DELETE CASCADE,

    -- Clasificación del patrón
    tipo_riesgo      VARCHAR(30) NOT NULL,
    severidad        VARCHAR(10) CHECK (severidad IN ('critico','alto','medio','bajo')),
    categoria        VARCHAR(50),
    periodo          VARCHAR(7),

    -- Texto indexable para similitud trigrama
    descripcion      TEXT NOT NULL,
    contexto         TEXT,

    -- Resolución aprendida
    resolucion       TEXT,
    fue_falso_positivo BOOLEAN DEFAULT FALSE,

    -- Metadata numérica para filtros
    monto_afectado   NUMERIC(18,2),
    rfc_relacionado  VARCHAR(13),

    -- Calidad del patrón (0.0–1.0)
    confianza        NUMERIC(3,2) DEFAULT 1.0 CHECK (confianza BETWEEN 0 AND 1),
    uso_count        INTEGER DEFAULT 0,

    deteccion_id     UUID REFERENCES detecciones(id) ON DELETE SET NULL,

    created_at       TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_rp_tipo     ON risk_patterns (tipo_riesgo);
CREATE INDEX IF NOT EXISTS idx_rp_severidad ON risk_patterns (severidad);
CREATE INDEX IF NOT EXISTS idx_rp_categoria ON risk_patterns (categoria);
CREATE INDEX IF NOT EXISTS idx_rp_empresa  ON risk_patterns (empresa_id);
CREATE INDEX IF NOT EXISTS idx_rp_desc_trgm ON risk_patterns USING gin (descripcion gin_trgm_ops);
CREATE INDEX IF NOT EXISTS idx_rp_ctx_trgm  ON risk_patterns USING gin (contexto gin_trgm_ops);
