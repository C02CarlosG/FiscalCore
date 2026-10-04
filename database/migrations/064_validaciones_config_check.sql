-- ============================================================
-- Migración 064: CHECK de objeto en validaciones_cfdi_config (V1, carril D)
-- Idempotente: corrige las filas y agrega el CHECK solo si la tabla no tiene ya
-- uno equivalente.
--
-- La 061 declara CHECK (jsonb_typeof(config) = 'object') dentro de
-- CREATE TABLE IF NOT EXISTS, así que las bases donde la tabla ya existía antes
-- de ese cambio se quedaron sin él. Aquí se agrega a esas bases.
-- ============================================================

-- 1. Cualquier configuración que no sea objeto vuelve a la configuración por defecto.
UPDATE validaciones_cfdi_config
SET config = '{}'::jsonb
WHERE jsonb_typeof(config) <> 'object';

-- 2. El CHECK, si la tabla no tiene ya uno sobre jsonb_typeof(config).
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conrelid = 'validaciones_cfdi_config'::regclass
          AND contype = 'c'
          AND pg_get_constraintdef(oid) LIKE '%jsonb_typeof(config)%'
    ) THEN
        ALTER TABLE validaciones_cfdi_config
            ADD CONSTRAINT chk_validaciones_cfdi_config_objeto CHECK (jsonb_typeof(config) = 'object');
    END IF;
EXCEPTION WHEN duplicate_object THEN
    NULL;
END $$;
