# F3.3 — Detalle, XML y visor del CFDI — Plan

**Goal:** Que desde el listado se pueda ver el contenido de un CFDI sin salir de la pantalla: conceptos desplegables en la fila y un visor con el comprobante completo, con descarga del XML e impresión.

**Spec:** `docs/superpowers/specs/2026-10-02-f3-listado-cfdi-design.md` (secciones "`GET /cfdis/{uuid}`", "`GET /cfdis/{uuid}/xml`", "Conceptos en la fila" y "Visor del CFDI").

## Alcance

**Entra:** `GET /cfdis/{uuid}` y `GET /cfdis/{uuid}/xml` (con auditoría); botón de la fila que despliega los conceptos (columnas de concepto visibles, 10 por página en el navegador, total de conceptos); botón que abre el visor; descarga del XML con el token de la sesión; impresión con hoja de estilos de impresión.

**No entra:** editor de columnas (también las de concepto), filtro avanzado y exportar a Excel (F3.4); columnas propias de Nómina y Pago y cancelados desde el SAT (F3.5). El PDF no se genera en el servidor: el usuario lo guarda desde el diálogo de impresión.

## Decisiones

- El detalle lee solo lo ya guardado (encabezado, `cfdi_impuestos`, `cfdi_conceptos`, `pagos_relaciones`); nunca reprocesa el XML.
- Un UUID de otra empresa responde igual que uno inexistente (404); sin acceso a la empresa, 403.
- Más de 500 conceptos: se envían los primeros 500 y `total_conceptos` trae el total real; ambas pantallas lo avisan.
- Cada descarga de XML se registra en `auditoria` (`cfdi_xml_descargado`).
- El nombre del archivo descargado se limpia (solo letras, números y guion) aunque el UUID ya exista en la base.
- La descarga usa `fetch` con `Authorization` (un enlace directo no llevaría el token) y entrega el archivo con un enlace temporal.
- Las columnas de concepto del catálogo (`columnas_concepto`) se derivan en el servidor del JSON de impuestos por concepto; varias tasas del mismo impuesto suman base e importe y dejan la tasa vacía.

## Verificación

- `python -m pytest` (unitarios, router y E2E contra Postgres: detalle completo, sin XML, UUID inexistente, otra empresa, auditoría).
- `npm test`, `tsc`, `lint`, `next build`.
- Playwright con la API simulada: desplegar conceptos, abrir el visor, descargar el XML, vista de impresión.
