-- ============================================================
-- Migración 063: Planes y suscripciones (M7.1, carril D)
-- Idempotente: CREATE ... IF NOT EXISTS e INSERT ... ON CONFLICT DO NOTHING.
--
-- Sin cobro en línea (decisión de Carlos, 2026-10-04): un administrador de la
-- plataforma asigna el plan a cada cuenta y el plan solo limita el número de RFC.
-- Los planes se siembran con valores de ejemplo; ON CONFLICT DO NOTHING evita
-- pisarlos cuando ya se editaron desde la app.
-- ============================================================

CREATE TABLE IF NOT EXISTS planes (
    clave           VARCHAR(30) PRIMARY KEY CHECK (clave ~ '^[a-z][a-z0-9_]{1,29}$'),
    nombre          VARCHAR(80) NOT NULL,
    precio_mensual  NUMERIC(12,2) NOT NULL CHECK (precio_mensual >= 0),  -- MXN, sin IVA
    max_rfc         INTEGER CHECK (max_rfc IS NULL OR max_rfc >= 0),     -- NULL = ilimitado
    por_defecto     BOOLEAN NOT NULL DEFAULT FALSE,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    orden           INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Un solo plan por defecto (el que tiene quien no tiene suscripción vigente).
CREATE UNIQUE INDEX IF NOT EXISTS uq_planes_por_defecto ON planes (por_defecto) WHERE por_defecto;

-- Si alguien borró «prueba» y marcó otro plan como por defecto, al reinsertarla no se
-- marca (chocaría con uq_planes_por_defecto y detendría el arranque).
INSERT INTO planes (clave, nombre, precio_mensual, max_rfc, por_defecto, orden)
SELECT v.clave, v.nombre, v.precio_mensual, v.max_rfc,
       v.por_defecto AND NOT EXISTS (SELECT 1 FROM planes p WHERE p.por_defecto), v.orden
FROM (VALUES
    ('prueba',    'Prueba',    0,    1,    TRUE,  10),
    ('basico',    'Básico',    499,  3,    FALSE, 20),
    ('despacho',  'Despacho',  1499, 15,   FALSE, 30),
    ('ilimitado', 'Ilimitado', 3999, NULL, FALSE, 40)
) AS v (clave, nombre, precio_mensual, max_rfc, por_defecto, orden)
ON CONFLICT (clave) DO NOTHING;

CREATE TABLE IF NOT EXISTS suscripciones (
    usuario_id     UUID PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    plan_clave     VARCHAR(30) NOT NULL REFERENCES planes(clave),
    estado         VARCHAR(20) NOT NULL DEFAULT 'activa'
                   CHECK (estado IN ('activa', 'suspendida', 'cancelada')),
    vigente_hasta  DATE,
    notas          TEXT,
    asignada_por   UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_suscripciones_plan ON suscripciones (plan_clave);

COMMENT ON TABLE planes IS 'Catálogo de planes (M7.1). Precio mensual en MXN sin IVA; max_rfc NULL = ilimitado.';
COMMENT ON TABLE suscripciones IS 'Plan asignado a cada cuenta de usuario (M7.1, asignación manual).';
