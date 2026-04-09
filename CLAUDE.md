# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proyecto

**FiscalCore** es una plataforma de auditoría fiscal mexicana para conciliación de CFDIs con estados de cuenta bancarios y detección automática de riesgos. El dominio es 100% SAT/México: RFC, CFDI 3.3/4.0, régimen fiscal, IVA/ISR/IEPS.

## Comandos

### Backend (Python/FastAPI)
```bash
# Instalar dependencias
pip install fastapi uvicorn python-multipart psycopg2-binary openpyxl pydantic

# Inicializar base de datos
psql -U postgres -c "CREATE DATABASE auditoria_fiscal;"
psql -U postgres -d auditoria_fiscal -f 001_schema_inicial.sql

# Ejecutar API
uvicorn main_api:app --reload --port 8000

# Ver docs interactivos
# http://localhost:8000/docs
```

### Frontend (React)
```bash
# El archivo AuditoriaFiscalDashboard.jsx requiere entorno React con bundler
npm install
npm run dev  # → http://localhost:3000
```

> **Nota**: No existe `package.json` ni `requirements.txt` aún. Los módulos están todos en la raíz del proyecto.

## Arquitectura

Todos los módulos principales viven en la raíz del proyecto (sin separación backend/frontend de carpetas). El flujo de datos es lineal:

```
Archivos usuario (XML/CSV/XLSX)
    → Parser Layer        cfdi_parser.py / banco_parser.py
    → Motor Fiscal        motor_fiscal.py
    → API REST            main_api.py
    → Base de datos       PostgreSQL (schema en 001_schema_inicial.sql)
    → Dashboard           AuditoriaFiscalDashboard.jsx
```

### Módulos clave

| Módulo | Responsabilidad |
|--------|-----------------|
| `cfdi_parser.py` | Parsea CFDI XML 3.3 y 4.0. Valida RFC (regex SAT), cuadre matemático, detecta namespace dinámicamente |
| `banco_parser.py` | Parsea CSV/XLSX bancarios. Auto-detecta encoding (UTF-8/Latin-1/CP1252) y columnas (6+ alias soportados). Extrae RFC de conceptos |
| `motor_fiscal.py` | Tres motores: **Conciliación** (matching banco↔CFDI), **Riesgos** (8 tipos), **Scoring** (0-100) |
| `main_api.py` | FastAPI con endpoints para empresas, ingesta de archivos, dashboard, riesgos y scoring |
| `001_schema_inicial.sql` | DDL completo PostgreSQL con 8 tablas + extensiones `uuid-ossp`, `pg_trgm` |

### Lógica de conciliación (`MotorConciliacion`)
- Prioridad: RFC + monto exacto → monto exacto → tolerancia ±2%
- Tolerancia exacta: ±$0.05 MXN
- Cuatro resultados posibles: `exacto`, `parcial`, `sin_cfdi`, `sin_movimiento`

### Riesgos detectados (`MotorRiesgos`) — 8 tipos
| Clave | Severidad |
|-------|-----------|
| `INGRESO_NO_FACTURADO` | Crítico |
| `CFDI_CANCELADO_COBRADO` | Crítico |
| `GASTO_SIN_CFDI` | Alto |
| `DIFERENCIA_IVA` | Alto |
| `RFC_INVALIDO` | Alto |
| `CFDI_NO_COBRADO` | Medio |
| `CFDI_NO_PAGADO` | Medio |
| `DIFERENCIA_TIPO_CAMBIO` | Bajo |

### Fórmula de scoring (`MotorScoring`)
```
score = 100
score -= Σ penalizaciones_por_riesgo   (Crítico=-15, Alto=-8, Medio=-4, Bajo=-1)
score -= int((1 - %_conciliado) * 20)  # hasta -20 por baja conciliación
score ∈ [0, 100]
```

## Estado actual del proyecto

- ✅ Schema DB, parsers, motor fiscal y API diseñados (8 iteraciones completas)
- **La API devuelve datos mock** — no está conectada a PostgreSQL
- **El dashboard no hace llamadas a la API** — es demo-driven con datos hardcoded
- Pendiente: integración end-to-end (DB → API → Frontend)

## Convenciones importantes

- **Precisión financiera**: Usar siempre `Decimal` (no `float`) para montos monetarios
- **RFC mexicano**: Formato `AAAA######XXX` — hay regex de validación en `cfdi_parser.py` y `main_api.py`; reutilizarlo siempre
- **CFDI**: Pueden ser versión 3.3 o 4.0; los namespaces XML difieren — ver `CFDIParser._detect_namespace()`
- **Severidades de riesgo**: Los 4 niveles (`critico`, `alto`, `medio`, `bajo`) tienen pesos fijos en `MotorScoring`; cambiarlos afecta todos los scores históricos
