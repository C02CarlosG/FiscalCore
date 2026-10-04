-- ============================================================
-- Migración 053: parámetros del ISR base flujo por empresa y ejercicio (F7.1)
-- Idempotente: CREATE TABLE IF NOT EXISTS.
--
-- pct_nomina_exenta: porcentaje deducible de las prestaciones exentas de la nómina (LISR 28-XXX):
-- 47 % por defecto; 53 % si la empresa acredita que no disminuyeron respecto al ejercicio anterior.
-- ============================================================
CREATE TABLE IF NOT EXISTS isr_config_flujo (
    id                 UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id         UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    ejercicio          INT  NOT NULL CHECK (ejercicio BETWEEN 2000 AND 2099),
    pct_nomina_exenta  NUMERIC(5,4) NOT NULL DEFAULT 0.47 CHECK (pct_nomina_exenta BETWEEN 0 AND 1),
    usuario_id         UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, ejercicio)
);
