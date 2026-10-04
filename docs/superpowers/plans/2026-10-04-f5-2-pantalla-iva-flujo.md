# F5.2 — Pantalla IVA base flujo y exportación — Plan

> Cada tarea va con prueba primero: se escribe, se ve fallar, se implementa, se ve pasar.

**Goal:** El contador ve el IVA de un mes por tasa y origen, abre la lista de CFDI que compone cada cifra, puede no considerar un CFDI o reasignarlo de periodo (con motivo y auditoría) y exportar la tarjeta a Excel.

**Spec:** `docs/superpowers/specs/2026-10-04-f5-iva-base-flujo-design.md` (secciones "Pantalla (F5.2)" y "Contrato de API"). Carril C: `backend/iva_flujo_exportacion.py` (nuevo), `frontend/components/iva-flujo/` y `app/(app)/empresas/[empresaId]/iva-flujo/` (nuevos); en archivos compartidos solo se agregan líneas (`Sidebar.tsx`, `Header.tsx`, `types/api.ts`, `openapi.yaml`, `e2e`).

## Hecho

- [x] **Excel** (`test_iva_flujo_exportacion.py`, router y E2E): hoja `Detalle` con las bases e IVA por tasa, fecha de pago, UUID del REP, marcas, motivo y ajuste; hoja `Resumen` con los orígenes y el resultado; un texto que empieza con `=` queda como texto; más de 50,000 renglones responde 422; cada exportación queda en la auditoría. `GET /iva-flujo/{periodo}/exportar`.
- [x] **Estado en la URL** (`lib/iva-flujo.ts`): vista (trasladado, acreditable, a cargo), origen y página; los valores por defecto no se escriben; cambiar de vista u origen regresa a la página 1.
- [x] **Hooks**: resumen, detalle paginado (50), guardar y quitar ajuste; un ajuste refresca el resumen, el detalle y la tabla de IVA del Inicio.
- [x] **Componentes**: tarjetas-pestaña (A cargo se vuelve A favor si el saldo es negativo), tarjetas por origen con "pagos / documentos" y las notas de crédito restando, desglose por tasa con retenciones, resultado del mes, tabla de detalle (fecha de pago y REP solo en crédito, marcas y motivo en español, acciones por renglón), ventana de ajuste (motivo obligatorio, periodo destino validado, error del servidor visible) y la pantalla que los une con el visor del CFDI del carril A.
- [x] **Menú** "IVA base flujo" y etiqueta del encabezado; la Cédula de IVA se conserva hasta F5.3.
- [x] **Playwright** (API simulada): tarjetas y detalle, no considerar con motivo, exportar y visor, menú y móvil.

## Review focus

- Que lo que se ve en cada tarjeta sea exactamente lo del servidor (nada se recalcula en el navegador).
- Que un ajuste no deje datos viejos en pantalla (resumen, detalle e Inicio se refrescan).
- Que el motivo sea obligatorio y los errores 422/404 del servidor se muestren sin cerrar la ventana.
