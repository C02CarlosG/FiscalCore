-- 072: criterio de efectivo por empresa (spec 2026-10-13-criterio-efectivo-design).
-- 'legal': efectivo mayor a $2,000 no se acredita ni se deduce (LIVA 5-III, LISR 27-III).
-- 'estricto': ningún pago en efectivo se acredita ni se deduce.
-- Idempotente: se puede ejecutar en cada arranque.

ALTER TABLE empresas ADD COLUMN IF NOT EXISTS criterio_efectivo TEXT NOT NULL DEFAULT 'legal';

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'empresas_criterio_efectivo_check') THEN
        ALTER TABLE empresas
            ADD CONSTRAINT empresas_criterio_efectivo_check CHECK (criterio_efectivo IN ('legal', 'estricto'));
    END IF;
END $$;
