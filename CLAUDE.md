# CLAUDE.md

Este archivo guía a Claude Code al trabajar en este repositorio.

## Proyecto

**FiscalCore** es una plataforma de auditoría fiscal mexicana para conciliación de CFDIs con estados de cuenta bancarios y detección automática de riesgos. El dominio es 100% SAT/México: RFC, CFDI 3.3/4.0, régimen fiscal, IVA/ISR/IEPS.
No es un sistema de visualización de datos fiscales.

Es un sistema de decisión para contadores de despacho.

El sistema debe ayudar a:

- Preparar el cierre fiscal mensual
- Reducir carga operativa
- Prevenir inconsistencias ante el SAT
- Mejorar flujo de efectivo del cliente

Antes de proponer cualquier solución, Claude debe evaluar:

1. ¿Reduce tiempo del contador?
2. ¿Reduce riesgo fiscal?
3. ¿Mejora flujo de efectivo?

Si la respuesta es NO, la solución es inválida.

Claude NO debe:

- Diseñar dashboards genéricos
- Usar tabs como eje principal de navegación — **decisión de producto, no preferencia de estilo**
- Agregar features sin impacto operativo
- Priorizar arquitectura sobre usabilidad

## Estructura de pantalla principal (decisión de producto)

La pantalla principal NO se organiza en tabs. Es una vista única que responde tres preguntas en orden:

1. **¿Puedo cerrar el mes?** — bloqueadores críticos arriba, visibles sin scroll
2. **¿Qué me falta?** — acciones pendientes priorizadas por impacto
3. **¿Qué hago hoy?** — tareas concretas con monto y plazo

La información se presenta en bloques verticales priorizados:
- **Bloqueadores** — riesgos críticos/altos que impiden el cierre
- **Acciones** — lista de tareas con impacto cuantificado en MXN
- **Conciliación** — estado del período actual (barra + brechas)
- **Score** — indicador de salud fiscal (secundario, no protagonista)

Las tabs **solo existen como navegación de drill-down**: ver todos los riesgos, ver detalle de conciliación, cargar archivos, diagnóstico CFDI. El usuario las usa para profundizar, nunca para orientarse.

**Criterio de validación del diseño:** Si el usuario necesita cambiar de tab para saber qué hacer, el diseño está mal.

## Vista principal — reglas de interacción (decisión de producto)

La vista principal es para **trabajar, no para navegar**. Es autocontenida.

Cada ítem de acción en la vista principal debe exponer:
- **Contexto mínimo** — qué pasó (ej. "Depósito $45,000 sin CFDI el 12/mar")
- **Impacto** — monto afectado en MXN
- **Acción clara** — qué debe hacer el contador (ej. "Emitir CFDI" / "Confirmar match" / "Marcar revisado")
- **Interacción directa** — el contador puede ejecutar o avanzar sin salir de pantalla (marcar como revisado, clasificar, confirmar match, resolver)

El drill-down solo se activa cuando:
- Se necesita detalle adicional para tomar la decisión
- El caso es ambiguo y requiere exploración
- El usuario elige profundizar voluntariamente

**Criterio de validación de interacción:** El 60–70% del trabajo del cierre mensual debe poder avanzarse desde la vista principal. Si el contador tiene que entrar a otra vista para resolver la mayoría de los casos, el diseño está mal.

## Rediseño funcional — vertical slice (alcance acordado)

Este no es un rediseño visual. Es un rediseño funcional mínimo que habilita interacción real desde la vista principal.

### 1. Backend — riesgos

Agregar campo `accion_sugerida` estructurado en riesgos (no strings en el frontend):
```json
{
  "tipo": "solicitar_cfdi",
  "label": "Solicitar CFDI",
  "puede_resolverse_inline": true
}
```

Introducir estados intermedios en `detecciones` (reemplaza el binario abierto/resuelto):
- `pendiente`
- `abierto`
- `en_revision`
- `en_espera_cfdi`
- `confirmado`
- `resuelto`
- `descartado`
- `falso_positivo`

Mantener `PATCH /api/v1/riesgos/{id}/resolver` y complementar con:
```
POST /api/v1/acciones/{id}/ejecutar
body: { "tipo": "confirmar_match" | "marcar_revisado" | "descartar" | ... }
```

### 2. Backend — conciliación (mínimo necesario)

No se rehace el motor. Solo se exponen casos accionables:
- Movimientos sin CFDI
- Matches débiles (score bajo)

Estructura de respuesta:
```json
{
  "movimiento_bancario": { ... },
  "cfdi_sugeridos": [ ... ],
  "score": 85
}
```
Con endpoint para confirmar/vincular desde la vista principal.

### 3. Frontend — vista principal

El bloque "Acciones del día" expone por cada ítem:
- Contexto: qué pasó (movimiento, fecha, contrapartes)
- Impacto: monto en MXN
- Acción directa: botón inline (no navega)
- Cambio de estado: visible e inmediato

El drill-down es una opción secundaria para casos complejos, no el flujo principal.

### Alcance intencional

**No buscamos:**
- Cobertura completa de todos los riesgos
- Sistema perfecto de conciliación
- Resolver todos los edge cases

**Sí buscamos:**
- Que el contador avance el 60–70% del cierre mensual desde la vista principal
- Esa es la métrica que define si el rediseño fue exitoso

Claude DEBE:

- Proponer acciones concretas, no solo datos
- Cuantificar el impacto en dinero
- Priorizar las tareas del contador
- Pensar en el flujo mensual del contador (cierre del 17, DIOT, declaraciones)

Toda propuesta funcional debe incluir:

- Impacto en carga operativa
- Impacto en flujo de efectivo
- Impacto en riesgo fiscal
- Prioridad de implementación

## Comandos

### Levantar con Docker (recomendado)
```bash
docker-compose up -d        # levanta PostgreSQL 16 + inicializa schema automáticamente (001 → 015)
python -m uvicorn backend.main_api:app --reload --port 8000
```

### Backend manual (Python/FastAPI)
```bash
pip install fastapi uvicorn python-multipart psycopg2-binary openpyxl pydantic python-jose bcrypt pdfplumber

# La DB se inicializa sola con docker-compose (scripts SQL 001 → 015).
# init_db() en backend/db.py aplica todas las migraciones al startup (Railway-ready).
python -m uvicorn backend.main_api:app --reload --port 8000
# Docs interactivos: http://localhost:8000/docs
```

### Deploy en Railway
```bash
# Railway detecta Procfile automáticamente:
# web: uvicorn backend.main_api:app --host 0.0.0.0 --port $PORT
# Variable de entorno requerida: DATABASE_URL (Railway la inyecta al vincular PostgreSQL)
# init_db() aplica todas las migraciones SQL al startup
```

### Frontend (React + Vite)
```bash
npm install
npm run dev   # → http://localhost:5173
```

## Arquitectura

```
Archivos usuario (XML/CSV/XLSX / Constancia PDF)
    → Parser Layer        backend/cfdi_parser.py / banco_parser.py / constancia_parser.py
    → Motor Fiscal        backend/motor_fiscal.py
    → API REST            backend/main_api.py  (FastAPI, puerto 8000)
    → DB Layer            backend/db.py  (connection pool + init_db con auto-migración)
    → Base de datos       PostgreSQL 16 (Docker / Railway) — database/migrations/ 001→015
    → Frontend            React 18 + Vite 5 (src/)
```

### Estructura de directorios

```
backend/                  # Paquete Python (tiene __init__.py)
  main_api.py             # FastAPI app
  db.py                   # Connection pool + init_db
  motor_fiscal.py         # Motores: conciliación, riesgos, scoring
  cfdi_parser.py          # Parser CFDI XML 3.3 / 4.0
  banco_parser.py         # Parser CSV/XLSX bancario
  constancia_parser.py    # Parser Constancia PDF
database/
  migrations/             # Scripts SQL idempotentes (001 → 015)
src/                      # Frontend React + Vite
  AuditoriaFiscalDashboard.jsx
  InicioPage.jsx          # Selector de empresa / onboarding post-login
  PerfilPage.jsx          # Perfil del contador (teléfono, RFC, despacho, cédula)
  AgregarEmpresaModal.jsx # Modal para agregar empresa por Constancia PDF
  LoginPage.jsx
  RegisterPage.jsx
  main.jsx
  auth.js
  components/ui/          # shadcn/ui
  lib/utils.js
  index.css
```

### Módulos backend (`backend/`)

| Módulo | Responsabilidad |
|--------|-----------------|
| `cfdi_parser.py` | Parsea CFDI XML 3.3 y 4.0. Valida RFC, cuadre matemático, detecta namespace. Extrae `cfdi_relacionados` (TipoRelacion + UUIDs) y calcula `es_anticipo_sat` (ClaveProdServ 84111506 + PUE + sin CfdiRel) |
| `banco_parser.py` | Parsea CSV/XLSX bancarios. Auto-detecta encoding y columnas (6+ alias) |
| `motor_fiscal.py` | Tres motores: Conciliación (banco↔CFDI), Riesgos (8 tipos), Scoring (0–100) |
| `constancia_parser.py` | Extrae RFC, razón social, régimen, obligaciones, CP, CURP de la Constancia de Situación Fiscal PDF (pdfplumber) |
| `main_api.py` | FastAPI: auth JWT, contador→N empresas, ingesta CFDI/banco, dashboard, riesgos, scoring, parseo constancia, acciones inline, cierre mensual, módulo Emitidos |
| `db.py` | Connection pool psycopg2 + helpers (`query_all`, `query_one`, `execute`) + `init_db()` con auto-migración al startup |

### Migraciones (`database/migrations/`)

| Migración | Contenido |
|-----------|-----------|
| `001_schema_inicial.sql` | DDL PostgreSQL: 8 tablas + extensiones `uuid-ossp`, `pg_trgm` |
| `002_usuarios.sql` | Tabla `usuarios` + columnas extra en `empresas` (constancia_path, obligaciones JSONB, cp_fiscal, curp) |
| `003_acciones.sql` | `accion_sugerida` JSONB en catálogo `riesgos` + estados intermedios en `detecciones` (idempotente) |
| `004_pagos_cfdi.sql` | Tablas `pagos_cfdi` y `pagos_relaciones`; agrega `complemento_pago` a `conciliaciones.tipo_match`; agrega `estado_pago` en `cfdi` (idempotente) |
| `005_cfdi40_campos.sql` | Campos CFDI 4.0: `exportacion`, `lugar_expedicion`, `domicilio_fiscal_receptor`, `regimen_fiscal_receptor` en tabla `cfdi` |
| `006_match_multiple.sql` | Extiende `tipo_match` con `agrupado` y `parcial_multiple` para matching 1:N y N:1 |
| `007_match_heuristico.sql` | Agrega `heuristico` a `tipo_match` (matches por similitud/heurística) |
| `008_confianza_conciliacion.sql` | Columna `confianza` (`alta`/`media`/`baja`) en `conciliaciones` |
| `009_ppd_estados.sql` | Extiende `tipo_match` con `pendiente_rep`/`pagado_parcial`; extiende `cfdi.estado_pago` con `pendiente_rep` (idempotente) |
| `010_complemento_tipos.sql` | Agrega `complemento_pago_total`/`complemento_pago_parcial` a `tipo_match`; columnas `pago_id` y `saldo_insoluto` en `conciliaciones` (idempotente) |
| `011_usuario_empresas.sql` | Tabla `usuario_empresas` (M:N): 1 contador → N empresas; migra relaciones existentes |
| `012_empresa_representante.sql` | Columnas `representante_legal` y `rfc_representante` en `empresas` (idempotente) |
| `013_perfil_contador.sql` | Perfil extendido del contador: `telefono`, `rfc`, `nombre_despacho`, `cedula` en `usuarios` (idempotente) |
| `014_cfdi_relacionados.sql` | Columna `cfdi_relacionados JSONB` + índice GIN en `cfdi` — almacena TipoRelacion + UUIDs del nodo CfdiRelacionados del XML (idempotente) |
| `015_anticipo_sat.sql` | Columna `es_anticipo_sat BOOLEAN DEFAULT FALSE` en `cfdi` — calculada en el parser según reglas SAT (ClaveProdServ 84111506 + MetodoPago PUE + sin CfdiRelacionados) (idempotente) |

### Módulos frontend (`src/`)

| Archivo | Responsabilidad |
|---------|-----------------|
| `main.jsx` | Raíz: enrutamiento login / register / inicio / dashboard basado en estado |
| `auth.js` | JWT en localStorage: `saveAuth`, `getToken`, `getEmpresaData`, `isLoggedIn` (verifica exp), `clearAuth` |
| `LoginPage.jsx` | Split-screen: branding izquierdo + formulario shadcn derecho. Llama `POST /api/v1/auth/login` |
| `RegisterPage.jsx` | Wizard 3 pasos: credenciales → constancia PDF → confirmación. Llama `POST /api/v1/auth/register` + `POST /api/v1/constancia/parsear` |
| `InicioPage.jsx` | Selección de empresa post-login. Lista empresas del contador, permite agregar nueva |
| `PerfilPage.jsx` | Perfil del contador: teléfono, RFC, despacho, cédula. Llama `PATCH /api/v1/perfil` |
| `AgregarEmpresaModal.jsx` | Modal para agregar empresa cargando Constancia PDF. Llama `POST /api/v1/mis-empresas` |
| `AuditoriaFiscalDashboard.jsx` | Dashboard principal con vista única accionable. Incluye tarjetas Emitidos/Recibidos, `TabEmitidos` (secciones por tipo SAT), parseo CFDI client-side con DOMParser |
| `components/ui/` | Componentes shadcn/ui: button, input, card, badge, label, alert, avatar, dialog, tabs, separator |
| `lib/utils.js` | Helper `cn()` (clsx + tailwind-merge) |
| `index.css` | Variables CSS dark theme (navy + cyan) + directivas Tailwind |

### Autenticación
- **JWT** con `python-jose`. Tokens con 8h de expiración.
- **Bcrypt** directo (`import bcrypt as _bcrypt`) — **NO usar passlib** (incompatibilidad con bcrypt moderno).
- **Modelo usuario-céntrico**: 1 contador puede gestionar N empresas. El token contiene `user_id`, `email`. La empresa activa se selecciona en el frontend.
- La tabla `usuario_empresas` (M:N) vincula usuarios a empresas con un rol (`contador` por defecto).
- Endpoints: `POST /api/v1/auth/register`, `POST /api/v1/auth/login`, `GET /api/v1/auth/me`.

### Endpoints principales (`backend/main_api.py`)

| Método | Ruta | Tag |
|--------|------|-----|
| POST | `/api/v1/auth/register` | Auth |
| POST | `/api/v1/auth/login` | Auth |
| GET | `/api/v1/auth/me` | Auth |
| POST | `/api/v1/constancia/parsear` | Constancia |
| GET | `/api/v1/empresas` | Empresas |
| POST | `/api/v1/mis-empresas` | Empresas |
| GET | `/api/v1/empresas/{id}` | Empresas |
| GET | `/api/v1/dashboard/{empresa_id}` | Dashboard |
| POST | `/api/v1/empresas/{id}/cfdi/upload` | Ingesta |
| POST | `/api/v1/empresas/{id}/banco/upload` | Ingesta |
| GET | `/api/v1/empresas/{id}/riesgos` | Riesgos |
| PATCH | `/api/v1/riesgos/{id}/resolver` | Riesgos |
| GET | `/api/v1/empresas/{id}/scoring` | Scoring |
| GET | `/api/v1/empresas/{id}/scoring/historial` | Scoring |
| GET | `/api/v1/empresas/{id}/conciliaciones` | Conciliación |
| GET | `/api/v1/empresas/{id}/conciliaciones/accionables` | Conciliación |
| POST | `/api/v1/acciones/{deteccion_id}/ejecutar` | Acciones |
| GET | `/api/v1/empresas/{id}/cierre/{periodo}` | Cierre |
| GET | `/api/v1/empresas/{id}/emitidos?periodo=YYYY-MM` | Emitidos |

### Frontend — stack y tema
- **React 18 + Vite 5 + Tailwind CSS v3 + shadcn/ui** (componentes instalados manualmente en `src/components/ui/`).
- **Paleta dark navy + cyan**: `--background: #0A0F1E`, `--primary: #06B6D4`, `--card: #0D1526`.
- **Fuentes**: Bricolage Grotesque (`font-display`), Outfit (`font-sans`), JetBrains Mono (`font-mono`) — cargadas en `index.html`.
- Variantes de `Badge` por severidad: `critical` (rojo), `high` (naranja), `medium` (amarillo), `low` (verde).

### Lógica de conciliación (`MotorConciliacion`)
- Prioridad: RFC + monto exacto → monto exacto → tolerancia ±2%
- Tolerancia exacta: ±$0.05 MXN
- Resultados completos: `exacto`, `parcial`, `sin_cfdi`, `sin_movimiento`, `complemento_pago`, `complemento_pago_total`, `complemento_pago_parcial`, `agrupado`, `parcial_multiple`, `heuristico`, `pendiente_rep`, `pagado_parcial`
- Columna `confianza` en cada resultado: `alta` / `media` / `baja`

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
- ✅ Auth JWT — registro con Constancia PDF, login, token
- ✅ **Modelo usuario-céntrico** — 1 contador → N empresas via `usuario_empresas` (M:N); `POST /api/v1/mis-empresas` crea/reutiliza empresa por RFC y la vincula al contador
- ✅ Docker Compose — PostgreSQL 16 con auto-init de scripts SQL (001 → 015)
- ✅ Frontend migrado a Tailwind CSS v3 + shadcn/ui (tema dark navy + cyan)
- ✅ **API conectada a PostgreSQL real** — pipeline ingesta → conciliación → riesgos → scoring persiste
- ✅ **Dashboard conectado a la API** — llama a endpoints reales, sin datos hardcoded
- ✅ **Vertical slice implementado** — vista principal accionable sin tabs como eje de navegación
  - `003_acciones.sql` — `accion_sugerida` JSONB en catálogo + estados intermedios en `detecciones`
  - `POST /api/v1/acciones/{id}/ejecutar` — actualiza estado con update optimista en frontend
  - `GET /api/v1/empresas/{id}/cierre/{periodo}` — vista consolidada: bloqueadores + acciones + conciliación
  - `GET /api/v1/empresas/{id}/conciliaciones/accionables` — pares sin_cfdi y parciales con contexto
- ✅ **`backend/db.py` modularizado** — connection pool psycopg2 + `init_db()` con auto-migración al startup (Railway-ready)
- ✅ **`Procfile` actualizado** — `uvicorn backend.main_api:app` (módulo con prefijo de paquete)
- ✅ **Reestructuración de directorios** — código Python en `backend/` (paquete Python), migraciones en `database/migrations/`
- ✅ **Campos CFDI 4.0** — `exportacion`, `lugar_expedicion`, `domicilio_fiscal_receptor`, `regimen_fiscal_receptor` (`005`)
- ✅ **Matching avanzado** — tipos `agrupado`, `parcial_multiple` (006), `heuristico` (007), columna `confianza` (008)
- ✅ **Complemento de Pago 2.0 (CFDI tipo P)** — parser, persistencia y conciliación con prioridad sobre heurística
- ✅ **Conciliación PPD completa con REP** — `enriquecer_estados_ppd()` clasifica cada CFDI PPD antes de conciliar; elimina falsos positivos en `CFDI_NO_COBRADO`/`CFDI_NO_PAGADO`; nuevos `tipo_match`: `pendiente_rep`, `pagado_parcial`; umbral PPD sin REP elevado a 60 días
- ✅ **Paso 1 score-based banco→REP** — `_conciliar_con_rep()` reemplaza el loop con `break`; scoring monto (exacto=10, ±2%=5) + fecha (exacta=+4, ≤2d=+2, ≤5d=+1); dedup de REPs por `pago.id`; emite `complemento_pago_total`/`complemento_pago_parcial` según `saldo_insoluto`; `TOLERANCIA_FECHA_REP=5d`; trazabilidad `pago_id` + `saldo_insoluto` en `ResultadoConciliacion`
  - `backend/cfdi_parser.py` — `PagoCFDI`, `DoctoRelacionado`, `_extraer_pagos()`, `es_pago` property; validación de cuadre omitida para tipo P
  - `database/migrations/004_pagos_cfdi.sql` — tablas `pagos_cfdi` + `pagos_relaciones`; `estado_pago` en `cfdi`; `complemento_pago` en tipo_match
  - `backend/motor_fiscal.py` — `PagoResumen`; `MotorConciliacion.conciliar()` acepta `pagos=`; regla: si existe complemento → NO usar heurística; output `{tipo_match:"complemento_pago", cfdis_relacionados:[], confianza:"alta"}`
  - `backend/main_api.py` — `_persistir_complemento_pago()` actualiza `monto_cobrado` y `estado_pago` en CFDIs relacionados; pipeline carga `pagos_cfdi` y pasa a motor
- ✅ **Módulo Emitidos** — vista completa de CFDIs emitidos (tipo I y E) organizados por lógica fiscal SAT
  - `database/migrations/014_cfdi_relacionados.sql` — columna `cfdi_relacionados JSONB` + índice GIN
  - `database/migrations/015_anticipo_sat.sql` — columna `es_anticipo_sat BOOLEAN` calculada en el parser
  - `backend/cfdi_parser.py` — `_extraer_cfdi_relacionados()`, `_tiene_clave_anticipo()`, campo `es_anticipo_sat`
  - `GET /api/v1/empresas/{id}/emitidos?periodo=YYYY-MM` — retorna ingresos y egresos clasificados con lógica SAT de 3 pasos; resumen + advertencias
  - `src/AuditoriaFiscalDashboard.jsx` — tarjetas Emitidos/Recibidos en vista principal, `TabEmitidos` con secciones por paso SAT, drag-and-drop funcional

### Lógica fiscal de anticipos (SAT oficial) — 3 pasos

El módulo Emitidos implementa la lógica SAT oficial. **No mezclar con TipoRelacion=07 en egresos** (era la implementación anterior incorrecta).

```
Paso 1 — ANTICIPO (Ingreso A):
  tipo_comprobante = "I"
  ClaveProdServ   = "84111506"   ← código SAT para anticipos
  MetodoPago      = "PUE"        ← pago en una sola exhibición
  Sin CfdiRelacionados
  → es_anticipo_sat = TRUE (calculado en el parser, persistido en DB)
  → acumula ingreso en el período de emisión

Paso 2 — FACTURA TOTAL (Ingreso B):
  tipo_comprobante = "I"
  CfdiRelacionados TipoRelacion = "07" → UUID del Ingreso A
  → es_factura_con_anticipo = TRUE (detectado en el endpoint)
  → ingresa el monto total de la venta

Paso 3 — EGRESO DE APLICACIÓN (Egreso C):
  tipo_comprobante = "E"
  FormaPago       = "30"         ← "Aplicación de anticipos"
  CfdiRelacionados → UUID del Ingreso B
  → aplicaciones_anticipo (detectado en el endpoint)
  → REDUCE el ingreso del período de B

Ingreso neto período = total(B) - total(C)

Advertencia activa: existe B sin C correspondiente en el período
→ tipo: "sin_egreso_anticipo" en la respuesta del endpoint
```

**Columnas clave en tabla `cfdi`:**
- `cfdi_relacionados JSONB` — array de `{tipo_relacion, uuids[]}`, extraído del XML
- `es_anticipo_sat BOOLEAN` — calculado en `cfdi_parser.py` al momento de la carga

## Convenciones importantes

- **Precisión financiera**: Usar siempre `Decimal` (no `float`) para montos
- **RFC mexicano**: `AAAA######XXX` — regex de validación en `cfdi_parser.py` y `main_api.py`; reutilizar siempre
- **CFDI**: Versión 3.3 o 4.0; namespaces XML distintos — ver `CFDIParser._detect_namespace()`
- **Severidades**: Los 4 niveles tienen pesos fijos en `MotorScoring`; cambiarlos afecta scores históricos
- **bcrypt**: Usar siempre `import bcrypt as _bcrypt` directamente, nunca a través de passlib
- **Tailwind**: Clases utilitarias en JSX; nunca `style={{}}` salvo para valores dinámicos (colores de severidad, SVG)
