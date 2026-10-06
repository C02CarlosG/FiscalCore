# Seguridad de cuentas — plan

Autorizado por Carlos tras F2.4. Alcance: correos únicos sin distinguir mayúsculas, versión de sesión (`token_version`), confianza en el proxy y rol `administrador` al crear empresa.

## Cambios

1. **Migración 032** (`database/migrations/032_seguridad_usuarios.sql`, registrada en `db.init_db`):
   - Si dos cuentas solo difieren en mayúsculas/espacios del correo, la migración **falla con la lista** y no borra ni fusiona nada; se resuelven a mano y se reintenta.
   - Sin duplicados: normaliza los correos existentes a `lower(btrim(email))`, crea `idx_usuarios_email_lower` (único) y agrega `usuarios.token_version INTEGER NOT NULL DEFAULT 0`.
2. **Correos**: `RegisterRequest`/`LoginRequest` normalizan (`strip().lower()`); un registro concurrente del mismo correo responde 409 (antes 500).
3. **Sesiones**: el JWT lleva `tv`. `get_current_user` consulta `activo` y `token_version` en cada petición y da 401 si la cuenta no existe, está desactivada o `tv` ≠ versión actual. Un token anterior sin `tv` vale como versión 0 (las sesiones abiertas al desplegar siguen válidas hasta que se invaliden). `deps.invalidar_sesiones(user_id)` incrementa la versión (para el futuro cambio de contraseña); `PATCH /admin/usuarios/{id}` la incrementa al cambiar `activo` o `rol`.
4. **Proxy** (`backend/proxy.py`): `TRUSTED_PROXY_IPS` (IPs separadas por comas) activa `ProxyHeadersMiddleware`; sin ella no se confía en `X-Forwarded-*`. uvicorn 0.29 no admite CIDR, solo IPs exactas. `*` solo para pruebas (la IP se puede falsear). Mientras no se configure, los límites de tasa siguen contando por IP del proxy.
5. **Rol**: `POST /mis-empresas` vincula al creador con `usuario_empresas.rol = 'administrador'` (antes quedaba el default `contador`).

6. **Endurecimiento del login** (revisión de seguridad): bcrypt contra un hash ficticio cuando el correo no existe o la cuenta está inactiva (sin enumeración por tiempo); el correo ya no se registra en INFO; los 500 no devuelven `str(e)`; `SEED_ADMIN_EMAIL` en minúsculas; `--no-proxy-headers` en `Procfile` y `dev.sh` para que solo `TRUSTED_PROXY_IPS` decida la confianza.

## Pendiente de operación

- Variable `TRUSTED_PROXY_IPS` en el hosting (`.env.example` no se pudo editar desde esta sesión).
- Antes de desplegar: `SELECT lower(btrim(email)), count(*) FROM usuarios GROUP BY 1 HAVING count(*) > 1;` en la base real.

## Pruebas

`test_migracion_032.py`, `test_e2e_seguridad_usuarios.py`, `test_proxy.py` y casos nuevos en `test_deps.py`.
