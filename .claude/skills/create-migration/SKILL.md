---
name: create-migration
description: Crea el siguiente archivo de migración SQL numerado para FiscalCore con boilerplate idempotente
---

Cuando el usuario invoque `/create-migration <descripcion>`, sigue exactamente estos pasos:

## Pasos

1. **Encuentra el número siguiente**: Lee los archivos en `database/migrations/` y detecta el número más alto (actualmente 018). El siguiente es ese número + 1, con cero a la izquierda de dos dígitos mínimo (019, 020, 021...).

2. **Construye el nombre**: `NNN_<descripcion>.sql` donde `<descripcion>` usa guiones bajos y minúsculas (ej: `019_agregar_telefono_empresa.sql`).

3. **Crea el archivo** en `database/migrations/` con esta estructura:

```sql
-- ============================================================
-- Migración NNN: <descripcion legible>
-- <una línea explicando qué hace y por qué>
--
-- Idempotente: <indicar la estrategia usada>
-- ============================================================

<SQL idempotente aquí>
```

## Patrones idempotentes a usar según el caso

**Columna nueva en tabla existente:**
```sql
ALTER TABLE nombre_tabla
  ADD COLUMN IF NOT EXISTS nombre_columna TIPO DEFAULT valor;

COMMENT ON COLUMN nombre_tabla.nombre_columna
  IS 'Descripción de la columna';
```

**Tabla nueva:**
```sql
CREATE TABLE IF NOT EXISTS nombre_tabla (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    ...
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_nombre_tabla_campo
    ON nombre_tabla(campo);
```

**Índice nuevo:**
```sql
CREATE INDEX IF NOT EXISTS idx_nombre
    ON tabla(columna);
```

**Constraint nuevo (sin duplicate_constraint en PG < 15):**
```sql
DO $$ BEGIN
  ALTER TABLE tabla ADD CONSTRAINT nombre_constraint ...;
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
```

**Columna en tabla con muchas filas (sin bloquear):**
```sql
ALTER TABLE tabla
  ADD COLUMN IF NOT EXISTS columna TIPO;  -- sin DEFAULT para evitar rewrite

UPDATE tabla SET columna = valor_default WHERE columna IS NULL;

ALTER TABLE tabla ALTER COLUMN columna SET DEFAULT valor_default;
```

## Reglas de este proyecto

- Todas las migraciones deben ser **completamente idempotentes** — se pueden correr múltiples veces sin error
- `init_db()` en `backend/db.py` aplica todas las migraciones al startup en Railway
- Los tipos UUID usan `uuid_generate_v4()` (extensión `uuid-ossp` ya instalada)
- Los JSONB deben tener un `DEFAULT '[]'::jsonb` o `DEFAULT '{}'::jsonb`
- Siempre agrega `COMMENT ON COLUMN` para columnas con lógica de negocio no obvia

## Al terminar

Confirma: "Migración `NNN_descripcion.sql` creada en `database/migrations/`" y muestra el SQL completo generado.
Si hay dudas sobre el tipo de datos o la tabla destino, pregunta antes de crear el archivo.
