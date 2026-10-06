# M7.2 — Suscripción: historial, pagos manuales y datos fiscales

Fecha: 2026-10-06. Carril D. Estado: en implementación.
Antecedente: `2026-10-04-m7-1-suscripcion-design.md` (planes, límite de RFC y
asignación manual).

## Decisión D10 de Carlos (2026-10-06)

- Se pospone el cobro en línea: los planes se asignan a mano desde la administración,
  como en M7.1. Sin proveedores de pago ni claves.
- El CFDI de la suscripción se emite fuera de FiscalCore. FiscalCore solo guarda los
  datos fiscales del cliente (RFC, razón social, régimen, código postal y uso del CFDI)
  y un historial de pagos que registra a mano el administrador de la plataforma.
- Avisos de vencimiento próximo, solo en la interfaz (sin correos).

## Objetivo

Que cada cuenta vea su plan, su uso de RFC contra el límite, la vigencia, el historial
de su plan, sus pagos y sus datos de facturación, y que se le avise antes de que venza.
Que el administrador de la plataforma registre pagos y capture los datos fiscales.

## Alcance

Entra:

- Historial de asignaciones de plan por cuenta.
- Datos fiscales del cliente (RFC, razón social, régimen, código postal, uso del CFDI y
  correo): los capturan y corrigen la cuenta y el administrador.
- Pagos registrados a mano por el administrador (fecha, monto, meses, referencia, folio
  o UUID del CFDI emitido). Cada pago extiende la vigencia en la misma transacción. Un
  pago no se borra: se anula con motivo. La cuenta ve los suyos; el administrador ve
  además quién los registró y el motivo de las anulaciones.
- Avisos de vencimiento en la interfaz: en «Mi suscripción» desde 15 días antes y
  después de vencer; en la administración, una etiqueta por cuenta y la lista de cuentas
  activas por vencer o vencidas.

No entra: cobro en línea, timbrado del CFDI, editar un pago (se anula y se registra de
nuevo), envío de correos.

## Reglas

| Regla | Cómo se aplica |
|---|---|
| Fuente del historial | Tabla propia, no la auditoría: `registrar_evento` es de mejor esfuerzo (no lanza si falla), así que una asignación podría quedar sin rastro. La fila de historial se escribe en la misma transacción que actualiza `suscripciones` |
| Datos previos | La 065 siembra, para cada cuenta que ya tenía suscripción y no tiene historial, su asignación vigente como primera fila (con `updated_at` como fecha) |
| Privacidad | `notas` y `asignada_por` son internas: solo en la ruta de administración |
| Límite | Las 50 asignaciones más recientes y los 100 pagos más recientes |
| Datos fiscales | RFC válido (en mayúsculas); régimen del catálogo c_RegimenFiscal que corresponda a persona moral (RFC de 12) o física (RFC de 13); código postal de 5 dígitos; uso del catálogo c_UsoCFDI 4.0. No se valida la combinación régimen–uso (la revisa quien emite el CFDI). Se audita `suscripcion.datos_fiscales` |
| Pagos | Fecha no futura (hora de México); monto mayor que 0 y hasta 10 millones con hasta dos decimales, enviado como texto (un número con decimales se rechaza: pudo perder centavos); `meses` de 1 a 24 (1 por defecto); referencia hasta 200 caracteres, folio hasta 40 y UUID del CFDI (formato 8-4-4-4-12), opcionales. 409 si la cuenta no tiene plan asignado. Se audita `suscripcion.registrar_pago` |
| Vigencia al pagar | En la misma transacción, con la suscripción bloqueada (`FOR UPDATE`): si la vigencia no había vencido a la fecha del pago, se extiende desde ella; si ya venció o no tenía, desde la fecha del pago. Fin de mes: 31 de enero + 1 mes = 28 (o 29) de febrero. El pago guarda la vigencia anterior y la nueva, y el cambio queda en el historial ("Pago registrado") |
| Anular | Con motivo obligatorio; el pago queda como `anulado` (no se borra) y se audita `suscripcion.anular_pago`. Si la vigencia actual sigue siendo la que dejó ese pago, vuelve a la anterior (historial: "Pago anulado"); si otro pago o una asignación la movió después, no se toca y la respuesta lo dice (`vigencia_revertida: false`) |
| Aviso de vencimiento | `dias_para_vencer`: días que faltan si la suscripción activa vence en 15 días o menos (0 = hoy), negativo si ya venció; null si no hay aviso o si está suspendida o cancelada |
| Lista de vencimientos | Cuentas con suscripción activa que vencen en 15 días o menos o ya vencieron, de la que vence antes a la que vence después (hasta 500) |

## Datos

Migración `065_suscripciones_historial.sql` (idempotente): tabla
`suscripciones_historial (usuario_id, plan_clave, estado, vigente_hasta, notas,
asignada_por, creada_en)` con índice `(usuario_id, creada_en DESC)` y la siembra
descrita.

Migración `066_suscripciones_pagos.sql` (idempotente): `suscripciones_datos_fiscales`
(una fila por cuenta, RFC en mayúsculas y CP de 5 dígitos por CHECK) y
`suscripciones_pagos` (monto > 0, meses de 1 a 24, estado `activo`/`anulado` y un
anulado siempre con motivo y fecha, por CHECK; vigencia anterior y nueva) con índice
`(usuario_id, fecha DESC)`. Las dos se borran con la cuenta.

## API

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `GET /api/v1/suscripcion/historial` | usuario | Mis asignaciones `{fecha, plan_clave, plan_nombre, estado, vigente_hasta}` |
| `GET /api/v1/suscripcion/admin/cuentas/{id}/historial` | admin de plataforma | Lo mismo, más `notas` y `asignada_por` (correo); 404 si la cuenta no existe |
| `GET /api/v1/suscripcion` | usuario | Ahora también `dias_para_vencer` |
| `GET`/`PUT /api/v1/suscripcion/datos-fiscales` | usuario | Mis datos fiscales (o null); guardarlos (422 con datos inválidos) |
| `GET /api/v1/suscripcion/pagos` | usuario | Mis pagos `{id, fecha, monto, referencia, folio_cfdi}` |
| `GET`/`PUT /api/v1/suscripcion/admin/cuentas/{id}/datos-fiscales` | admin de plataforma | Ver o capturar; 422 con datos inválidos |
| `GET`/`POST /api/v1/suscripcion/admin/cuentas/{id}/pagos` | admin de plataforma | Ver (con `registrado_por` y `motivo_anulacion`) o registrar y extender la vigencia (201); 422 con datos inválidos, 409 sin plan |
| `POST /api/v1/suscripcion/admin/cuentas/{id}/pagos/{pago}/anular` `{motivo}` | admin de plataforma | Anula; `{vigencia_revertida}`; 404 si no hay un pago activo con ese id en la cuenta |
| `GET /api/v1/suscripcion/admin/vencimientos` | admin de plataforma | Lista de vencimientos |
| `GET /api/v1/suscripcion/admin/cuentas` | admin de plataforma | Ahora también `dias_para_vencer` por cuenta (negativo si venció) |

## Pantallas

- `/suscripcion`: aviso de vencimiento («vence en N días», «vence hoy», «venció hace N
  días») en la tarjeta del plan; tarjeta "Pagos y facturación" con el formulario de
  datos fiscales y la tabla de pagos (los anulados tachados); tarjeta "Historial de tu
  plan" (fecha con hora local).
- Administración de suscripciones: lista "Por vencer y vencidas", etiqueta de
  vencimiento por cuenta y botón "Detalle" que despliega el historial, el formulario de
  datos fiscales, el de registrar un pago (con meses y UUID) y la lista de pagos con
  "Anular" (pide el motivo).

## Criterios de aceptación

1. Dos asignaciones seguidas dejan dos filas, de la más reciente a la más antigua.
2. La cuenta no ve notas ni quién asignó; el administrador sí.
3. Un usuario que no es administrador de la plataforma recibe 403 en la ruta de
   administración; una cuenta inexistente da 404.
4. La 065 siembra la asignación vigente una sola vez aunque se repita.
5. Datos fiscales con régimen de persona física en un RFC de persona moral dan 422; los
   válidos se guardan en mayúsculas y la cuenta los ve.
6. Un pago con fecha futura da 422 y sin plan asignado, 409. Un pago de 1 mes con la
   vigencia en 10 días la lleva a un mes después de esa fecha; uno de 12 meses parte de
   la nueva. Con la suscripción vencida, el pago extiende desde su fecha. La cuenta no
   ve quién los registró. Solo el administrador de la plataforma registra y anula.
7. Anular el primero de dos pagos no revierte la vigencia; anular el último la regresa a
   la anterior. Un pago ya anulado da 404 al anularlo otra vez.
8. Con vencimiento en 5 días, `dias_para_vencer = 5`; vencida hace 3, −3; con 30 días,
   null. La lista de vencimientos trae la vencida antes que la por vencer y no trae
   suspendidas.
9. La cuenta y el administrador guardan los datos fiscales; la auditoría dice quién.
