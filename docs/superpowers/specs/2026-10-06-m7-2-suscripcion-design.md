# M7.2 — Suscripción: historial y cobro en línea

Fecha: 2026-10-06. Carril D. Estado: historial en implementación; cobro pendiente de
decisión.
Antecedente: `2026-10-04-m7-1-suscripcion-design.md` (planes, límite de RFC y
asignación manual).

## Objetivo

Que cada cuenta vea cómo ha cambiado su plan y que el administrador de la plataforma vea
el historial completo de una cuenta. Después, cobrar la suscripción en línea.

## Alcance

Entra ahora (no depende del proveedor de cobro):

- Historial de asignaciones de plan por cuenta: plan, estado, vigencia y fecha de cada
  asignación.
- La cuenta ve el suyo sin notas internas ni quién asignó. El administrador de la
  plataforma ve el de cualquier cuenta, con notas y con quién asignó.

Pendiente de Carlos (la coordinación le preguntó el 2026-10-06):

- Proveedor de cobro: Stripe, Mercado Pago o Conekta.
- Cómo se emite el CFDI de la suscripción: quién timbra, con qué datos fiscales del
  cliente y si es por pago o global.

## Reglas

| Regla | Cómo se aplica |
|---|---|
| Fuente del historial | Tabla propia, no la auditoría: `registrar_evento` es de mejor esfuerzo (no lanza si falla), así que una asignación podría quedar sin rastro. La fila de historial se escribe en la misma transacción que actualiza `suscripciones` |
| Datos previos | La 065 siembra, para cada cuenta que ya tenía suscripción y no tiene historial, su asignación vigente como primera fila (con `updated_at` como fecha) |
| Privacidad | `notas` y `asignada_por` son internas: solo en la ruta de administración |
| Límite | Las 50 asignaciones más recientes |

## Datos

Migración `065_suscripciones_historial.sql` (idempotente): tabla
`suscripciones_historial (usuario_id, plan_clave, estado, vigente_hasta, notas,
asignada_por, creada_en)` con índice `(usuario_id, creada_en DESC)` y la siembra
descrita.

## API

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `GET /api/v1/suscripcion/historial` | usuario | Mis asignaciones `{fecha, plan_clave, plan_nombre, estado, vigente_hasta}` |
| `GET /api/v1/suscripcion/admin/cuentas/{id}/historial` | admin de plataforma | Lo mismo, más `notas` y `asignada_por` (correo); 404 si la cuenta no existe |

## Pantallas

- `/suscripcion`: tarjeta "Historial de tu plan" debajo de los planes.
- Administración de suscripciones: botón "Historial" por cuenta que despliega su
  historial completo.

## Criterios de aceptación

1. Dos asignaciones seguidas dejan dos filas, de la más reciente a la más antigua.
2. La cuenta no ve notas ni quién asignó; el administrador sí.
3. Un usuario que no es administrador de la plataforma recibe 403 en la ruta de
   administración; una cuenta inexistente da 404.
4. La 065 siembra la asignación vigente una sola vez aunque se repita.
