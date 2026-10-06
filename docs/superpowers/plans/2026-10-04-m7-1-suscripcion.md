# Plan M7.1 — Suscripción sin cobro en línea (carril D)

Spec: `docs/superpowers/specs/2026-10-04-m7-1-suscripcion-design.md`.
Rama: `claude/d-m7-suscripcion` desde `origin/main`. PR: `D·M7.1: planes, límite de RFC y asignación manual`.

No depende de U1 (#36): el uso de RFC se calcula en SQL con la misma regla de
administrador (marcado, o el primer vinculado si no hay ninguno).

## Tarea 1 — Módulo puro `suscripcion.py`
- Pruebas `backend/tests/test_suscripcion.py`: plan efectivo (sin suscripción, activa,
  vencida, suspendida, cancelada, plan inactivo), límite (nulo, alcanzado, debajo),
  admin sin límite, validación de asignación (plan, estado, fecha) y de plan (clave,
  nombre, precio `Decimal`, límite).

## Tarea 2 — Migración 063
- Prueba `backend/tests/test_migracion_063.py` (`-m db`): tablas, planes de ejemplo, un
  solo por defecto, no pisa planes editados al repetir.

## Tarea 3 — Datos y router
- `backend/tests/test_router_suscripcion.py` (mock): 401, 403 de `/admin/*`, 422.
- `backend/tests/test_e2e_suscripcion.py` (`-m db`): criterios 1 a 7.
- `include_router`, OpenAPI.

## Tarea 4 — Frontend
- Vitest de `components/suscripcion/MiSuscripcion` y `AdminSuscripciones`.
- Página `/suscripcion`, entrada del menú.

## Tarea 5 — Cierre
Merge de `main`, suites, Playwright, plan maestro (M7 y pedido a B: llamar a
`verificar_alta_rfc` en `POST /mis-empresas`), PR y aviso.
