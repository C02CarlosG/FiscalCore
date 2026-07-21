-- ============================================================
-- Migración 024: configuración anual de ISR provisional por empresa
-- - Coeficiente de utilidad (Art. 14-I LISR): se fija una vez al año
--   a partir del ejercicio anterior.
-- - Insumos del cálculo mensual: pérdidas fiscales pendientes, PTU
--   pagada en el ejercicio y tasa de ISR (30% personas morales).
--
-- El cálculo de la cédula de ISR es on-the-fly (como IVA/DIOT); esta
-- tabla solo persiste los parámetros anuales que NO salen de los CFDIs.
--
-- Idempotente: CREATE TABLE / CREATE INDEX IF NOT EXISTS
-- ============================================================

CREATE TABLE IF NOT EXISTS config_isr_empresa (
    id                   UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id           UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    ejercicio            INT  NOT NULL,
    -- Coeficiente de utilidad = utilidad fiscal / ingresos nominales del
    -- ejercicio anterior. Rango típico 0..1; NUMERIC(6,4) admite 0.0000..99.9999.
    coeficiente_utilidad NUMERIC(6,4)  NOT NULL,
    -- Pérdidas fiscales de ejercicios anteriores pendientes de amortizar.
    perdidas_pendientes  NUMERIC(18,2) NOT NULL DEFAULT 0,
    -- PTU pagada en el ejercicio (deducible del pago provisional, Art. 14).
    ptu_pagada           NUMERIC(18,2) NOT NULL DEFAULT 0,
    -- Tasa de ISR de personas morales (Art. 9 LISR): 30%.
    tasa_isr             NUMERIC(4,2)  NOT NULL DEFAULT 0.30,
    created_at           TIMESTAMPTZ DEFAULT NOW(),
    updated_at           TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (empresa_id, ejercicio)
);

CREATE INDEX IF NOT EXISTS idx_config_isr_empresa ON config_isr_empresa (empresa_id);

COMMENT ON TABLE  config_isr_empresa IS 'Parámetros anuales del pago provisional de ISR por empresa (Art. 14 LISR); lo que no se deriva de los CFDIs';
COMMENT ON COLUMN config_isr_empresa.coeficiente_utilidad IS 'CU = utilidad fiscal / ingresos nominales del ejercicio anterior (Art. 14-I LISR)';
COMMENT ON COLUMN config_isr_empresa.perdidas_pendientes IS 'Pérdidas fiscales de ejercicios anteriores pendientes de aplicar';
COMMENT ON COLUMN config_isr_empresa.ptu_pagada IS 'PTU pagada en el ejercicio, disminuible de la utilidad estimada del pago provisional';
COMMENT ON COLUMN config_isr_empresa.tasa_isr IS 'Tasa de ISR de personas morales (0.30 = 30%, Art. 9 LISR)';
