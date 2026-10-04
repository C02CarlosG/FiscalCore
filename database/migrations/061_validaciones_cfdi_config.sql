-- ============================================================
-- Migración 061: Configuración de las validaciones de CFDI (V1, carril D)
-- Idempotente: CREATE TABLE IF NOT EXISTS.
--
-- Una fila por empresa con las validaciones apagadas y el umbral de efectivo:
-- {"inactivas": ["pue_con_rep"], "umbral_efectivo": "2000.00"}. Sin fila, todas
-- las validaciones están activas con el umbral de 2,000 (art. 27-III LISR).
-- ============================================================

CREATE TABLE IF NOT EXISTS validaciones_cfdi_config (
    empresa_id  UUID PRIMARY KEY REFERENCES empresas(id) ON DELETE CASCADE,
    config      JSONB NOT NULL DEFAULT '{}'::jsonb,
    usuario_id  UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE validaciones_cfdi_config IS
    'Validaciones de CFDI apagadas y umbral de efectivo por empresa (V1).';
