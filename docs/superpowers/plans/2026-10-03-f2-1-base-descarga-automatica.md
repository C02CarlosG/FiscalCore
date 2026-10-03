# F2.1 — Base de la descarga automática — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Dejar listo el terreno de F2 sin cambiar lo que ve el usuario: migración 031, la lógica de avance/importación de solicitudes movida a un módulo compartido por el router y el futuro worker, reintentos con espera creciente y ventanas mensuales con partición por volumen.

**Architecture:** `backend/sat_sync.py` pasa a ser el dueño de `_avanzar_solicitud`, `_importar_paquetes_bg`, `_registrar_paquete_fallido`, sus constantes de estado y las funciones puras nuevas (`ventanas_mensuales`, `partir_ventana`, `espera_reintento`). `backend/routers/sat.py` queda delgado: valida, delega y re-exporta los nombres que ya usan sus endpoints. La migración 031 agrega a `sat_solicitudes` lo que el worker necesita y crea `sat_sync_config`.

**Tech Stack:** Python 3.11, FastAPI, psycopg2 (`db.execute` / `db.query_one`), PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-10-03-f2-descarga-automatica-design.md` (entrega F2.1; secciones "Datos — migración 031" y "Ventanas, límites y reintentos").

## Global Constraints

- Rama `ccr-69bc8121-eae6jv`; sin tocar `frontend/` (esta entrega no cambia pantallas).
- **Sin cambio de comportamiento observable**: las pruebas existentes de `test_router_sat.py` siguen verdes; solo cambian los objetivos de `monkeypatch` (de `sat.<fn>` a `sat_sync.<fn>`) para las funciones movidas.
- Migración **031** idempotente y registrada en `backend/db.py::init_db`; la 032 queda reservada a F3.2 (otra sesión).
- La e.firma nunca se escribe en logs, `error_msg` ni `auditoria`.
- Ninguna solicitud cubre más de un mes natural; la partición por volumen baja hasta un día como mínimo.
- Valores de configuración (espera, máximos) salen de variables de entorno con valor por defecto; ninguno va fijo en el código de decisión.
- Línea base: `python -m pytest -m "not db"` y `python -m pytest` en verde antes de empezar (se anota el conteo en el primer commit).

## Review Focus

- La extracción no cambia el orden ni la atomicidad de los `UPDATE` condicionales de `_avanzar_solicitud` (dos pasadas no importan el mismo paquete) (Task 3).
- El índice único parcial no hace fallar la migración cuando ya hay solicitudes activas repetidas (Task 1).
- `5002` (solicitudes agotadas) difiere sin consumir intento; `5004` sigue siendo éxito con cero CFDI (Task 4).
- Las esperas de reintento son las del spec: 5 min, 15 min, 1 h, 6 h; al cuarto intento, `fallo` (Task 4).
- La partición de ventanas nunca produce un rango vacío ni solapado (Task 2).

---

### Task 1: Migración 031

**Files:**
- Create: `database/migrations/031_sat_sync.sql`
- Modify: `backend/db.py` (`init_db`, después de la 030)
- Test: `backend/tests/test_migracion_031.py`

**Interfaces:**
- Produces: columnas `sat_solicitudes.origen`, `estado_comprobante`, `tipo_solicitud`, `intentos`, `proximo_intento`, `fecha_inicio`, `fecha_fin` (DATE, nulas en solicitudes viejas); `usuario_id` nulo; índice `uq_sat_solicitudes_ventana_activa` sobre `(empresa_id, tipo, periodo_inicio, periodo_fin, COALESCE(fecha_inicio, '0001-01-01'), COALESCE(fecha_fin, '0001-01-01'), estado_comprobante, tipo_solicitud)` solo para estados activos; tabla `sat_sync_config`.

- [ ] **Step 1: Prueba que falla** (`@pytest.mark.db`, mismo patrón que `test_migracion_030.py`)
  - Aplica la 031 dos veces seguidas sin error.
  - `information_schema`: existen las 5 columnas nuevas con sus valores por defecto; `usuario_id` es nulable.
  - Se puede insertar una solicitud sin `usuario_id`.
  - Dos solicitudes activas de la misma ventana (`empresa_id, tipo, periodo_inicio, estado_comprobante, tipo_solicitud`) violan el índice único; una activa y otra `descargado` o `fallo` conviven.
  - `sat_sync_config`: llave primaria `empresa_id`, `estado` rechaza valores fuera del `CHECK`, borrar la empresa borra su fila.
  - **Datos previos**: con dos solicitudes activas repetidas insertadas *antes* de aplicar la 031 (se simula en una transacción con el índice recién borrado), la migración termina sin error y deja una sola activa; la más antigua queda `fallo` con `error_msg` explicativo.

- [ ] **Step 2: Verificar que falla** — `python -m pytest backend/tests/test_migracion_031.py -m db -v` → falla (no existe la migración).

- [ ] **Step 3: Escribir la migración** con el SQL del spec, más, **antes** de crear el índice único, el saneamiento:

```sql
UPDATE sat_solicitudes s
SET estado = 'fallo',
    error_msg = 'Solicitud duplicada reemplazada al migrar a descarga automática',
    updated_at = NOW()
WHERE s.estado IN ('pendiente','solicitado','en_proceso','terminado')
  AND EXISTS (
      SELECT 1 FROM sat_solicitudes o
      WHERE o.empresa_id = s.empresa_id AND o.tipo = s.tipo
        AND o.periodo_inicio = s.periodo_inicio
        AND o.estado IN ('pendiente','solicitado','en_proceso','terminado')
        AND (o.created_at > s.created_at OR (o.created_at = s.created_at AND o.id > s.id))
  );
```

  Nota: en este punto las columnas `estado_comprobante` y `tipo_solicitud` ya existen con su valor por defecto, así que el saneamiento y el índice usan la misma clave que el spec (añadir ambas columnas al `WHERE`/`EXISTS` si el validador lo pide).

- [ ] **Step 4: Registrar** `_run_sql_file("031_sat_sync.sql")` en `init_db` con su comentario.
- [ ] **Step 5: Verificar** — la prueba pasa; `python -m pytest backend/tests/test_migraciones.py backend/tests/test_db_guardas_produccion.py -v` en verde.
- [ ] **Step 6: Revisión del agente `migration-validator`** sobre la 031; corregir lo que marque.
- [ ] **Step 7: Commit** — `feat: migración 031 para descarga automática del SAT`.

---

### Task 2: Funciones puras de ventanas y reintentos

**Files:**
- Modify: `backend/sat_sync.py` (nuevo)
- Test: `backend/tests/test_sat_sync_ventanas.py`

**Interfaces:**
- Produces:
  - `ventanas_mensuales(desde: date, hasta: date) -> list[tuple[date, date]]`
  - `partir_ventana(inicio: date, fin: date) -> list[tuple[date, date]] | None`
  - `espera_reintento(intentos: int) -> timedelta | None`
  - `config_sync() -> ConfigSync` (dataclass inmutable leída de `os.environ`)

- [ ] **Step 1: Pruebas que fallan** (sin base de datos)
  - `ventanas_mensuales(2025-01-15, 2025-03-10)` → `[(2025-01-15, 2025-01-31), (2025-02-01, 2025-02-28), (2025-03-01, 2025-03-10)]`; año bisiesto (febrero 2024 termina el 29); `desde > hasta` → `[]`; cruce de año.
  - `partir_ventana(2025-01-01, 2025-01-31)` → dos mitades contiguas sin hueco ni solape que cubren todo el rango; ventana de un día → `None`; ventana de dos días → dos de un día.
  - `espera_reintento(1..4)` → 5 min, 15 min, 1 h, 6 h; `espera_reintento(5)` → `None` (se agotó). `espera_reintento(0)` → `None` (no tiene sentido).
  - `config_sync()` toma valores por defecto (`intervalo 60`, `hora_local 03:00`, `traslape_dias 7`, `meses_cancelacion 3`, `max_en_vuelo 4`) y respeta las variables `SAT_SYNC_*`; un valor no numérico cae al defecto y no truena.
- [ ] **Step 2: Verificar que fallan**.
- [ ] **Step 3: Implementar** las cuatro piezas en `sat_sync.py`, sin importar `db` en estas funciones.
- [ ] **Step 4: Verificar que pasan**; `python -m pytest backend/tests/test_sat_sync_ventanas.py -v`.
- [ ] **Step 5: Commit** — `feat: ventanas mensuales, partición y esperas de reintento para el SAT`.

---

### Task 3: Mover avance e importación a `sat_sync.py`

**Files:**
- Modify: `backend/sat_sync.py`, `backend/routers/sat.py`, `backend/tests/test_router_sat.py`

**Interfaces:**
- Produces en `sat_sync`: `avanzar_solicitud`, `importar_paquetes`, `registrar_paquete_fallido`, `estado_sat`, `sin_informacion`, `ESTADOS_EN_SAT`, `ESTADOS_PENDIENTES`, `ESTADOS_FALLO_SAT`, `MAX_INTENTOS_PAQUETE`.
- `routers/sat.py` conserva los nombres con guion bajo como alias importados (`_avanzar_solicitud = sat_sync.avanzar_solicitud`, etc.) para no tocar los endpoints.

- [ ] **Step 1: Línea base** — `python -m pytest backend/tests/test_router_sat.py -v` → anotar el conteo (todas pasan).
- [ ] **Step 2: Mover** las funciones y constantes **sin editar su cuerpo** (solo cambiar el import relativo de `_correr_pipeline` y de `obtener_signer`). `_sync_completo_bg` y los endpoints se quedan en el router.
- [ ] **Step 3: Actualizar pruebas**: donde `test_router_sat.py` hace `monkeypatch.setattr(sat, "_importar_paquetes_bg", ...)` y la función que se prueba vive ahora en `sat_sync`, apuntar el parche a `sat_sync.importar_paquetes` (y lo mismo para `descargar_paquete`, `verificar_solicitud`, `db` según corresponda). No se cambia ninguna aserción.
- [ ] **Step 4: Verificar** — mismo conteo que el Step 1, todo en verde. `python -m pytest -m "not db"` completo en verde.
- [ ] **Step 5: Commit** — `refactor: mover avance e importación de solicitudes SAT a sat_sync`.

---

### Task 4: Reintentos con espera creciente y `5002`

**Files:**
- Modify: `backend/sat_sync.py` (`avanzar_solicitud`, `registrar_solicitud_fallida` nueva)
- Test: `backend/tests/test_sat_sync_reintentos.py`

**Interfaces:**
- Produces: `registrar_solicitud_fallida(solicitud_id, mensaje, *, diferir: bool = False) -> str` que devuelve `'pendiente'`/`'solicitado'` (se reintentará) o `'fallo'` (agotada).

Reglas (del spec):
- Error transitorio del SAT al **verificar** o **solicitar**: `intentos += 1`, `proximo_intento = now() + espera_reintento(intentos)`; al llegar a 4 intentos → `fallo` con el mensaje del SAT.
- `5002` (solicitudes agotadas) al solicitar: `proximo_intento = now() + 1 h`, **sin** incrementar `intentos`.
- `5004` sigue siendo éxito con cero CFDI (ya cubierto; solo se agrega prueba de regresión).
- Los reintentos de **paquete** conservan su mecanismo actual (3 intentos en `error_msg`); no se unifican en esta entrega.
- `avanzar_solicitud` no toca solicitudes cuyo `proximo_intento` es futuro.

- [ ] **Step 1: Pruebas que fallan** (monkeypatch de `db` como en `test_router_sat.py`, sin Postgres)
  - Fallo transitorio #1 → `intentos=1`, `proximo_intento ≈ now+5 min`, estado sin cambiar a `fallo`.
  - Fallos #2, #3 → esperas de 15 min y 1 h; fallo #4 → `fallo` y `error_msg` con el texto del SAT.
  - `5002` → `proximo_intento ≈ now+1 h`, `intentos` igual.
  - Solicitud con `proximo_intento` futuro → `avanzar_solicitud` devuelve su estado sin llamar al SAT.
  - `error_msg` de un fallo nunca contiene la contraseña ni bytes de la e.firma (se fuerza un `FIELError` cuyo mensaje incluye un marcador y se verifica que solo pasa el texto del SAT).
- [ ] **Step 2: Verificar que fallan**.
- [ ] **Step 3: Implementar**; `/fiel/sync` y `/fiel/sync/avanzar` usan los mismos helpers (siguen respondiendo igual).
- [ ] **Step 4: Verificar** — nuevas pruebas y `test_router_sat.py` en verde.
- [ ] **Step 5: Commit** — `feat: reintentos con espera creciente para solicitudes del SAT`.

---

### Task 5: Partición por volumen

**Files:**
- Modify: `backend/sat_sync.py`
- Test: `backend/tests/test_sat_sync_particion.py`

**Interfaces:**
- Produces: `crear_solicitud_ventana(creds, empresa, tipo, inicio, fin, *, origen, estado_comprobante="Vigente", tipo_solicitud="CFDI") -> list[dict]` que inserta la fila, la envía al SAT y, si el SAT rechaza por volumen, la cierra y repite con `partir_ventana`.

- [ ] **Step 1: Verificar contra la documentación vigente del SAT** los límites de descarga masiva (solicitudes por periodo, tamaño de resultado, paquetes) y el código exacto que devuelve el rechazo por volumen. Anotar fuente y fecha en un comentario del módulo y en la sección "Dudas abiertas" de la spec. Si el código no se puede confirmar, la detección se hace por el texto del mensaje y se deja una constante nombrada para ajustarla.
- [ ] **Step 2: Pruebas que fallan**
  - SAT acepta → una fila `solicitado` con `origen`, `estado_comprobante`, `tipo_solicitud` y fechas correctas.
  - SAT rechaza por volumen un mes → dos filas con mitades contiguas; si una mitad vuelve a rechazarse, se parte otra vez; con rango de un día rechazado → `fallo` con el mensaje del SAT, sin bucle infinito.
  - La fila original rechazada queda `fallo` con `error_msg` que dice que se partió, y las nuevas no violan el índice único (se distinguen por `fecha_inicio`/`fecha_fin`).
- [ ] **Step 3: Implementar** `crear_solicitud_ventana`; las mitades llevan `fecha_inicio`/`fecha_fin` propias (columnas de la 031, parte de la clave del índice único) y la fila original pasa a `fallo` *antes* de insertarlas. El endpoint `/fiel/sync` la usa para crear la solicitud del mes (comportamiento visible igual).
- [ ] **Step 4: Verificar** — nuevas pruebas, `test_router_sat.py`, `test_migracion_031.py` en verde.
- [ ] **Step 5: Commit** — `feat: ventanas mensuales y partición por volumen al solicitar al SAT`.

---

### Task 6: Verificación y cierre

- [ ] **Step 1:** `python -m pytest` completo (con `docker compose up -d db`) y `python -m pytest -m "not db"` en verde; anotar conteos.
- [ ] **Step 2:** `docs/openapi.yaml`: sin rutas nuevas en esta entrega; `test_openapi_sync.py` en verde. Si el listado de solicitudes cambia su forma (campos nuevos), documentarlos.
- [ ] **Step 3:** Revisión del agente `dominio-fiscal` solo si algún cambio toca importación de CFDI (no se espera) y del `migration-validator` sobre la 031 final.
- [ ] **Step 4:** Actualizar la tabla "Estado" del plan maestro: F2.1 hecha; anotar los límites del SAT verificados.
- [ ] **Step 5:** PR en borrador contra `main`, título `feat: base de la descarga automática del SAT (F2.1)`.

## Fuera de esta entrega

El worker, el ciclo, la carga inicial y la corrida diaria (F2.2); endpoints `sync/*` y pausa por vencimiento (F2.3); cancelaciones (F2.4); pantalla (F2.5).
