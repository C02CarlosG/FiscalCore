# V1 — Validaciones de CFDI

Fecha: 2026-10-04. Carril D. Estado: en implementación.
Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md` ("Detalle de las entregas", V1).
Referencia: `2026-10-01-referencia-plataforma.md`, sección "Validaciones".

## Objetivo

Una pantalla con tarjetas que cuentan, para el periodo y el acumulado del ejercicio,
los CFDI con posibles situaciones incorrectas, separados en emitidos y recibidos. El
contador ve de un vistazo qué revisar y, con un clic, la lista de comprobantes que
componen cada número. Cada validación se puede apagar y el umbral de efectivo se puede
ajustar por empresa.

## Alcance

Entra:

- Cuatro validaciones sobre la tabla `cfdi` (ya cargada), sin volver a leer el XML.
- Conteo del periodo (`YYYY-MM`) y del acumulado (enero al mes del periodo), por
  dirección.
- Lista de los CFDI de cada tarjeta (tope 500 filas por consulta).
- Configuración por empresa: validaciones activas y umbral de efectivo.

No entra:

- Corregir ni cancelar CFDI; solo se señalan.
- Mezclar estas validaciones con el motor de riesgos de conciliación (`riesgos.py`,
  carril C): se exponen aparte. Unirlas en un solo tablero es M1/M3.
- La navegación al listado de CFDI con filtros (M1, carril A); aquí la lista es propia.

## Reglas

Solo CFDI **vigentes**. Emitidos: `rfc_emisor = empresas.rfc`; recibidos:
`rfc_receptor = empresas.rfc`. Fecha: `fecha_emision`, con el mismo rango de mes que el
listado de CFDI (`cfdi_listado.rango`).

| Clave | Dirección | Condición | Por qué se señala |
|---|---|---|---|
| `pue_forma_99` | emitidos y recibidos | Ingreso (`I`), método `PUE`, forma de pago `99` | En PUE el pago ya ocurrió, así que la forma de pago debe ser la real; "99 Por definir" corresponde a PPD (Anexo 20, Guía de llenado del CFDI 4.0, campos MetodoPago y FormaPago) |
| `pue_con_rep` | emitidos y recibidos | Ingreso `PUE` con al menos un complemento de pago **vigente** que lo relaciona (`pagos_relaciones.cfdi_uuid`) | Un PUE se liquida al emitirse; si tiene REP, se debió emitir como PPD (regla 2.7.1.32 de la RMF sobre el método de pago, 2.7.1.35 en RMF anteriores; numeración a confirmar en la revisión fiscal). El ingreso podría contarse dos veces en flujo |
| `egreso_sin_relacion` | emitidos y recibidos | Egreso (`E`) sin `cfdi_relacionados` | La nota de crédito debe relacionar el CFDI que disminuye (Guía de llenado, nodo CfdiRelacionados, tipo de relación 01). Sin relación no se sabe a qué periodo e ingreso afecta |
| `no_bancarizado` | solo recibidos | Ingreso con forma de pago `01` (efectivo) y total en pesos **mayor** al umbral (2,000 por defecto) | No deducible (art. 27-III LISR) ni acreditable (art. 5-I LIVA) si el pago en efectivo excede $2,000. Es la misma regla que ya usan `iva.py` y `deducciones.py` (`UMBRAL_EFECTIVO`) |

Total en pesos: `total × tipo_cambio` (1 si es nulo o cero), como en el listado.

## Datos

Migración `061_validaciones_cfdi_config.sql` (idempotente):

```sql
CREATE TABLE IF NOT EXISTS validaciones_cfdi_config (
    empresa_id  UUID PRIMARY KEY REFERENCES empresas(id) ON DELETE CASCADE,
    config      JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    usuario_id  UUID REFERENCES usuarios(id) ON DELETE SET NULL
);
```

`config = {"inactivas": ["pue_con_rep"], "umbral_efectivo": "2000.00"}`. Lo que falta
toma el valor por defecto; las claves desconocidas se ignoran al leer.

## Módulos

- `backend/validaciones_cfdi.py` (puro): catálogo de validaciones, `Configuracion`
  (validación y valores por defecto, umbral en `Decimal`), `rangos(periodo)` y la
  condición SQL parametrizada de cada validación.
- `backend/validaciones_cfdi_datos.py`: una sola consulta con `COUNT(*) FILTER` por
  validación, periodo y acumulado; la lista de CFDI de una tarjeta; leer y guardar la
  configuración.
- `backend/routers/validaciones_cfdi.py`: rutas delgadas.

## API

Prefijo `/api/v1/validaciones-cfdi/empresas/{empresa_id}`; sesión y acceso a la empresa.

| Método y ruta | Qué hace |
|---|---|
| `GET /?periodo=YYYY-MM` | `{periodo, configuracion, emitidos: [Tarjeta], recibidos: [Tarjeta]}`; `Tarjeta = {clave, titulo, descripcion, activa, periodo, acumulado}`; una tarjeta inactiva trae conteos `null` |
| `GET /cfdis?periodo&direccion&validacion&alcance=periodo\|acumulado` | Hasta 500 CFDI `{uuid, fecha_emision, serie, folio, rfc, nombre, total, moneda, forma_pago, metodo_pago}` y `total_filas` |
| `GET /configuracion` | Configuración vigente (con valores por defecto) |
| `PUT /configuracion` | Guarda `{inactivas: [...], umbral_efectivo}`; 422 con claves desconocidas o umbral negativo |

422 por periodo, dirección, validación o alcance inválidos; `no_bancarizado` con
`direccion=emitidos` es 422.

## Pantalla

`/empresas/{id}/validaciones`, entrada "Validaciones" en el menú. Selector de periodo
(`PeriodSelector`), dos bloques (Emitidos, Recibidos) con una tarjeta por validación:
título, conteo del periodo grande y acumulado debajo. Clic en la tarjeta: diálogo con la
lista de CFDI (periodo o acumulado). Botón de engrane: diálogo de configuración con un
interruptor por validación y el umbral de efectivo.

## Criterios de aceptación

Con una empresa sembrada en marzo de 2026 (y febrero para el acumulado):

1. Un ingreso emitido PUE con forma 99 en marzo y otro en febrero: periodo 1, acumulado 2.
2. Un PUE con REP vigente cuenta; si el REP está cancelado, no.
3. Un egreso sin relacionados cuenta; con `cfdi_relacionados` no vacío, no.
4. Recibido en efectivo por 2,000.00 no cuenta; por 2,000.01 sí; en USD por 150 con tipo
   de cambio 17 (2,550 pesos) sí. Con umbral 3,000 el de 2,550 deja de contar.
5. Un CFDI cancelado nunca cuenta. Un CFDI de otra empresa nunca cuenta.
6. Una validación inactiva devuelve conteos `null` y su lista responde vacía.
7. La lista de una tarjeta trae exactamente los UUID que se cuentan.

## Pruebas

Unitarias del módulo puro; router con base mockeada; E2E `-m db` con la siembra de los
criterios; migración 061 idempotente; vitest de la pantalla.
