-- ============================================================
-- Migración 055: restricciones de las tablas del ISR base flujo (F7.1) para bases ya creadas
-- Idempotente: las restricciones se agregan solo si no existen; los datos previos se normalizan antes.
--
-- isr_ajustes.motivo: obligatorio (no vacío).
-- isr_config_flujo.pct_nomina_exenta: solo 0.47 (por defecto) o 0.53 (LISR 28-XXX).
-- ============================================================
UPDATE isr_ajustes SET motivo = 'Sin motivo registrado' WHERE length(btrim(motivo)) = 0;
DO $$
DECLARE
    fila RECORD;
BEGIN
    -- Los porcentajes fuera de 0.47/0.53 se normalizan a 0.47; cada cambio queda en el log del servidor
    FOR fila IN SELECT empresa_id, ejercicio, pct_nomina_exenta FROM isr_config_flujo WHERE pct_nomina_exenta NOT IN (0.47, 0.53) LOOP
        RAISE NOTICE '055: empresa % ejercicio %: porcentaje de nómina exenta % cambiado a 0.47',
            fila.empresa_id, fila.ejercicio, fila.pct_nomina_exenta;
    END LOOP;
    UPDATE isr_config_flujo SET pct_nomina_exenta = 0.47 WHERE pct_nomina_exenta NOT IN (0.47, 0.53);
END
$$;

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
