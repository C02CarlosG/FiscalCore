# F2.3 — Endpoints de la descarga automática — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el usuario pueda activar, pausar y consultar la descarga automática de una empresa, y forzar una corrida, con consentimiento explícito y auditoría.

**Architecture:** La lógica vive en `backend/sat_sync.py` (`estado_sync`, `configurar_sync`, `forzar_corrida`, `desactivar_por_fiel_eliminada`), que lanza `ConfigSyncInvalida` con el código HTTP y el detalle; `backend/routers/sat.py` solo valida acceso, delega y traduce. El worker (F2.2) ya hace el trabajo: activar solo deja la empresa "vencida" para que el siguiente ciclo cree la carga inicial.

**Tech Stack:** Python 3.11, FastAPI, psycopg2 (`db`), PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-10-03-f2-descarga-automatica-design.md` (entrega F2.3: secciones "Activar la automatización", "API", "Seguridad" y criterios 1 y 10).

## Global Constraints

- Carril B: solo `backend/sat_sync.py`, `backend/routers/sat.py`, sus pruebas y `docs/openapi.yaml` (solo se agregan rutas). Sin migraciones nuevas (la 031 ya trae todo lo necesario).
- Activar exige `consentimiento: true`, e.firma guardada y vigente; si no, 422 sin escribir nada.
- Cada cambio de configuración y cada "actualizar ahora" quedan en `auditoria` con el usuario (`sync_activada`, `sync_desactivada`, `sync_ahora`).
- Borrar la e.firma desactiva la automatización en la misma operación.
- Los endpoints nunca devuelven credenciales ni datos de la e.firma.
- Límites: `PUT sync/config` 10/min, `POST sync/ahora` 5/min.
- Línea base: `python -m pytest` → 782 passed.

## Review Focus

- Activar sin consentimiento, sin e.firma o con e.firma vencida no modifica `sat_sync_config` (Task 2).
- Activar una empresa ya activa no reinicia una corrida en curso (Task 2).
- `ahora` responde 409 con corrida en curso y 422 si la automatización está apagada (Task 3).
- Un usuario sin acceso a la empresa recibe 403 en los tres endpoints (Task 4).
- El progreso no cuenta como falla las ventanas partidas por volumen (Task 1).

---

### Task 1: `estado_sync` y `GET /sync/estado`

**Files:** Modify `backend/sat_sync.py`, `backend/routers/sat.py`; Test `backend/tests/test_e2e_sync_endpoints.py` (`@pytest.mark.db`).

**Interfaces:** `estado_sync(empresa_id) -> dict` con `activa, estado, motivo_pausa, ultima_exitosa, proxima_corrida, carga_inicial_ok, consentimiento_por, consentimiento_el, progreso: {total, terminadas, fallidas}`. Sin configuración devuelve los valores por defecto (`activa=False`, `estado='inactiva'`, progreso en cero). Las fechas van como ISO 8601.

Progreso (solo con corrida en curso): `terminadas` = solicitudes `descargado` desde `corrida_inicio`; `fallidas` = `fallo` sin contar las ventanas partidas (`MARCA_PARTIDA`); `total` = terminadas + fallidas + activas + ventanas planeadas que aún no se crean (se reutiliza la planeación del worker: helper `ventanas_por_crear`, compartido con `_crear_ventanas_faltantes`).

- [x] **Step 1: Pruebas que fallan**: sin config → valores por defecto; con config y corrida en curso → progreso correcto (terminadas, fallidas, partidas no cuentan, por crear incluidas en el total); sin corrida en curso → progreso en cero; no expone credenciales.
- [x] **Step 2: Verificar que fallan.**
- [x] **Step 3: Implementar** `estado_sync`, el helper `ventanas_por_crear` y el endpoint.
- [x] **Step 4: Verificar**: pruebas nuevas y `test_sat_sync_procesar.py` en verde (el refactor no cambia el worker).
- [x] **Step 5: Commit** — `feat: GET sync/estado de la descarga automática`.

### Task 2: `configurar_sync` y `PUT /sync/config`

**Interfaces:** `configurar_sync(empresa_id, usuario_id, *, activa, consentimiento) -> dict` (el mismo objeto de `estado_sync`); `ConfigSyncInvalida(codigo: int, detalle: str)`.

Reglas: activar → `consentimiento` verdadero (422), e.firma guardada (422) y vigente (422); guarda `consentimiento_por/el`, `activa=TRUE`, `estado='sincronizando'`, `proxima_corrida=NOW()`, `motivo_pausa=NULL`, audita `sync_activada`. Si ya estaba activa no reinicia la corrida ni vuelve a auditar. Desactivar → `activa=FALSE`, `estado='inactiva'`, `corrida_inicio=NULL`, `motivo_pausa=NULL`, audita `sync_desactivada`; sin configuración previa no hace nada.

- [x] **Step 1: Pruebas que fallan**: sin consentimiento / sin e.firma / vencida → 422 y sin cambios en la base; activar → fila y auditoría con usuario; activar dos veces → no reinicia `corrida_inicio` ni duplica auditoría; desactivar → inactiva, auditoría, y el worker (`empresas_elegibles`) ya no la incluye; cuerpo inválido → 422 de FastAPI.
- [x] **Step 2–4:** fallar, implementar, verificar.
- [x] **Step 5: Commit** — `feat: PUT sync/config con consentimiento y auditoría`.

### Task 3: `forzar_corrida` y `POST /sync/ahora`

Reglas: automatización apagada → 422; e.firma ausente o vencida → 422; corrida en curso (`corrida_inicio` no nulo) → 409; si no, `proxima_corrida = NOW()`, audita `sync_ahora` con el usuario y devuelve el estado.

- [x] **Step 1: Pruebas que fallan** (cada regla y el camino feliz; el worker recoge la empresa en el siguiente ciclo).
- [x] **Step 2–4:** fallar, implementar, verificar.
- [x] **Step 5: Commit** — `feat: POST sync/ahora para forzar una corrida`.

### Task 4: Borrar la e.firma desactiva, acceso y OpenAPI

- `DELETE /fiel` llama a `desactivar_por_fiel_eliminada` (misma operación: sin e.firma no hay automatización); audita `sync_desactivada` con `motivo: e.firma eliminada`.
- 403 sin acceso a la empresa en los tres endpoints; 401 sin sesión.
- Documentar las tres rutas y sus esquemas en `docs/openapi.yaml` (`test_openapi_sync.py`).

- [x] **Step 1: Pruebas que fallan** (borrado desactiva; 403 y 401; openapi sincronizado).
- [x] **Step 2–4:** fallar, implementar, verificar.
- [x] **Step 5: Commit** — `feat: borrar la e.firma desactiva la descarga automática y documenta sync/*`.

### Task 5: Verificación y cierre

- [x] `python -m pytest` completo y `npm test` en verde; `migration-validator` no aplica (sin migración); `dominio-fiscal` no aplica (sin cálculo fiscal).
- [x] Actualizar la fila de F2 del plan maestro (F2.3 en revisión) y abrir el PR en borrador.

## Fuera de esta entrega

Cancelaciones (F2.4) y pantalla (F2.5). La observación opcional del validador sobre `terminado` en la limpieza de duplicados de la 031 no se atiende aquí: la 031 ya está en `main` y la limpieza solo corre una vez, al aplicarla.
