-- 032: seguridad de cuentas — correos únicos sin distinguir mayúsculas y versión de sesión.
-- Idempotente. NO borra ni fusiona cuentas: si hay correos que solo difieren en
-- mayúsculas/minúsculas, falla con la lista para que se resuelvan a mano.

DO $$
DECLARE
    duplicados TEXT;
BEGIN
    SELECT string_agg(correo || ' (' || n || ' cuentas)', ', ')
      INTO duplicados
      FROM (
          SELECT lower(btrim(email)) AS correo, count(*) AS n
            FROM usuarios
           GROUP BY lower(btrim(email))
          HAVING count(*) > 1
      ) d;

    IF duplicados IS NOT NULL THEN
        RAISE EXCEPTION
            'Migración 032 detenida: hay correos duplicados al ignorar mayúsculas: %. Resuélvelos a mano (no se borra ninguna cuenta) y reintenta.',
            duplicados;
    END IF;
END $$;

-- Normaliza los correos existentes (ya sin duplicados posibles).
UPDATE usuarios SET email = lower(btrim(email)) WHERE email <> lower(btrim(email));

CREATE UNIQUE INDEX IF NOT EXISTS idx_usuarios_email_lower ON usuarios (lower(email));

-- Cada cambio de contraseña o desactivación incrementa la versión: los JWT emitidos con
-- una versión anterior dejan de valer.
ALTER TABLE usuarios ADD COLUMN IF NOT EXISTS token_version INTEGER NOT NULL DEFAULT 0;
