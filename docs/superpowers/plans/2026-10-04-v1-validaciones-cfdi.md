# Plan V1 — Validaciones de CFDI (carril D)

Spec: `docs/superpowers/specs/2026-10-04-v1-validaciones-cfdi-design.md`.
Rama: `claude/d-v1-validaciones-cfdi` desde `origin/main`. PR: `D·V1: validaciones de CFDI`.

Cada tarea: prueba en rojo, código, verificación.

## Tarea 1 — Módulo puro `validaciones_cfdi.py`

- Pruebas (`backend/tests/test_validaciones_cfdi.py`): catálogo (4 claves, direcciones);
  `rangos("2026-03")` → (2026-03-01, 2026-04-01, 2026-01-01); diciembre; periodo
  inválido; `Configuracion.desde_json` con faltantes, claves desconocidas y umbral como
  texto; `validar_cambio` rechaza clave desconocida y umbral negativo; condiciones SQL
  sin interpolar valores (el umbral va como parámetro).
- Verificación: `python -m pytest backend/tests/test_validaciones_cfdi.py`.

## Tarea 2 — Migración 061

- Prueba `backend/tests/test_migracion_061.py` (`-m db`): idempotente, columnas, cascada.
- Código: `database/migrations/061_validaciones_cfdi_config.sql`, línea en `db.py`.
- Revisión: `migration-validator`.

## Tarea 3 — Datos y router

- Pruebas `backend/tests/test_router_validaciones_cfdi.py` (base mockeada): 401/403;
  422 de periodo, dirección, validación, alcance y `no_bancarizado` en emitidos;
  respuesta del resumen con tarjeta inactiva en `null`; PUT de configuración.
- Pruebas `backend/tests/test_e2e_validaciones_cfdi.py` (`-m db`): los siete criterios
  de aceptación de la spec con una siembra propia.
- Código: `backend/validaciones_cfdi_datos.py`, `backend/routers/validaciones_cfdi.py`,
  `include_router` en `main_api.py`, rutas en `docs/openapi.yaml`.

## Tarea 4 — Frontend

- Pruebas vitest: tarjetas con conteos y acumulado; inactiva; clic abre la lista;
  configuración guarda y valida el umbral.
- Código: `hooks/useValidacionesCfdi.ts`, `components/validaciones/`, página
  `app/(app)/empresas/[empresaId]/validaciones/page.tsx`, entrada en `Sidebar.tsx`.
- Verificación: `npm test`, `tsc --noEmit`, `npm run lint`.

## Tarea 5 — Cierre

Merge de `origin/main`, suites completas, Playwright de la pantalla, fila de V1 en el
plan maestro, PR en borrador y aviso a la coordinación (que lanza las revisiones).
