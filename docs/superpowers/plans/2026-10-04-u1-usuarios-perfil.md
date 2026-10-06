# Plan U1 — Usuarios y perfil (carril D)

Spec: `docs/superpowers/specs/2026-10-04-u1-usuarios-perfil-design.md`.
Rama: `claude/d-u1-usuarios-perfil` desde `origin/main`. PR: `D·U1: usuarios y perfil`.

## Tarea 1 — Módulo puro `usuarios_empresa.py`

- Pruebas `backend/tests/test_usuarios_empresa.py`: correo (minúsculas, espacios,
  inválidos), rol válido, contraseña (longitud, igual a la actual), administrador
  efectivo (con y sin administrador marcado, desempate), `puede_administrar` (rol de
  empresa y admin de plataforma), último administrador al degradar y al quitar.

## Tarea 2 — Migración 062

- Prueba `backend/tests/test_migracion_062.py` (`-m db`): backfill del creador, otros a
  contador, CHECK, idempotente.

## Tarea 3 — Router `cuenta.py`

- Pruebas `backend/tests/test_router_cuenta.py` (base mockeada): 401, validaciones 422,
  403 de contador, 409 último administrador, auditoría sin contraseñas.
- Pruebas `backend/tests/test_e2e_cuenta.py` (`-m db`): criterios 2 a 6 de la spec con
  login real.
- `include_router`, `docs/openapi.yaml`.

## Tarea 4 — Frontend

- Vitest de `components/cuenta/PerfilForm`, `CambiarContrasenaForm` y `UsuariosEmpresa`.
- Páginas `/perfil` y `/empresas/{id}/usuarios`; entradas del menú.

## Tarea 5 — Cierre

Merge de `origin/main`, suites completas, Playwright, plan maestro, PR y aviso.
