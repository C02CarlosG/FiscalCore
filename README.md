# Plataforma de Auditoría Fiscal Preventiva
> **"Un SAT interno que detecta errores antes que la autoridad"**

## Arquitectura del Sistema

```
auditoria-fiscal/
├── backend/
│   ├── migrations/
│   │   └── 001_schema_inicial.sql     # DDL completo PostgreSQL
│   └── app/
│       ├── main.py                    # FastAPI endpoints
│       └── services/
│           ├── cfdi_parser.py         # Parser XML CFDI 3.3/4.0
│           ├── banco_parser.py        # Parser CSV/XLSX bancario
│           └── motor_fiscal.py        # Conciliación + Riesgos + Scoring
└── frontend/
    └── AuditoriaFiscalDashboard.jsx   # Dashboard React
```

## Iteraciones completadas

| # | Módulo | Estado |
|---|--------|--------|
| 1 | Modelo de base de datos PostgreSQL (DDL) | ✅ |
| 2 | Parser CFDI XML (3.3 y 4.0) | ✅ |
| 3 | Parser estados de cuenta (CSV/XLSX) | ✅ |
| 4 | Motor de conciliación banco↔CFDI | ✅ |
| 5 | Motor de riesgos (8 tipos) | ✅ |
| 6 | Sistema de scoring 0-100 | ✅ |
| 7 | API FastAPI (endpoints REST) | ✅ |
| 8 | Dashboard React | ✅ |

## Inicio rápido

### Backend
```bash
cd backend
pip install fastapi uvicorn python-multipart psycopg2-binary openpyxl
# Crear DB
psql -U postgres -c "CREATE DATABASE auditoria_fiscal;"
psql -U postgres -d auditoria_fiscal -f migrations/001_schema_inicial.sql
# Levantar API
uvicorn app.main:app --reload --port 8000
```

### Frontend
```bash
cd frontend
npm install
npm run dev
# → http://localhost:3000
```

## Tablas PostgreSQL

| Tabla | Propósito |
|-------|-----------|
| `empresas` | Registro de contribuyentes |
| `cfdi` | CFDI ingresos y egresos timbrados |
| `movimientos_bancarios` | Extracto bancario normalizado |
| `conciliaciones` | Resultado del matching banco↔CFDI |
| `riesgos` | Catálogo de 8 tipos de riesgo |
| `detecciones` | Instancias de riesgo por período |
| `recomendaciones` | Acciones concretas por detección |
| `scoring_fiscal` | Score histórico 0-100 por período |

## Riesgos detectados automáticamente

| Código | Severidad | Descripción |
|--------|-----------|-------------|
| `INGRESO_NO_FACTURADO` | 🔴 Crítico | Depósito bancario sin CFDI de ingreso |
| `GASTO_SIN_CFDI` | 🟠 Alto | Cargo bancario sin CFDI de egreso |
| `CFDI_NO_COBRADO` | 🟡 Medio | CFDI PPD sin cobrar > 30 días |
| `CFDI_NO_PAGADO` | 🟡 Medio | CFDI PPD sin pagar > 30 días |
| `DIFERENCIA_IVA` | 🟠 Alto | IVA en CFDI ≠ IVA en movimientos |
| `RFC_INVALIDO` | 🟠 Alto | RFC con formato inválido en CFDI |
| `CFDI_CANCELADO_COBRADO` | 🔴 Crítico | CFDI cancelado con movimiento bancario |
| `DIFERENCIA_TIPO_CAMBIO` | 🔵 Bajo | Tipo de cambio desactualizado |

## Scoring Fiscal

```
Score = 100
  - Penalización por riesgo crítico: -15 pts c/u
  - Penalización por riesgo alto:    -8  pts c/u
  - Penalización por riesgo medio:   -4  pts c/u
  - Penalización por baja conciliación: hasta -20 pts

Clasificación:
  85-100 → Excelente  🟢
  70-84  → Bueno      🔵
  50-69  → Regular    🟡
  0-49   → Crítico    🔴
```

## API Endpoints

```
GET  /api/v1/empresas
POST /api/v1/empresas
GET  /api/v1/dashboard/{empresa_id}?periodo=2024-10
POST /api/v1/empresas/{id}/cfdi/upload
POST /api/v1/empresas/{id}/banco/upload
GET  /api/v1/empresas/{id}/riesgos
GET  /api/v1/empresas/{id}/scoring
GET  /api/v1/empresas/{id}/conciliaciones
PATCH /api/v1/riesgos/{id}/resolver
```
