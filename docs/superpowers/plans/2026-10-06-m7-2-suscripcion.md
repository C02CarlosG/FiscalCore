# Plan M7.2 — Suscripción: historial, pagos manuales y datos fiscales (D10)

Spec: `docs/superpowers/specs/2026-10-06-m7-2-suscripcion-design.md`.

1. Prueba de la migración 065 (siembra única) → migración y registro en `init_db`.
2. E2E del historial (orden, privacidad, 403 y 404) → `asignar` en una transacción con
   la fila de historial, `historial(...)` y las dos rutas.
3. OpenAPI (dos rutas y el esquema `AsignacionPlan`).
4. Vitest: tarjeta del historial sin notas y el historial del administrador → hooks,
   `HistorialPlan` y el botón por cuenta.
5. Suites completas, PR `D·M7.2a` y aviso a la coordinación.
6. D10: pruebas puras (`test_suscripcion_pagos.py`: datos fiscales, pagos, aviso) →
   `suscripcion_pagos.py`.
7. Prueba de la 066 (CHECKs, borrado en cascada) → migración y registro.
8. E2E de datos fiscales, pagos y aviso → datos y rutas; OpenAPI.
9. Vitest: aviso, pagos y datos fiscales en «Mi suscripción»; detalle de cuenta con los
   formularios → componentes `PagosTabla` y `DetalleCuenta`.
10. Suites completas, push al PR y aviso a la coordinación.

## M7.2b (PR «D·M7.2b», sobre main después del #51)

11. Pruebas puras: `sumar_meses`, `nueva_vigencia`, meses, UUID, correo y anulación →
    `suscripcion_pagos.py`.
12. 066: estado, anulación, meses, UUID, vigencias y correo → prueba de la migración.
13. E2E: pagos que extienden y anulaciones que revierten, datos fiscales de la cuenta y
    del admin, avisos y lista de vencimientos → datos (`registrar_pago` y `anular_pago`
    con la suscripción bloqueada) y rutas; OpenAPI.
14. Vitest: aviso vencido, formulario de datos fiscales de la cuenta, anular con motivo,
    lista de vencimientos → `DatosFiscalesForm`, `PagosTabla`, `DetalleCuenta`.
15. Menores de las revisiones del #50 y #51: `strip(" ")` como `btrim`, 409 por
    `ConfiguracionInvalida` al aprobar, E2E de correo distinto del invitado,
    `formatearInstante` en el historial, aviso si falla el historial, `ETIQUETA_ESTADO`.
