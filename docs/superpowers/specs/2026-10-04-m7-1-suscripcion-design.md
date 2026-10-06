# M7.1 — Suscripción: planes, límite de RFC y asignación manual

Fecha: 2026-10-04. Carril D. Estado: en implementación.
Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md` (M7, decisión D3).

## Decisiones de Carlos (2026-10-04)

| Pregunta | Respuesta |
|---|---|
| Cobro | Primero **sin cobro en línea**: un administrador de la plataforma asigna el plan a mano y el pago se registra aparte. El cobro en línea (Stripe, Mercado Pago o Conekta) es M7.2 y se monta sobre esto sin rehacerlo |
| Qué limita el plan | **Número de RFC (empresas)** por cuenta |
| Planes y precios | **Valores de ejemplo editables** sin tocar código; Carlos los ajusta después |

## Alcance

Entra:

- Catálogo de planes en la base (nombre, precio mensual sin IVA, máximo de RFC, activo,
  orden) con valores de ejemplo.
- Suscripción por cuenta de usuario: plan, estado, vigente hasta, notas y quién la
  asignó.
- Cálculo del uso (RFC que administra la cuenta) y de si puede agregar otro.
- Función para que `POST /mis-empresas` (carril B) valide el límite; la llamada la agrega
  B (pedido entre carriles). Mientras tanto el límite se muestra pero no bloquea.
- Pantalla **Suscripción** para cada usuario y, para el administrador de la plataforma,
  la asignación de planes y la edición del catálogo.

No entra:

- Cobro en línea, recibos, renovación automática (M7.2).
- Emitir el CFDI de la suscripción: el despacho que cobra debe facturar; se resuelve con
  el proveedor de cobro o el facturador de Carlos en M7.2.
- Límites de usuarios o de funciones (Carlos eligió solo RFC).

## Reglas

| Regla | Cómo se aplica |
|---|---|
| A quién pertenece la suscripción | A la cuenta de usuario (el titular del despacho) |
| Qué cuenta como RFC usado | Empresas activas donde la cuenta es **administrador** (regla de U1: el marcado, o el primer vinculado si la empresa no tiene ninguno). Las empresas donde solo es contador no cuentan: las paga quien las administra |
| Plan efectivo | El de la suscripción si está `activa` y `vigente_hasta` es nulo o no ha pasado (fecha de la Ciudad de México). Si no hay suscripción, está suspendida, cancelada o vencida: el plan marcado `por_defecto` |
| Límite | `max_rfc` nulo = ilimitado. Puede agregar si `uso < max_rfc`. Bajar de plan no quita acceso a lo que ya tiene; solo impide agregar |
| Administrador de la plataforma | `usuarios.rol = 'admin'`: sin límite y es quien asigna planes y edita el catálogo |
| Precios | `Decimal` con dos decimales, en MXN, **sin IVA**; la pantalla muestra "más IVA" |
| Auditoría | Asignar plan y editar un plan quedan en `auditoria` |

Planes de ejemplo (editables): `prueba` "Prueba" $0, 1 RFC, por defecto; `basico`
"Básico" $499, 3 RFC; `despacho` "Despacho" $1,499, 15 RFC; `ilimitado` "Ilimitado"
$3,999, sin límite.

## Datos

Migración `063_suscripciones.sql` (idempotente):

```sql
CREATE TABLE IF NOT EXISTS planes (
    clave           VARCHAR(30) PRIMARY KEY CHECK (clave ~ '^[a-z][a-z0-9_]{1,29}$'),
    nombre          VARCHAR(80) NOT NULL,
    precio_mensual  NUMERIC(12,2) NOT NULL CHECK (precio_mensual >= 0),
    max_rfc         INTEGER CHECK (max_rfc IS NULL OR max_rfc >= 0),
    por_defecto     BOOLEAN NOT NULL DEFAULT FALSE,
    activo          BOOLEAN NOT NULL DEFAULT TRUE,
    orden           INTEGER NOT NULL DEFAULT 0,
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_planes_por_defecto ON planes (por_defecto) WHERE por_defecto;
INSERT INTO planes (...) VALUES (...) ON CONFLICT (clave) DO NOTHING;   -- los de ejemplo

CREATE TABLE IF NOT EXISTS suscripciones (
    usuario_id     UUID PRIMARY KEY REFERENCES usuarios(id) ON DELETE CASCADE,
    plan_clave     VARCHAR(30) NOT NULL REFERENCES planes(clave),
    estado         VARCHAR(20) NOT NULL DEFAULT 'activa' CHECK (estado IN ('activa', 'suspendida', 'cancelada')),
    vigente_hasta  DATE,
    notas          TEXT,
    asignada_por   UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    updated_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

`ON CONFLICT DO NOTHING` deja intactos los planes que Carlos ya haya editado.

## Módulos

- `backend/suscripcion.py` (puro): plan efectivo, uso y límite, validación de cambios de
  plan y de asignación.
- `backend/suscripcion_datos.py`: lecturas y escrituras, y
  `verificar_alta_rfc(cur, usuario_id, de_tercero=False)` (lanza `LimiteRfcAlcanzado`
  con el mensaje para el usuario; ver "Contrato del límite").
- `backend/routers/suscripcion.py`.

## Contrato del límite

Toda operación que haga a una cuenta administrar un RFC más llama a
`verificar_alta_rfc(cur, usuario_id)` **con el cursor de su propia transacción y antes
del INSERT/UPDATE** que crea el vínculo de administrador, y responde 403 con el mensaje
de `LimiteRfcAlcanzado`. La función toma `pg_advisory_xact_lock` por cuenta antes de
contar: dos altas simultáneas de la misma cuenta se forman y la segunda cuenta ya con
la primera confirmada (sin el candado, con `max_rfc = 1` pasaban las dos). El candado
se suelta al terminar la transacción.

| Operación | Carril | Cuenta que se verifica |
|---|---|---|
| `POST /mis-empresas` (crear empresa) | B (pedido) | quien la crea |
| Aprobar una invitación de administrador | D (U1) | la persona aprobada (`de_tercero=True`) |
| Cambiar el rol de alguien a administrador | D (U1) | la persona promovida (`de_tercero=True`) |

Validación de la administración: `plan_clave`, `estado`, `notas`, `nombre` que no son
texto y `activo` que no es booleano dan 422 (antes, 500 o `bool("false") == True`). La
búsqueda de cuentas trata `%` y `_` como literales. La siembra de la 063 no marca
`prueba` como plan por defecto si al reinsertarla ya hay otro.

## API

| Método y ruta | Quién | Qué hace |
|---|---|---|
| `GET /api/v1/suscripcion` | usuario | Mi plan efectivo, estado, vigencia, uso de RFC y si puedo agregar |
| `GET /api/v1/suscripcion/planes` | usuario | Planes activos |
| `GET /api/v1/suscripcion/admin/cuentas?q=` | admin | Hasta 200 cuentas con su plan, estado y uso (búsqueda por correo o nombre) |
| `PUT /api/v1/suscripcion/admin/cuentas/{usuario_id}` | admin | Asigna `{plan_clave, estado, vigente_hasta, notas}` |
| `PUT /api/v1/suscripcion/admin/planes/{clave}` | admin | Edita `{nombre, precio_mensual, max_rfc, activo}`; crea el plan si no existe |

403 para quien no es admin en `/admin/*`; 422 con plan inexistente o inactivo, estado
desconocido, precio negativo, límite negativo o fecha inválida.

## Pantalla

`/suscripcion` (entrada "Suscripción" en el menú, grupo de cuenta): tarjeta con el plan,
precio "más IVA", vigencia, barra de uso "2 de 3 RFC" y aviso al llegar al límite;
tabla de planes. Si la sesión es de administrador de la plataforma: sección
"Administración" con buscador de cuentas, asignación por fila y edición de planes.

## Criterios de aceptación

1. Una cuenta sin suscripción tiene el plan por defecto; con 1 empresa que administra,
   `puede_agregar_rfc = false`.
2. Asignado `despacho` vigente: límite 15. Vencido (`vigente_hasta` ayer) o suspendido:
   vuelve al por defecto.
3. Las empresas donde la cuenta es solo contador no cuentan en el uso.
4. Un admin de plataforma no tiene límite.
5. Un no admin recibe 403 en `/admin/*`.
6. Editar un plan cambia el límite efectivo de todas las cuentas que lo tienen.
7. `verificar_alta_rfc` lanza al llegar al límite y no lanza por debajo. Dos altas
   concurrentes de una cuenta con plan de 1 RFC: una pasa y la otra recibe el límite.
