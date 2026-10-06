# U1 — Usuarios y perfil

Fecha: 2026-10-04. Carril D. Estado: en implementación.
Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md` ("Detalle de las entregas", U1).
Referencia: `2026-10-01-referencia-plataforma.md`, "Configuración → Perfil de usuario, Usuarios".

## Objetivo

Que cada usuario vea y edite su perfil y cambie su contraseña, y que quien administra
una empresa invite a otras personas con un rol, les cambie el rol o les
quite el acceso. Hoy una empresa solo la ve quien la creó y no hay forma de compartirla.

## Alcance

Entra:

- Pantalla **Perfil** (`/perfil`): datos de `GET /api/v1/auth/me` y
  `PATCH /api/v1/usuarios/perfil` (existentes, carril B; se usan sin editarlos) y cambio
  de contraseña (endpoint nuevo del carril D).
- Pantalla **Usuarios** por empresa (`/empresas/{id}/usuarios`): lista, invitaciones,
  cambio de rol y baja.
- **Invitaciones con doble confirmación** (decisión de Carlos, 2026-10-04): el
  administrador invita un correo; la persona acepta o rechaza desde su perfil (si no
  tiene cuenta, se registra con ese correo y la ve ahí); aceptar **no** da acceso: un
  administrador revisa quién aceptó y aprueba o rechaza.
- Roles por empresa en `usuario_empresas.rol`: `administrador` y `contador`.

No entra:

- Rol de solo lectura: exigiría revisar cada endpoint de escritura de los demás carriles.
  Si se pide, va en una entrega aparte con su pedido entre carriles.
- Envío del aviso por correo: no hay envío de correo (llega con M3). El administrador le
  dice a la persona que entre o se registre con ese correo.
- Verificación del correo con enlace: es del carril B (pedido de la coordinación, D9).
  Mientras no exista, la doble confirmación es la defensa contra quien se registra con
  un correo ajeno.
- Cuentas creadas por el administrador con contraseña temporal: se descartó en la
  revisión de seguridad (el administrador conocería la contraseña y la respuesta
  revelaría si el correo tenía cuenta).

## Reglas

| Regla | Cómo se aplica |
|---|---|
| Roles por empresa | `administrador`: todo lo de contador y además gestiona usuarios. `contador`: trabaja la empresa. El rol global `usuarios.rol = 'admin'` (administrador de la plataforma) puede gestionar cualquier empresa |
| Quién es administrador hoy | La migración 062 marca como `administrador` al primer usuario vinculado de cada empresa (su creador) si la empresa no tiene ninguno. Como `POST /mis-empresas` (carril B) sigue vinculando con el valor por defecto, el código aplica la misma regla al leer: si una empresa no tiene administrador, el primer vinculado actúa como tal. Pedido al carril B: vincular al creador como `administrador` |
| Siempre queda un administrador | No se puede quitar ni degradar al último administrador (409) |
| Invitación | Correo en minúsculas y sin espacios. La respuesta es la misma exista o no una cuenta con ese correo y nunca incluye su nombre. Nadie queda vinculado hasta que acepta. Re-invitar actualiza la pendiente. 409 si ya tiene acceso; 422 si es el propio correo (impide que un administrador de la plataforma se dé acceso a sí mismo). Límite: 20 por hora por usuario autenticado (no por IP) |
| Doble confirmación | Aceptar deja la invitación en `aceptada_pendiente` sin crear el vínculo. Los administradores ven en "Por aprobar" el nombre y el correo de la cuenta que aceptó (tal como se registró), cuándo se creó esa cuenta y cuándo aceptó, y aprueban o rechazan. Aprobar crea el vínculo con el rol invitado dentro de la transacción con `FOR UPDATE`; rechazar no lo crea. Solo administradores (403 a un contador); una invitación que no es de la empresa de la ruta, ya resuelta o vencida da 404 |
| Límite de RFC del plan (M7.1) | Aprobar a alguien como administrador o promoverlo a administrador le suma la empresa a su uso de RFC: en la misma transacción se llama a `verificar_alta_rfc(cur, persona, de_tercero=True)`, que toma el candado por cuenta. Si su plan ya no lo permite, 403 con el mensaje del plan de esa persona y no se crea ni cambia el vínculo. Como contador no cuenta |
| Estados | `pendiente` → `aceptada_pendiente` → `aprobada` / `rechazada_admin`; `pendiente` → `rechazada` (la persona) / `cancelada` (el administrador). Solo puede haber una abierta (`pendiente` o `aceptada_pendiente`) por empresa y correo |
| Vencimiento | Una invitación vale 7 días; vencida no se lista ni se acepta. Al aceptarla corren otros 7 días para aprobarla; vencida no se lista en "Por aprobar" ni se aprueba. Re-invitar renueva la abierta |
| Correo duplicado en mayúsculas | `usuarios.email` distingue mayúsculas. Si hay más de una cuenta con el mismo correo en minúsculas, ninguna ve ni acepta invitaciones a ese correo (404 uniforme) y se audita `cuenta.correo_ambiguo`. Se resuelve de fondo con un índice único sobre `lower(email)` (pedido al carril B, requisito de U1) |
| Empresa inactiva | Sus invitaciones no se listan ni se aceptan |
| Concurrencia | Invitar, cancelar, cambio de rol, baja y aceptar invitación leen los vínculos con `SELECT … FOR UPDATE` en la misma transacción que escriben: dos administradores que se quitan a la vez no dejan la empresa sin administrador |
| Administrador de plataforma | Ve la empresa, cambia roles y quita usuarios sin ser miembro; queda `via_admin_plataforma` en la auditoría |
| Cambio de contraseña | Exige la contraseña actual; la nueva tiene de 8 a 72 bytes (bcrypt ignora lo que pasa de 72) y es distinta de la actual. Límite de 5 intentos por minuto |
| Auditoría | Invitar, cancelar, aceptar, rechazar, aprobar (`cuenta.aprobar_invitacion`), rechazar la aceptación (`cuenta.rechazar_aceptacion`), cambio de rol (con los administradores que se fijaron), baja y cambio de contraseña quedan en `auditoria` (sin contraseñas) |

## Datos

Migración `062_roles_usuario_empresa.sql` (idempotente):

1. Por cada empresa sin `administrador`, marca como tal al vínculo con `created_at` más
   antiguo (desempate por `usuario_id`).
2. Normaliza a `contador` cualquier otro valor.
3. `CHECK (rol IN ('administrador', 'contador'))`, creado solo si no existe (antes,
   las variantes `admin`/`Administrador` se conservan como administrador).
4. Tabla `invitaciones_empresa` (empresa, correo, rol, estado, vencimiento, quién invitó,
   quién respondió y cuándo, y qué administrador la resolvió y cuándo) con una sola
   abierta (`pendiente` o `aceptada_pendiente`) por empresa y correo.

## Módulos

- `backend/usuarios_empresa.py` (puro): roles, normalización y validación del correo,
  validación de la contraseña, `puede_administrar(...)`, `administrador_efectivo(...)` y
  la regla del último administrador.
- `backend/routers/cuenta.py` (nuevo): cambio de contraseña y gestión de usuarios de una
  empresa.

## API

| Método y ruta | Qué hace | Errores |
|---|---|---|
| `POST /api/v1/cuenta/contrasena` `{actual, nueva}` | Cambia la contraseña | 400 actual incorrecta, 422 nueva inválida, 429 |
| `GET /api/v1/cuenta/empresas/{id}/usuarios` | `{mi_rol, puede_administrar, usuarios: [...], invitaciones: [...], por_aprobar: [...]}` (invitaciones y por aprobar solo para quien administra) | 403 sin acceso |
| `POST /api/v1/cuenta/empresas/{id}/invitaciones` `{email, rol}` | Invita; misma respuesta exista o no la cuenta | 403, 409 ya tiene acceso, 422, 429 |
| `DELETE /api/v1/cuenta/empresas/{id}/invitaciones/{inv}` | Cancela una pendiente | 403, 404 |
| `POST /api/v1/cuenta/empresas/{id}/invitaciones/{inv}/aprobar` · `/rechazar` | Resuelve una aceptación por aprobar | 403, 404 |
| `GET /api/v1/cuenta/invitaciones` | Mis invitaciones pendientes y las que acepté y esperan aprobación (`estado`) | — |
| `POST /api/v1/cuenta/invitaciones/{inv}/aceptar` · `/rechazar` | Responder; aceptar devuelve `{estado: "aceptada_pendiente"}` | 404 si no es de mi correo o ya se respondió |
| `PATCH /api/v1/cuenta/empresas/{id}/usuarios/{usuario_id}` `{rol}` | Cambia el rol | 403, 404, 409 último administrador, 422 |
| `DELETE /api/v1/cuenta/empresas/{id}/usuarios/{usuario_id}` | Quita el acceso (no borra la cuenta) | 403, 404, 409 último administrador |

## Pantallas

- `/perfil` (enlace "Mi perfil" en el menú): invitaciones recibidas (aceptar o rechazar;
  las aceptadas dicen "Esperando aprobación"), formulario con nombre, teléfono, RFC,
  despacho y cédula; aparte, el cambio de contraseña.
- `/empresas/{id}/usuarios` (entrada "Usuarios" en el menú): tabla con nombre, correo,
  rol y fecha. Si el usuario administra: sección "Por aprobar" (aprobar o rechazar),
  invitaciones pendientes, formulario para invitar, selector de rol por fila y
  quitar con confirmación. Si no, la tabla es de solo lectura con un aviso.

## Criterios de aceptación

1. Tras la 062, el creador de cada empresa es `administrador` y los demás `contador`.
2. Invitar un correo con cuenta y uno sin cuenta da la misma respuesta, sin nombres.
   Quien acepta no ve la empresa hasta que un administrador aprueba; quien rechaza, nunca;
   nadie más puede responder su invitación.
2b. Alguien se registra con el correo de una invitada sin cuenta y acepta: queda por
   aprobar, sin acceso. El administrador ve su nombre y la fecha de su cuenta; un
   contador no puede aprobar ni rechazar (403); al rechazar, sigue sin acceso. Aprobar
   da acceso con el rol invitado. Una aceptación sin aprobar vence a los 7 días.
3. Un contador recibe 403 al invitar, cambiar rol o quitar; un `usuario_id` de otra
   empresa da 404.
4. No se puede degradar ni quitar al último administrador (409); con dos, sí. Dos
   administradores que se quitan entre sí al mismo tiempo dejan exactamente uno.
5. Quitar a un usuario le retira el acceso (403 en las rutas de esa empresa) sin borrar
   su cuenta.
6. Cambiar la contraseña con la actual incorrecta da 400; con la correcta, el login con
   la nueva funciona y con la vieja no.
