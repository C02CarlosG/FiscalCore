# F3 — Listado unificado de CFDI

Fecha: 2026-10-02. Estado: borrador para revisión.
Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md` (fase F3).
Referencia de comportamiento: `2026-10-01-referencia-plataforma.md`.

## Contexto

Hoy FiscalCore tiene cuatro pantallas de CFDI (Visor SAT, Emitidos, Recibidos, Nómina),
cada una con su endpoint, que devuelven **todo** el periodo y se paginan en el navegador
de 8 en 8. Muestran 7 columnas fijas, no se pueden filtrar por estado ni método de pago,
no listan traslados ni pagos, no permiten ver los conceptos ni el comprobante, y el
periodo se pierde al cambiar de pantalla.

F1 ya guarda lo necesario (impuestos por tasa, conceptos, encabezados, impuestos de
cada pago). F3 lo hace visible: un solo listado, servido y paginado por el backend, con
las piezas que después reutilizan IVA (F5), ISR (F7) y EFOS (M3).

## Objetivo

Que un contador pueda encontrar, revisar y exportar cualquier CFDI de la empresa
—emitido o recibido, de cualquier tipo— eligiendo qué columnas ver, sin salir de una
pantalla y sin perder el periodo al navegar.

## Alcance

### Entra

1. API de listado paginada, con filtros, orden, conteos por tipo y totales del periodo y
   del acumulado del ejercicio.
2. Pantalla única de listado para Emitidos y Recibidos, con pestañas por tipo de
   comprobante (Ingreso, Egreso, Traslado, Nómina, Pago).
3. Estado de la pantalla en la URL y periodo compartido entre todas las pantallas, con
   el mes actual por defecto.
4. Conceptos desplegables en la fila y visor del CFDI, con descarga del XML.
5. Editor de columnas (orden y visibilidad) guardado por usuario en el servidor.
6. Filtro avanzado por campo.
7. Exportación a Excel de lo filtrado, con las columnas visibles.
8. Columnas de nómina y de pagos (requiere ampliar la extracción de nómina).
9. Descarga manual de cancelados desde "Conexión SAT".
10. Correcciones chicas detectadas en la comparación (ver "Correcciones incluidas").

### No entra (y dónde queda)

| Tema | Queda en |
|---|---|
| Etiquetas, comentarios y evidencias por CFDI | M1 |
| Selección en lote y acciones masivas | M1 |
| Exportaciones como trabajos en cola con expiración | Solo si el volumen lo exige; ver "Decisiones" |
| PDF generado en el servidor | No se hace; el visor se imprime desde el navegador |
| Fecha de cancelación y "alcance" de cancelación | F2 (requiere metadatos del SAT) |
| Interruptor "no considerar IVA / ISR" | F5 / F7 |
| EFOS y Validaciones | M3 / M1 (reutilizan este listado) |

## Decisiones

| # | Decisión | Motivo | Si resulta equivocada |
|---|---|---|---|
| D1 | Un endpoint de listado y uno de resumen, separados | Paginar no debe recalcular conteos ni totales | Se fusionan; el contrato de cada uno no cambia |
| D2 | El catálogo de columnas vive en el backend y el frontend lo consume | Una sola fuente para listar, ordenar, filtrar y exportar; evita que la exportación y la pantalla diverjan | Duplicarlo en el frontend es mecánico |
| D3 | Exportación directa (respuesta con el archivo), tope de 50,000 filas | Ya existe para otros reportes; una cola agrega una tabla, un worker y una pantalla | Se agrega la cola cuando haya una empresa que lo supere |
| D4 | Reordenar columnas con botones subir/bajar, sin arrastrar | Sin dependencia nueva y accesible por teclado | Agregar arrastre encima no cambia lo guardado |
| D5 | El periodo de un CFDI es el de su **fecha de emisión**, para todos los tipos; nómina y pagos muestran además su fecha de pago como columna | Es el criterio que ya usan todas las consultas existentes y el del SAT | Ver "Dudas abiertas" |
| D6 | Las pantallas Visor SAT y Nómina desaparecen; sus endpoints se retiran al final | Nómina pasa a ser una pestaña; el visor queda cubierto por "Todos" los tipos | — |
| D7 | La clasificación de anticipos de FiscalCore se conserva como columna "Categoría" | Es una ventaja propia que la referencia no tiene | — |

## API

Todas bajo `/api/v1/empresas/{empresa_id}`, con sesión y `validar_acceso_empresa`.
Se documentan en `docs/openapi.yaml`.

### `GET /cfdis`

Parámetros:

| Nombre | Valores | Por defecto |
|---|---|---|
| `direccion` | `emitidos`, `recibidos` | obligatorio |
| `periodo` | `YYYY-MM` | obligatorio |
| `tipo` | `I`, `E`, `T`, `N`, `P` | `I` |
| `estado` | `vigente`, `cancelado`, `todos` | `vigente` |
| `metodo` | `PUE`, `PPD`, `todos` | `todos` |
| `pago` | `pendientes`, `pagadas`, `todos` (solo con `metodo=PPD`) | `todos` |
| `q` | texto: UUID, RFC, nombre, serie o folio de la contraparte | — |
| `filtros` | JSON: lista de `{campo, op, valor}` | — |
| `orden` | clave de columna ordenable | `fecha_emision` |
| `dir` | `asc`, `desc` | `asc` |
| `pagina` | entero ≥ 1 | 1 |
| `por_pagina` | 30, 50, 100 | 30 |

Respuesta: `{ items: [...], total, pagina, por_pagina }`. Cada item trae todas las
columnas del catálogo para ese tipo (no solo las visibles): el editor de columnas no
vuelve a consultar al mostrar una columna.

Reglas:

- "Emitido" es `rfc_emisor = RFC de la empresa`; "recibido" es `rfc_receptor = RFC`.
- `campo` y `orden` solo aceptan claves del catálogo; `op` solo los operadores del tipo
  de dato de la columna. Cualquier otro valor responde 422. Los valores siempre van
  como parámetros de la consulta, nunca concatenados.
- Operadores: texto (`contiene`, `igual`, `empieza`), número y fecha (`igual`, `mayor`,
  `menor`, `entre`), booleano (`igual`), catálogo (`igual`, `en`).
- Máximo 10 filtros avanzados por consulta.

### `GET /cfdis/resumen`

Mismos filtros (sin orden ni paginación). Respuesta:

- `conteos`: número de CFDI por tipo con los filtros de estado, método y búsqueda
  aplicados (alimenta las pestañas).
- `totales.periodo` y `totales.acumulado` (enero al mes del periodo) para el tipo activo.
  Las cifras dependen del tipo:
  - Ingreso, Egreso, Traslado: conteo; retención de IVA, IEPS e ISR; traslado de IVA,
    IEPS e ISR; total de retenciones; subtotal; descuento; neto; total.
  - Nómina: conteo; número de empleados (RFC distintos); sueldos; otras percepciones;
    gravado; exento; ISR retenido; otras deducciones; subsidio causado; neto a pagar.
  - Pago: conteo; base de IVA al 16 %, 8 %, 0 % y exento; traslado de IVA; retención de
    IVA; total; total de pagos relacionados.
- `advertencias`: las de anticipos que hoy devuelve `/emitidos` (factura que aplica
  anticipo sin su egreso).

Los importes se calculan en `Decimal` en SQL y en pesos (importe × tipo de cambio).
Cuando no hay CFDI, las cifras van en `null` (la pantalla muestra un guion, no ceros).

### `GET /cfdis/columnas?direccion=&tipo=`

Catálogo de columnas para ese tipo: `clave`, `etiqueta`, `tipo_dato` (`texto`, `fecha`,
`fecha_hora`, `moneda`, `numero`, `booleano`, `catalogo`), `grupo` (`encabezado`,
`concepto`), `visible_por_defecto`, `ordenable`, `filtrable`.

Columnas de encabezado para Ingreso y Egreso (★ = visible por defecto):

- Identificación: fecha de expedición ★, serie ★, folio ★, UUID, versión, tipo de
  comprobante, lugar de expedición, fecha de timbrado, no. de certificado, exportación.
- Contraparte: RFC ★, nombre ★, régimen fiscal del receptor, régimen fiscal del emisor.
- Importes: total ★, saldo de la factura ★, subtotal ★, descuento ★, neto ★, y cada uno
  en pesos; moneda; tipo de cambio.
- Impuestos: traslado de IVA ★, traslado de IEPS, retención de IVA, retención de ISR,
  retención de IEPS (y en pesos).
- Pago: método ★, forma ★, condiciones, uso ★, CFDI de pago relacionados ★.
- Relaciones: UUID relacionado, tipo de relación, UUID que sustituye ★.
- Factura global: periodicidad, meses, año.
- Propias de FiscalCore: categoría (venta, anticipo, factura con anticipo, aplicación de
  anticipo, nota de crédito) ★, estado ★, estado de pago.

Los códigos del SAT (régimen, forma y método de pago, uso, tipo de relación) se devuelven
como código y como descripción; el catálogo de descripciones vive en un módulo del
backend (`catalogos_sat.py`).

Columnas de concepto (para la fila desplegada): clave de producto ★, no. de
identificación, cantidad ★, clave de unidad ★, unidad, descripción ★, valor unitario ★,
importe ★, descuento ★, objeto de impuesto, cuenta predial, base y importe de IVA
trasladado ★, tasa de IVA, base/tasa/importe de IEPS, base/tasa/importe de IVA retenido,
base/tasa/importe de ISR retenido.

### `GET /cfdis/{uuid}`

Detalle para el visor: encabezado completo (con descripciones de catálogo), emisor y
receptor, impuestos por tasa, conceptos (hasta 500; `total_conceptos` indica si hay
más), pagos que lo liquidan (UUID del REP, fecha, importe, saldo) y CFDI relacionados.
404 si el UUID no pertenece a la empresa.

### `GET /cfdis/{uuid}/xml`

Devuelve el XML guardado como descarga (`application/xml`, nombre `<uuid>.xml`). 404 si
no pertenece a la empresa o no hay XML. Se registra en `auditoria`.

### `GET /cfdis/exportar`

Mismos filtros que el listado más `columnas` (claves, en orden). Devuelve un `.xlsx`
con una hoja de CFDI y una de totales. Si el resultado supera 50,000 filas responde 422
pidiendo acotar los filtros. Se registra en `auditoria`.

### `GET` y `PUT /api/v1/preferencias/tablas/{vista}`

Por usuario. `vista` identifica la tabla (por ejemplo `cfdi-emitidos-I`,
`cfdi-emitidos-I-totales`, `cfdi-conceptos`). Cuerpo: `{ columnas: [{clave, visible}] }`
en el orden deseado. Sin preferencia guardada, `GET` devuelve `{columnas: null}` y la
pantalla usa el orden y la visibilidad del catálogo. Claves desconocidas se ignoran al
leer (el catálogo puede cambiar entre versiones).

## Datos

- **Migración 030**:
  - Tabla `preferencias_tabla (usuario_id, vista, config JSONB, updated_at)`, llave
    primaria `(usuario_id, vista)`, borrado en cascada con el usuario.
  - Índices compuestos para el listado: `(empresa_id, rfc_emisor, fecha_emision)` y
    `(empresa_id, rfc_receptor, fecha_emision)`.
  - Columnas de nómina en `cfdi`: `nomina_fecha_pago`, `nomina_tipo_regimen`,
    `nomina_sueldos`, `nomina_otras_deducciones`, `nomina_subsidio_causado`.
- **Extracción de nómina** (sube `DETALLE_VERSION` a 2; el reproceso existente rellena
  lo ya guardado): `FechaPago` del nodo de nómina, `TipoRegimen` del receptor,
  `TotalSueldos`, `TotalOtrasDeducciones` y el subsidio causado. Revisión del agente
  `dominio-fiscal`: el subsidio causado y el "ajuste de ISR retenido" tienen reglas que
  cambiaron en 2024 y hay que confirmar de qué nodo salen antes de implementarlos; si no
  queda claro, "ajuste de ISR retenido" se deja fuera de F3 y se anota.
- **Bases de IVA de los pagos**: suma de `pagos_relaciones_impuestos` del REP,
  convertida a pesos con la equivalencia y el tipo de cambio del pago. Un REP de
  Pagos 1.0 no tiene bases: se muestra un guion y la pantalla lo advierte.
- **Saldo de la factura**: `total − monto_cobrado` para PPD; cero para PUE.
- **Cancelados**: la descarga manual de "Conexión SAT" acepta el estado a pedir
  (vigentes, cancelados). Al importar un paquete pedido como cancelado, cada CFDI queda
  con `estado = 'cancelado'`, sea nuevo o ya existente. Lo que el SAT permite descargar
  de cancelados se verifica al implementar; si solo entrega metadatos, este punto pasa
  a F2 y F3 solo filtra por el estado que ya exista.

## Pantalla

### Ruta y estado

`/empresas/{id}/cfdi/emitidos` y `/empresas/{id}/cfdi/recibidos`. Todo el estado va en
los parámetros de la URL: `periodo`, `tipo`, `estado`, `metodo`, `pago`, `q`, `filtros`,
`orden`, `dir`, `pagina`, `por_pagina`. Recargar, compartir el enlace o usar atrás y
adelante del navegador reproduce la misma vista.

### Periodo global

- Selector "2026 - Septiembre" en lugar del campo de mes del navegador. Ofrece los
  periodos con datos (endpoint `/periodos`, ya existe) más el mes actual.
- El periodo elegido se conserva al cambiar de pantalla (los enlaces del menú lo
  arrastran) y se recuerda por empresa entre sesiones. Sin periodo en la URL se usa el
  recordado y, si no hay, el mes actual.
- Aplica a todas las pantallas con periodo: Dashboard, CFDI, Conciliación, Cédula de IVA.

### Composición

1. **Barra**: periodo, búsqueda, filtro avanzado, estado (Vigentes / Cancelados / Todos),
   método (PUE / PPD / Todos), sub-filtro de PPD cuando aplica, Exportar.
2. **Pestañas** por tipo con su conteo.
3. **Totales**: tabla de dos renglones (Periodo, Acumulado) con su editor de columnas.
4. **CFDI**: tabla con encabezado fijo, desplazamiento horizontal, orden por columna,
   paginación en servidor (30 / 50 / 100) y su editor de columnas.
5. **Fila**: botón para desplegar conceptos; botón para abrir el visor.

### Conceptos en la fila

Al desplegar se consulta el detalle del CFDI y se muestran sus conceptos con las columnas
de concepto visibles, paginados en el navegador de 10 en 10, con el total de conceptos.

### Visor del CFDI

Ventana con: tipo y estado, serie y folio, emisor y receptor (nombre, RFC, régimen,
domicilio fiscal o lugar de expedición), folio fiscal, fecha y hora, certificado,
conceptos, subtotal / descuento / traslados / retenciones / total, moneda y tipo de
cambio, forma y método de pago, uso, CFDI relacionados y pagos que lo liquidan. Acciones:
descargar XML e imprimir (hoja de estilos de impresión; el usuario la guarda como PDF
desde el navegador).

### Editor de columnas

Ventana con la lista de columnas en su orden actual; cada una con interruptor de
visibilidad y botones subir y bajar. En la tabla de CFDI hay dos listas: encabezados y
conceptos. "Guardar" persiste en el servidor; "Restablecer" vuelve al catálogo.

### Filtro avanzado

Ventana con renglones de campo, operador y valor; se agregan y quitan. El operador y el
control del valor dependen del tipo de dato del campo. "Aplicar" los pone en la URL; un
indicador en el botón muestra cuántos hay activos.

### Estados

Cargando (esqueleto de tabla), vacío ("No hay CFDI con estos filtros" y botón para
limpiarlos), error (mensaje y reintento), totales sin datos (guiones).

### Móvil

Barra y pestañas se apilan; la tabla conserva el desplazamiento horizontal con las dos
primeras columnas fijas. Las tarjetas por fila quedan para M6.

## Correcciones incluidas

- Fechas en `dd/mm/aaaa` en todas las tablas.
- Encabezados de tabla con un solo estilo (hoy mezclan mayúsculas y minúsculas).
- El "Score fiscal actual" del dashboard muestra el del periodo elegido, no el último
  de la tendencia.
- El rol bajo el nombre del usuario refleja su rol real (hoy dice "Contador" fijo).
- La campana sin función se oculta hasta M3.
- Menú: "Gestión de CFDI" pasa a "CFDIs" con Emitidos y Recibidos.

## Criterios de aceptación

Con los CFDI de COPLASUR descargados y comparando el mismo día contra la plataforma de
referencia, para septiembre de 2026, emitidos, vigentes:

1. Los conteos de las cinco pestañas coinciden.
2. Los totales de Ingreso coinciden al centavo: subtotal, descuento, neto, traslado de
   IVA y total, en periodo y en acumulado.
3. Cambiar a PPD → "pendientes de pago" da el mismo conteo.
4. Lo mismo para recibidos (conteos y totales de Ingreso).

Y, sin depender de la referencia:

5. Con 100,000 CFDI sintéticos en una empresa, el listado y el resumen responden en
   menos de 500 ms cada uno en el entorno local.
6. Un valor de `orden`, `campo` u `op` fuera del catálogo responde 422 (prueba con
   intentos de inyección).
7. Un usuario sin acceso a la empresa recibe 403 en los seis endpoints.
8. Recargar la página con filtros aplicados muestra exactamente la misma vista.
9. El orden y la visibilidad de columnas guardados se conservan al volver a entrar y
   al cambiar de equipo.
10. El Excel exportado tiene las mismas filas (todas las páginas) y columnas que la
    pantalla, en el mismo orden, y sus totales coinciden con los de pantalla.

## Entregas

Cada una con su plan, su rama y su PR; todas dejan la aplicación funcionando.

| Entrega | Contenido | Depende de |
|---|---|---|
| F3.1 | Migración 030 (índices y preferencias), catálogo de columnas, `GET /cfdis`, `/cfdis/resumen`, `/cfdis/columnas`; prueba de volumen | F1 |
| F3.2 | Periodo global y estado en la URL; pantalla unificada con barra, pestañas, totales, tabla y paginación; retiro de Visor SAT y Nómina; correcciones chicas | F3.1 |
| F3.3 | `GET /cfdis/{uuid}` y `/xml`; conceptos en la fila; visor del CFDI | F3.2 |
| F3.4 | Preferencias de columnas y editor; filtro avanzado; exportación a Excel | F3.2 |
| F3.5 | Nómina y pagos (extracción versión 2, columnas y totales propios); descarga de cancelados | F3.1, F3.2 |

Al terminar F3.5 se retiran los endpoints `/emitidos`, `/recibidos`, `/cfdi/visor` y
`/cfdi/nomina` junto con sus pruebas.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El listado con todas las columnas del catálogo hace consultas pesadas (impuestos por tasa, pagos relacionados) | Agregados por subconsulta solo sobre la página devuelta; prueba de volumen en F3.1 |
| El filtro avanzado abre la puerta a inyección de SQL | Lista blanca de campos y operadores; valores siempre parametrizados; prueba dedicada |
| El catálogo cambia y las preferencias guardadas quedan con claves viejas | Se ignoran al leer; las columnas nuevas aparecen al final con su visibilidad por defecto |
| Las cifras no cuadran con la referencia por criterios distintos | Se documenta la diferencia en el PR; manda el fundamento, no la coincidencia |
| Sin datos reales no se pueden verificar los criterios 1 a 4 | Se desarrolla con datos sintéticos; esos criterios quedan pendientes y visibles hasta cargar los CFDI |

## Dudas abiertas

1. **Periodo de los complementos de pago y de la nómina.** La referencia muestra "fecha
   de pago" en esas pestañas. Si sus conteos corresponden a la fecha de pago y no a la
   de emisión, la decisión D5 cambia para esos dos tipos. Se resuelve comparando
   conteos con datos reales en F3.5.
2. **Qué permite descargar el SAT de CFDI cancelados** (XML o solo metadatos). Se
   verifica al implementar F3.5; define si ese punto se queda en F3 o pasa a F2.
3. **Subsidio causado y ajuste de ISR retenido en nómina**: de qué nodo salen con las
   reglas vigentes. Lo confirma el agente `dominio-fiscal` antes de F3.5.
