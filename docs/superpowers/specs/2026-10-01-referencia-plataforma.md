# Referencia funcional de la plataforma de comparación

Fecha: 2026-10-01. Fuente: recorrido en vivo de la plataforma de referencia (cuenta de
prueba de COPLASUR), solo lectura, más las 26 capturas analizadas antes. Complementa al
plan maestro (`2026-10-01-paridad-y-mejoras-roadmap.md`): aquí está **cómo se comporta**
cada pantalla, para escribir las specs de F2 a F8 sin volver a abrirla.

Se describe comportamiento, no diseño visual: FiscalCore conserva su propio sistema
visual y no copia marca ni textos.

## Mapa de navegación

| Menú | Submenú | Fase de FiscalCore |
|---|---|---|
| Inicio | — | F4 |
| CFDIs | Emitidos, Recibidos | F3 |
| Impuestos | IVA base flujo, ISR base flujo | F5, F7 |
| DIOT | Generar DIOT, Proveedores | F6 |
| Exportaciones | — | F3 (cola de exportaciones) |
| EFOS | — | M3 |
| Validaciones | — | M1 / M3 |
| Sincroniza SAT | Información Fiscal, Descargas CFDIs, Actualizar e.firma | F2, F8 |
| Configuración | Perfil de usuario, Usuarios, Notificaciones, Reiniciar | M3, M4 |
| Suscripción | — | M7 |
| Soporte | Sitio, WhatsApp, chat, correo, capacitación | fuera de alcance |

Comunes a todas las pantallas: selector de empresa arriba a la derecha, icono de ayuda
"?" junto al título, y un indicador fijo al pie del menú con el estado y la hora de la
última descarga del SAT.

## Hallazgos que cambian el diseño ya planeado

### El estado de cada pantalla vive en la URL

Periodo, tipo de comprobante, estado y variante de cancelación son parámetros de la
URL (periodo, tipo, estado, alcance de cancelación). Consecuencias para F3:

- Un listado filtrado se puede compartir, recargar y abrir en otra pestaña.
- El periodo se conserva al cambiar de pantalla.
- En FiscalCore el periodo hoy es estado local de cada página y se pierde al navegar.

### CFDIs emitidos / recibidos (F3)

- **Barra superior**: periodo, búsqueda (UUID, RFC o nombre), filtro avanzado,
  Vigentes / Cancelados / Todos, PUE / PPD / Todos, Exportar.
- **Cancelados** agrega un segundo selector con el alcance ("cancelados y emitidos en el
  mes" y variantes) y una columna "Fecha de cancelación". Los totales muestran guiones
  cuando no hay datos, no ceros.
- **Pestañas por tipo** con contador: Ingreso, Egreso, Traslado, Nómina, Pago. El
  contador respeta los filtros activos.
- **Totales**: dos renglones (Periodo y Acumulado del ejercicio) con editor de columnas
  propio.
- **Fila**:
  - "+" despliega los conceptos dentro de la tabla, con su propia paginación
    ("6 conceptos") y columnas configurables (las de "Detalles" del editor).
  - Un icono abre el **visor del CFDI** en una ventana: etiquetas de tipo y estado,
    serie y folio, emisor y receptor con régimen y domicilio, folio fiscal, fecha y
    hora, certificado, conceptos, subtotal / traslados / total, moneda, forma y método
    de pago, uso. Al pie: selector de etiquetas, descarga del XML y del PDF, y acceso a
    las evidencias. **Este visor no estaba en el plan de F3 y hay que agregarlo**; el
    PDF implica generar una representación impresa del CFDI.
  - Icono para adjuntar evidencia y casilla de selección para acciones en lote.
- **Exportar** no descarga al momento: crea un trabajo que aparece en "Exportaciones".

### Exportaciones (nuevo, va con F3)

Pantalla con pestañas por origen (CFDIs, Detalle de base IVA, Detalle de base ISR,
Evidencias, DIOT). Cada exportación tiene fecha de creación, **fecha de expiración**,
rango, efecto y tipo de comprobante, formato y acciones (descargar). Es decir, las
exportaciones son trabajos asíncronos con archivo temporal, no respuestas directas.

Para FiscalCore: con volúmenes chicos basta la descarga directa que ya existe para
otros reportes; la cola solo se justifica con listados grandes. Decidirlo en la spec de
F3.

### Descargas de CFDI (F2)

- **Descargas diarias**: una fila por **fecha de emisión**, con estatus y cuatro
  conteos: emitidos que tiene el SAT, emitidos descargados, recibidos que tiene el SAT,
  recibidos descargados. La comparación "lo que tiene el SAT contra lo descargado" es
  el control de integridad, y exige consultar metadatos además de los XML.
- **Descarga inicial (histórica)**: un renglón con fecha de inicio y fin (desde varios
  años atrás hasta la fecha de alta) y los mismos conteos.
- Botón de **descarga manual** y de refrescar.

Para FiscalCore: el plan de F2 hablaba de solicitudes por mes; conviene llevar el
control **por día de emisión** con los conteos del SAT, que es lo que permite demostrar
que no falta nada. La pantalla "Conexión SAT" actual muestra solicitudes, no este
cuadro.

### Actualizar e.firma (hecho en FiscalCore)

Muestra RFC y fecha de expiración de la configuración actual, y un formulario con
certificado, llave y contraseña. Equivale a la tarjeta de e.firma de "Conexión SAT".

### Validaciones (nuevo; encaja con los riesgos de FiscalCore)

Tarjetas con conteo del periodo y acumulado de CFDI con posibles situaciones
incorrectas, separadas en emitidos y recibidos:

- Ingresos PUE con forma de pago "99" (por definir); en recibidos, además, no
  bancarizados.
- Ingresos PUE con CFDI de pago relacionados.
- Egresos sin CFDI relacionados.

Tiene configuración propia (icono de engrane). FiscalCore ya detecta riesgos de
conciliación; estas son validaciones puramente de CFDI que se pueden sumar al mismo
motor de riesgos.

### EFOS (M3)

Mismo esqueleto que el listado de CFDI (filtros, totales, tabla con editor de
columnas), limitado a comprobantes de emisores en el listado del SAT, con columna de
estatus, fecha de última actualización del listado y botón para consultarlo completo.

### Notificaciones (M3)

Tres avisos por correo, cada uno con su lista de destinatarios: CFDI con error,
operaciones con EFOS y CFDI cancelados.

### Configuración

"Reiniciar" es una acción destructiva sobre los datos de la empresa: no se abrió.
"Usuarios" y "Perfil de usuario" no se revisaron a detalle.

## Segundo recorrido (2026-10-02)

### Listado de CFDI: lo que faltaba

- **Recibidos** tiene la misma estructura que Emitidos, con emisor en lugar de receptor.
  Cada fila ofrece "Agregar" en las columnas de etiquetas y comentarios.
- **Parámetros de la URL** observados: periodo, tipo de comprobante, estado
  (activo / inactivo), método (todos / PUE / PPD), sub-filtro de PPD y alcance de
  cancelación.
- **PPD** agrega un selector: pendientes de pago, totalmente pagadas, ambos.
- **Filtro avanzado**: ventana con renglones de (campo, operador, valor) que se pueden
  agregar y quitar; el campo se elige de la lista completa de columnas (RFC, serie,
  folio, fecha, versión, régimen, "tiene XML", "no considerar IVA", etc.).
- **Columnas por tipo de comprobante** (cada pestaña tiene su propio juego):
  - Ingreso y Egreso: fecha de expedición, serie, folio, RFC y nombre de la contraparte,
    total, saldo de la factura, CFDI de pago relacionados, subtotal, descuento, neto,
    traslado de IVA, UUID que sustituye, uso, método y forma de pago, etiquetas,
    comentarios. Totales: retenciones y traslados de IVA, IEPS e ISR, subtotal,
    descuento, neto y total.
  - **Nómina**: fecha de pago, RFC y nombre del empleado, tipo de régimen, sueldos,
    otras percepciones, gravado, exento, ISR retenido, ajuste de ISR retenido, otras
    deducciones, subsidio causado, neto a pagar. Totales con las mismas cifras más
    **número de empleados**.
  - **Pago**: fecha de pago, serie, folio, contraparte, bases de IVA al 16 %, 8 %, 0 % y
    exento, traslado y retención de IVA, total. Totales con las mismas bases más "total
    de pagos relacionados".
- Las cifras de septiembre cambiaron respecto a las capturas del 29 de septiembre
  (por ejemplo, el IVA trasladado cobrado pasó de 3,190,362.48 a 3,798,239.51) porque
  el mes siguió recibiendo comprobantes. **Las cifras de control solo valen comparadas
  el mismo día y con los mismos comprobantes descargados.**

### IVA base flujo

- Tres tarjetas que funcionan como pestañas: trasladado, acreditable y "a cargo" (este
  último solo muestra la resta).
- Trasladado: Totales, Facturas de contado, Cobro de facturas de crédito, Notas de
  crédito, No considerados, Periodo reasignado. Acreditable: lo mismo con "Pago de
  facturas de crédito".
- El conteo de cobros se muestra como "95 / 210": pagos del periodo contra documentos
  relacionados.
- El detalle por CFDI trae fecha de emisión **y fecha de pago**, las bases por tasa, el
  IVA por tasa, retenciones, total y, en acreditable, el UUID del pago.
- En acreditable hay muchos "No considerados" (134 en septiembre): la plataforma
  excluye por regla, no solo a mano. Las reglas hay que deducirlas en la spec de F5.
- Aviso fijo: no se consideran los CFDI de pago versión 1.0.

### ISR base flujo

- Dos tarjetas-pestaña: ingresos acumulables (con ISR retenido a favor) y deducciones
  (con ISR retenido a cargo).
- Deducciones: Totales, Facturas de contado, Pagos, Devoluciones/descuentos/
  bonificaciones emitidos, No considerados en el pre-llenado, Egresos recibidos,
  Inversiones, No considerados ISR.
- El porcentaje de nómina exenta deducible se elige en la propia tabla.

### DIOT

- Pestañas por región: Todos, Zona norte, Zona sur, IVA general, Importaciones
  tangibles, Importaciones intangibles.
- Columnas en cinco grupos: datos del tercero; actividades pagadas (total de actos y
  devoluciones por región); IVA acreditable (gravadas y con proporción por región);
  IVA no acreditable (no cumple, exentas, no objeto por región); datos adicionales.
- "Exportar DIOT" ofrece Excel y carga batch. "Agregar proveedor" ofrece crear uno o
  elegir uno existente.
- Tipo de tercero y tipo de operación son selectores por fila; se editan con el lápiz
  y se confirman con "Guardar cambios".

## Pendiente de revisar

- Opciones de "Exportar" en los listados (no se pulsó para no generar una exportación).
- Efecto de los interruptores "no considerar" y de la edición en línea de la DIOT (no
  se accionaron para no modificar datos).
- Usuarios y perfil.
