# U1 — Usuarios y perfil

Fecha: 2026-10-04. Carril D. Estado: en implementación.
Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md` ("Detalle de las entregas", U1).
Referencia: `2026-10-01-referencia-plataforma.md`, "Configuración → Perfil de usuario, Usuarios".

## Objetivo

Que cada usuario vea y edite su perfil y cambie su contraseña, y que quien administra
una empresa dé de alta a otras personas en ella con un rol, les cambie el rol o les
quite el acceso. Hoy una empresa solo la ve quien la creó y no hay forma de compartirla.

## Alcance

Entra:

- Pantalla **Perfil** (`/perfil`): datos de `GET /api/v1/auth/me` y
  `PATCH /api/v1/usuarios/perfil` (existentes, carril B; se usan sin editarlos) y cambio
  de contraseña (endpoint nuevo del carril D).
- Pantalla **Usuarios** por empresa (`/empresas/{id}/usuarios`): lista, alta, cambio de
  rol y baja.
- Roles por empresa en `usuario_empresas.rol`: `administrador` y `contador`.

No entra:

- Rol de solo lectura: exigiría revisar cada endpoint de escritura de los demás carriles.
  Si se pide, va en una entrega aparte con su pedido entre carriles.
- Invitación por correo con enlace: no hay envío de correo (llega con M3). El alta crea
  la cuenta con una contraseña temporal que el administrador comunica por otro medio.
- Obligar a cambiar la contraseña temporal en el primer acceso: requiere tocar el login
  (`auth.py`, carril B). Queda como pedido.

## Reglas

| Regla | Cómo se aplica |
|---|---|
| Roles por empresa | `administrador`: todo lo de contador y además gestiona usuarios. `contador`: trabaja la empresa. El rol global `usuarios.rol = 'admin'` (administrador de la plataforma) puede gestionar cualquier empresa |
| Quién es administrador hoy | La migración 062 marca como `administrador` al primer usuario vinculado de cada empresa (su creador) si la empresa no tiene ninguno. Como `POST /mis-empresas` (carril B) sigue vinculando con el valor por defecto, el código aplica la misma regla al leer: si una empresa no tiene administrador, el primer vinculado actúa como tal. Pedido al carril B: vincular al creador como `administrador` |
| Siempre queda un administrador | No se puede quitar ni degradar al último administrador (409) |
| Alta | Correo obligatorio, en minúsculas y sin espacios. Si la cuenta existe, se vincula (409 si ya estaba). Si no existe, se crea con nombre y contraseña temporal de 8 caracteres o más (bcrypt, `deps.hash_password`) |
| Cambio de contraseña | Exige la contraseña actual; la nueva tiene 8 caracteres o más y es distinta de la actual. Límite de 5 intentos por minuto |
| Auditoría | Alta, cambio de rol, baja y cambio de contraseña quedan en `auditoria` (sin contraseñas) |

## Datos

Migración `062_roles_usuario_empresa.sql` (idempotente):

1. Por cada empresa sin `administrador`, marca como tal al vínculo con `created_at` más
   antiguo (desempate por `usuario_id`).
2. Normaliza a `contador` cualquier otro valor.
3. `CHECK (rol IN ('administrador', 'contador'))`, creado solo si no existe.

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
| `GET /api/v1/cuenta/empresas/{id}/usuarios` | `{mi_rol, puede_administrar, usuarios: [{usuario_id, email, nombre, rol, desde, soy_yo}]}` | 403 sin acceso |
| `POST /api/v1/cuenta/empresas/{id}/usuarios` `{email, rol, nombre?, password_temporal?}` | Alta o vínculo; responde `{usuario, cuenta_creada}` | 403 no administra, 409 ya vinculado, 422 |
| `PATCH /api/v1/cuenta/empresas/{id}/usuarios/{usuario_id}` `{rol}` | Cambia el rol | 403, 404, 409 último administrador, 422 |
| `DELETE /api/v1/cuenta/empresas/{id}/usuarios/{usuario_id}` | Quita el acceso (no borra la cuenta) | 403, 404, 409 último administrador |

## Pantallas

- `/perfil` (enlace "Mi perfil" en el menú): formulario con nombre, teléfono, RFC,
  despacho y cédula; aparte, el cambio de contraseña.
- `/empresas/{id}/usuarios` (entrada "Usuarios" en el menú): tabla con nombre, correo,
  rol y fecha. Si el usuario administra: formulario de alta, selector de rol por fila y
  quitar con confirmación. Si no, la tabla es de solo lectura con un aviso.

## Criterios de aceptación

1. Tras la 062, el creador de cada empresa es `administrador` y los demás `contador`.
2. Un administrador da de alta un correo nuevo (cuenta creada, puede iniciar sesión con
   la temporal y ve la empresa) y vincula un correo existente sin tocar su contraseña.
3. Un contador recibe 403 al dar de alta, cambiar rol o quitar.
4. No se puede degradar ni quitar al último administrador (409); con dos, sí.
5. Quitar a un usuario le retira el acceso (403 en las rutas de esa empresa) sin borrar
   su cuenta.
6. Cambiar la contraseña con la actual incorrecta da 400; con la correcta, el login con
   la nueva funciona y con la vieja no.
