-- ============================================================
-- Migración 057: PTU pagada y pérdidas pendientes para el pago provisional del ISR por flujo (F7.3)
-- Idempotente: ADD COLUMN IF NOT EXISTS.
--
-- ptu_pagada: PTU pagada en el ejercicio, resta de la utilidad del pago provisional (Art. 109 LISR).
-- perdidas_pendientes: pérdidas fiscales de ejercicios anteriores pendientes de aplicar.
-- ============================================================
ALTER TABLE isr_config_flujo
    ADD COLUMN IF NOT EXISTS ptu_pagada          NUMERIC(16,2) NOT NULL DEFAULT 0 CHECK (ptu_pagada >= 0),
    ADD COLUMN IF NOT EXISTS perdidas_pendientes NUMERIC(16,2) NOT NULL DEFAULT 0 CHECK (perdidas_pendientes >= 0);
