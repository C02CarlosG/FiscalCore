---
name: nueva-migracion
description: Crea una migración SQL idempotente para FiscalCore con el número siguiente correcto y los patrones de seguridad establecidos del proyecto
---

# Skill: nueva-migracion

Crea una migración SQL nueva en `database/migrations/` siguiendo las convenciones de FiscalCore.

## Uso

El usuario invoca `/nueva-migracion <descripcion>` donde descripcion describe qué hace la migración (ej. `fiel_config`, `tipos_riesgo_extra`, `sesiones_sat`).

## Pasos obligatorios

### 1. Determinar el número siguiente

Lee el directorio `database/migrations/` y encuentra el número más alto:

```bash
ls database/migrations/ | sort | tail -5
```

El nuevo archivo debe ser `NNN_<descripcion>.sql` donde NNN = número actual + 1 con padding de 3 dígitos (ej. si el último es `024_coeficiente_utilidad.sql`, el nuevo es `025_`).

### 2. Generar el archivo SQL

Crea `database/migrations/NNN_<descripcion>.sql` con esta estructura obligatoria:

```sql
-- Migración NNN: <descripcion en español>
-- Idempotente: segura para ejecutar múltiples veces

-- Patrón para NUEVAS TABLAS:
CREATE TABLE IF NOT EXISTS nombre_tabla (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    -- columnas...
    creado_en TIMESTAMPTZ DEFAULT NOW()
);

-- Patrón para NUEVAS COLUMNAS:
DO $$ BEGIN
    ALTER TABLE nombre_tabla ADD COLUMN nombre_columna TIPO DEFAULT valor;
EXCEPTION WHEN duplicate_column THEN NULL;
END $$;

-- Patrón para NUEVOS ÍNDICES:
CREATE INDEX IF NOT EXISTS idx_tabla_columna ON nombre_tabla(columna);

-- Patrón para NUEVOS VALORES EN ENUM (si aplica):
DO $$ BEGIN
    ALTER TYPE nombre_enum ADD VALUE 'nuevo_valor';
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;
```

### 3. Reglas invariantes del proyecto

- **SIEMPRE idempotente**: Toda instrucción debe poder ejecutarse N veces sin error
- **UUIDs**: Usar `uuid_generate_v4()` (extensión ya instalada desde migración 001)
- **Timestamps**: Usar `TIMESTAMPTZ` (no `TIMESTAMP`)
- **JSONB**: Para campos estructurados o arrays (no JSON)
- **Índices GIN**: Para columnas JSONB con búsquedas frecuentes
- **Comentario de tabla**: `COMMENT ON TABLE` cuando la semántica no es obvia
- **Precisión financiera**: Columnas de montos como `NUMERIC(15,2)`, nunca `FLOAT`

### 4. Verificar la migración

Después de crear el archivo, verifica que sea idempotente revisando que cada operación `ALTER TABLE` use protección contra duplicados.

## Ejemplo de output esperado

Para `/nueva-migracion config_sat_periodos`:

```
Creando: database/migrations/025_config_sat_periodos.sql

Número siguiente: 025 (último era 024_coeficiente_utilidad.sql)

Contenido generado con:
- CREATE TABLE IF NOT EXISTS config_sat_periodos (...)
- Índice en empresa_id
- Restricción UNIQUE en (empresa_id, periodo)
```
