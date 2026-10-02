-- ============================================================
-- Migración 029: Ampliar cfdi.serie (VARCHAR(10) -> VARCHAR(25))
-- Idempotente: solo altera la columna mientras mida menos de 25.
--
-- Bug: el Anexo 20 permite Serie de 1 a 25 caracteres, pero la columna
-- seguía en VARCHAR(10) desde la 001. Un CFDI con serie más larga lanzaba
-- "value too long for type character varying(10)" y se quedaba sin
-- importar — visto en la descarga masiva de recibidos del 2026-10-01.
-- ============================================================

DO $$ BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = 'cfdi' AND column_name = 'serie'
          AND character_maximum_length < 25
    ) THEN
        ALTER TABLE cfdi ALTER COLUMN serie TYPE VARCHAR(25);
    END IF;
END $$;
