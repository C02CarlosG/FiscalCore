-- ============================================================
-- Migración 055: restricciones de las tablas del ISR base flujo (F7.1) para bases ya creadas
-- Idempotente: las restricciones se agregan solo si no existen; los datos previos se normalizan antes.
--
-- isr_ajustes.motivo: obligatorio (no vacío).
-- isr_config_flujo.pct_nomina_exenta: solo 0.47 (por defecto) o 0.53 (LISR 28-XXX).
-- ============================================================
UPDATE isr_ajustes SET motivo = 'Sin motivo registrado' WHERE length(btrim(motivo)) = 0;
UPDATE isr_config_flujo SET pct_nomina_exenta = 0.47 WHERE pct_nomina_exenta NOT IN (0.47, 0.53);

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'isr_ajustes_motivo_no_vacio') THEN
        ALTER TABLE isr_ajustes ADD CONSTRAINT isr_ajustes_motivo_no_vacio CHECK (length(btrim(motivo)) > 0);
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'isr_config_flujo_pct_47_o_53') THEN
        ALTER TABLE isr_config_flujo ADD CONSTRAINT isr_config_flujo_pct_47_o_53 CHECK (pct_nomina_exenta IN (0.47, 0.53));
    END IF;
END
$$;
