# Plan M7.2 — Suscripción: historial (y cobro, pendiente)

Spec: `docs/superpowers/specs/2026-10-06-m7-2-suscripcion-design.md`.

1. Prueba de la migración 065 (siembra única) → migración y registro en `init_db`.
2. E2E del historial (orden, privacidad, 403 y 404) → `asignar` en una transacción con
   la fila de historial, `historial(...)` y las dos rutas.
3. OpenAPI (dos rutas y el esquema `AsignacionPlan`).
4. Vitest: tarjeta del historial sin notas y el historial del administrador → hooks,
   `HistorialPlan` y el botón por cuenta.
5. Suites completas, PR `D·M7.2a` y aviso a la coordinación.
6. Cobro en línea: spec propia cuando Carlos decida proveedor y CFDI.
