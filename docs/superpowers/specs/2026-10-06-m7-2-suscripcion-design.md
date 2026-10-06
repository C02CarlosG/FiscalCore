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
- Datos fiscales del cliente: los captura y corrige el administrador; la cuenta los ve.
- Pagos registrados a mano (fecha, monto, referencia y folio del CFDI emitido). La
  cuenta ve los suyos; el administrador ve además quién los registró.
- Aviso de vencimiento próximo en «Mi suscripción» y en la lista de cuentas del
  administrador.

No entra: cobro en línea, timbrado del CFDI, borrar o editar pagos (un error se corrige
con una nota en el siguiente pago; se puede agregar si Carlos lo pide), envío de correos.

## Reglas

| Regla | Cómo se aplica |
|---|---|
| Fuente del historial | Tabla propia, no la auditoría: `registrar_evento` es de mejor esfuerzo (no lanza si falla), así que una asignación podría quedar sin rastro. La fila de historial se escribe en la misma transacción que actualiza `suscripciones` |
| Datos previos | La 065 siembra, para cada cuenta que ya tenía suscripción y no tiene historial, su asignación vigente como primera fila (con `updated_at` como fecha) |
| Privacidad | `notas` y `asignada_por` son internas: solo en la ruta de administración |
| Límite | Las 50 asignaciones más recientes y los 100 pagos más recientes |
| Datos fiscales | RFC válido (en mayúsculas); régimen del catálogo c_RegimenFiscal que corresponda a persona moral (RFC de 12) o física (RFC de 13); código postal de 5 dígitos; uso del catálogo c_UsoCFDI 4.0. No se valida la combinación régimen–uso (la revisa quien emite el CFDI). Se audita `suscripcion.datos_fiscales` |
| Pagos | Fecha no futura (hora de México); monto mayor que 0 y hasta 10 millones con hasta dos decimales, enviado como texto (un número con decimales se rechaza: pudo perder centavos); referencia hasta 200 caracteres y folio hasta 40, opcionales. Se audita `suscripcion.registrar_pago` |
| Aviso de vencimiento | Si la suscripción está vigente y `vigente_hasta` cae dentro de los próximos 15 días (hoy incluido), `dias_para_vencer` trae los días que faltan; si no, null. Una vencida ya se explica con el motivo del plan por defecto |

## Datos

Migración `065_suscripciones_historial.sql` (idempotente): tabla
`suscripciones_historial (usuario_id, plan_clave, estado, vigente_hasta, notas,
asignada_por, creada_en)` con índice `(usuario_id, creada_en DESC)` y la siembra
descrita.

Migración `066_suscripciones_pagos.sql` (idempotente): `suscripciones_datos_fiscales`
(una fila por cuenta, RFC en mayúsculas y CP de 5 dígitos por CHECK) y
`suscripciones_pagos` (monto > 0 por CHECK) con índice `(usuario_id, fecha DESC)`. Las
dos se borran con la cuenta.

## API

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `GET /api/v1/suscripcion/historial` | usuario | Mis asignaciones `{fecha, plan_clave, plan_nombre, estado, vigente_hasta}` |
| `GET /api/v1/suscripcion/admin/cuentas/{id}/historial` | admin de plataforma | Lo mismo, más `notas` y `asignada_por` (correo); 404 si la cuenta no existe |
| `GET /api/v1/suscripcion` | usuario | Ahora también `dias_para_vencer` |
| `GET /api/v1/suscripcion/datos-fiscales` | usuario | Mis datos fiscales o null |
| `GET /api/v1/suscripcion/pagos` | usuario | Mis pagos `{id, fecha, monto, referencia, folio_cfdi}` |
| `GET`/`PUT /api/v1/suscripcion/admin/cuentas/{id}/datos-fiscales` | admin de plataforma | Ver o capturar; 422 con datos inválidos |
| `GET`/`POST /api/v1/suscripcion/admin/cuentas/{id}/pagos` | admin de plataforma | Ver (con `registrado_por`) o registrar (201); 422 con datos inválidos |
| `GET /api/v1/suscripcion/admin/cuentas` | admin de plataforma | Ahora también `dias_para_vencer` por cuenta |

## Pantallas

- `/suscripcion`: aviso de vencimiento próximo en la tarjeta del plan; tarjeta "Pagos y
  facturación" (datos fiscales y pagos) y tarjeta "Historial de tu plan".
- Administración de suscripciones: etiqueta "Vence en N días" por cuenta y botón
  "Detalle" que despliega el historial, el formulario de datos fiscales, el de registrar
  un pago y la lista de pagos.

## Criterios de aceptación

1. Dos asignaciones seguidas dejan dos filas, de la más reciente a la más antigua.
2. La cuenta no ve notas ni quién asignó; el administrador sí.
3. Un usuario que no es administrador de la plataforma recibe 403 en la ruta de
   administración; una cuenta inexistente da 404.
4. La 065 siembra la asignación vigente una sola vez aunque se repita.
5. Datos fiscales con régimen de persona física en un RFC de persona moral dan 422; los
   válidos se guardan en mayúsculas y la cuenta los ve.
6. Un pago con fecha futura da 422; dos pagos se listan del más reciente al más antiguo
   y la cuenta no ve quién los registró. Solo el administrador de la plataforma registra.
7. Con vencimiento en 5 días, `dias_para_vencer = 5` en «Mi suscripción» y en la lista
   del administrador; con 30 días, null.
