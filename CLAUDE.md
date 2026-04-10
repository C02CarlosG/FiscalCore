# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Proyecto

**FiscalCore** es una plataforma de auditoría fiscal mexicana para conciliación de CFDIs con estados de cuenta bancarios y detección automática de riesgos. El dominio es 100% SAT/México: RFC, CFDI 3.3/4.0, régimen fiscal, IVA/ISR/IEPS.

## Comandos

### Levantar con Docker (recomendado)
```bash
docker-compose up -d        # levanta PostgreSQL 16 + inicializa schema automáticamente
python -m uvicorn main_api:app --reload --port 8000
```

### Backend manual (Python/FastAPI)
```bash
pip install fastapi uvicorn python-multipart psycopg2-binary openpyxl pydantic python-jose bcrypt pdfplumber

# La DB se inicializa sola con docker-compose.
# Scripts SQL en orden: 001_schema_inicial.sql → 002_usuarios.sql
python -m uvicorn main_api:app --reload --port 8000
# Docs interactivos: http://localhost:8000/docs
```

### Frontend (React + Vite)
```bash
npm install
npm run dev   # → http://localhost:5173
```

## Arquitectura

```
Archivos usuario (XML/CSV/XLSX / Constancia PDF)
    → Parser Layer        cfdi_parser.py / banco_parser.py / constancia_parser.py
    → Motor Fiscal        motor_fiscal.py
    → API REST            main_api.py  (FastAPI, puerto 8000)
    → Base de datos       PostgreSQL 16 (Docker) — schema en 001_schema_inicial.sql + 002_usuarios.sql
    → Frontend            React 18 + Vite 5 (src/)
```

### Módulos backend

| Módulo | Responsabilidad |
|--------|-----------------|
| `cfdi_parser.py` | Parsea CFDI XML 3.3 y 4.0. Valida RFC, cuadre matemático, detecta namespace |
| `banco_parser.py` | Parsea CSV/XLSX bancarios. Auto-detecta encoding y columnas (6+ alias) |
| `motor_fiscal.py` | Tres motores: Conciliación (banco↔CFDI), Riesgos (8 tipos), Scoring (0–100) |
| `constancia_parser.py` | Extrae RFC, razón social, régimen, obligaciones, CP, CURP de la Constancia de Situación Fiscal PDF (pdfplumber) |
| `main_api.py` | FastAPI: auth JWT, empresas, ingesta CFDI/banco, dashboard, riesgos, scoring, parseo constancia |
| `001_schema_inicial.sql` | DDL PostgreSQL: 8 tablas + extensiones `uuid-ossp`, `pg_trgm` |
| `002_usuarios.sql` | Tabla `usuarios` + columnas extra en `empresas` (constancia_path, obligaciones JSONB, cp_fiscal, curp) |

### Módulos frontend (`src/`)

| Archivo | Responsabilidad |
|---------|-----------------|
| `main.jsx` | Raíz: enrutamiento login / register / dashboard basado en estado |
| `auth.js` | JWT en localStorage: `saveAuth`, `getToken`, `getEmpresaData`, `isLoggedIn` (verifica exp), `clearAuth` |
| `LoginPage.jsx` | Split-screen: branding izquierdo + formulario shadcn derecho. Llama `POST /api/v1/auth/login` |
| `RegisterPage.jsx` | Wizard 3 pasos: credenciales → constancia PDF → confirmación. Llama `POST /api/v1/auth/register` + `POST /api/v1/constancia/parsear` |
| `../AuditoriaFiscalDashboard.jsx` | Dashboard principal: 5 tabs (Resumen, Riesgos, Conciliación, Cargar, Diagnóstico CFDI). Parseo CFDI client-side con DOMParser |
| `components/ui/` | Componentes shadcn/ui: button, input, card, badge, label, alert, avatar, dialog, tabs, separator |
| `lib/utils.js` | Helper `cn()` (clsx + tailwind-merge) |
| `index.css` | Variables CSS dark theme (navy + cyan) + directivas Tailwind |

### Autenticación
- **JWT** con `python-jose`. Tokens con 8h de expiración.
- **Bcrypt** directo (`import bcrypt as _bcrypt`) — **NO usar passlib** (incompatibilidad con bcrypt moderno).
- Un usuario por empresa. El token contiene `empresa_id`, `rfc`, `razon_social`.
- Endpoints: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`.

### Frontend — stack y tema
- **React 18 + Vite 5 + Tailwind CSS v3 + shadcn/ui** (componentes instalados manualmente en `src/components/ui/`).
- **Paleta dark navy + cyan**: `--background: #0A0F1E`, `--primary: #06B6D4`, `--card: #0D1526`.
- **Fuentes**: Bricolage Grotesque (`font-display`), Outfit (`font-sans`), JetBrains Mono (`font-mono`) — cargadas en `index.html`.
- Variantes de `Badge` por severidad: `critical` (rojo), `high` (naranja), `medium` (amarillo), `low` (verde).

### Lógica de conciliación (`MotorConciliacion`)
- Prioridad: RFC + monto exacto → monto exacto → tolerancia ±2%
- Tolerancia exacta: ±$0.05 MXN
- Resultados: `exacto`, `parcial`, `sin_cfdi`, `sin_movimiento`

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
score -= Σ penalizaciones  (Crítico=-15, Alto=-8, Medio=-4, Bajo=-1)
score -= int((1 - %_conciliado) * 20)   # hasta -20 por baja conciliación
score ∈ [0, 100]
```

## Estado actual del proyecto

- ✅ Schema DB, parsers, motor fiscal y API — diseñados y funcionales
- ✅ Auth JWT multiempresa — registro con Constancia PDF, login, token
- ✅ Docker Compose — PostgreSQL 16 con auto-init de scripts SQL
- ✅ Frontend migrado a Tailwind CSS v3 + shadcn/ui (tema dark navy + cyan)
- ⚠️ **La API aún devuelve datos mock** — no conectada a PostgreSQL real
- ⚠️ **El dashboard no llama a la API** — demo con datos hardcoded
- Pendiente: integración end-to-end (DB real → API → Frontend)

## Convenciones importantes

- **Precisión financiera**: Usar siempre `Decimal` (no `float`) para montos
- **RFC mexicano**: `AAAA######XXX` — regex de validación en `cfdi_parser.py` y `main_api.py`; reutilizar siempre
- **CFDI**: Versión 3.3 o 4.0; namespaces XML distintos — ver `CFDIParser._detect_namespace()`
- **Severidades**: Los 4 niveles tienen pesos fijos en `MotorScoring`; cambiarlos afecta scores históricos
- **bcrypt**: Usar siempre `import bcrypt as _bcrypt` directamente, nunca a través de passlib
- **Tailwind**: Clases utilitarias en JSX; nunca `style={{}}` salvo para valores dinámicos (colores de severidad, SVG)
