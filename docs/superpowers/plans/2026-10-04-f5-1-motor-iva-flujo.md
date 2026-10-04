# F5.1 — Motor del IVA por flujo, API y ajustes — Plan

> Cada tarea va con prueba primero: se escribe, se ve fallar, se implementa, se ve pasar.

**Goal:** Calcular el IVA de un mes por flujo de efectivo con desglose por tasa, origen y retenciones; listar los CFDI que componen cada cifra; permitir no considerar o reasignar un CFDI con auditoría.

**Spec:** `docs/superpowers/specs/2026-10-04-f5-iva-base-flujo-design.md` (entrega F5.1). Carril C: archivos nuevos `backend/iva_flujo.py`, `iva_flujo_datos.py`, `routers/iva_flujo.py` y la migración `050`; en archivos compartidos solo se agregan líneas (`db.py`, `main_api.py`, `openapi.yaml`). `iva.py` no se toca todavía (F5.3 cambia la cédula y el Inicio al motor nuevo).

## Tareas

- [x] **Motor puro** (`test_iva_flujo.py`, 70 pruebas): desglose por tasa (16, 8, 0, exento, otras, no objeto) y retenciones; conversión a pesos de un cobro (`equivalencia_dr` + tipo de cambio del pago, sin asumir 1); eventos de documento (PUE, notas de crédito, anticipo, aplicación de anticipo) y de pago (REP 2.0 con `ImpuestosDR`, aproximación por proporción para 1.0, `sin_equivalencia`); descuadre y CFDI sin desglose guardado; motivos de exclusión del acreditable; ajustes (excluir, reasignar); resumen por origen con resultado y advertencias; detalle paginado.
- [x] **Migración 050** `iva_ajustes` (única por empresa, CFDI y dirección; `reasignar` ⇔ hay periodo destino) registrada en `db.init_db`.
- [x] **Carga SQL** (`iva_flujo_datos.py`): impuestos por tasa y no-objeto por subconsulta lateral, pagos con sus impuestos del documento, documentos PUE/notas del mes, PPD con pago en el mes y reasignados al mes.
- [x] **Endpoints** (`test_router_iva_flujo.py`, 23): resumen, detalle, listar/guardar/quitar ajustes; validación 422, 404 de CFDI ajeno o de otra dirección, 403 sin acceso; auditoría `iva_ajuste` / `iva_ajuste_retirado`.
- [x] **E2E contra Postgres** (`test_e2e_iva_flujo.py`, 17): las cuatro tasas en un CFDI, crédito con dos REP en meses distintos, REP 1.0 aproximado, USD sin equivalencia, REP cancelado, anticipo + factura − aplicación, efectivo y uso S01 fuera del acreditable, retenciones a favor y a enterar, ajustes con auditoría, reasignación de un PPD, aislamiento entre empresas.
- [x] **OpenAPI** (`test_openapi_sync.py`).
- [x] Revisión de `dominio-fiscal` y `migration-validator` (migración apta). Corregido tras la revisión: UUID en minúsculas en `pagos_relaciones` (el PPD se perdía), la retención a enterar ya no depende de la exclusión por efectivo o uso, efectivo medido en pesos y sobre lo pagado, nota de crédito recibida fuera de las reglas de deducibilidad, tipo de cambio ausente sin asumir 1, autofactura PPD en ambas direcciones, motivo obligatorio, CFDI vigentes en los ajustes, redondeo medio hacia arriba y total = suma de las tarjetas redondeadas. Pendiente a propósito: Egreso contra PPD sin cobrar (D-F5-7), forma de pago del REP (F5.4).
- [ ] PR `C·F5.1`.

## Review focus

- La suma por tasa explica el IVA del encabezado; si no, manda el encabezado y se marca `descuadre`.
- Un PPD solo causa en la fecha de cada pago y solo por lo pagado; un PUE nunca genera crédito.
- Anticipo + factura − aplicación = factura.
- Un ajuste de una dirección no afecta a la otra; reasignar mueve todos los cobros del CFDI.
- Un REP cancelado o un pago sin equivalencia no suma.
