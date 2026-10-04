# F2.2 — Worker de descarga automática — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Un proceso `worker` que, para cada empresa con la automatización activada, crea las solicitudes de la carga inicial y de la corrida diaria, las avanza hasta importar los CFDI, cierra la corrida y programa la siguiente; sin que nadie pulse nada y sin perder trabajo ante un reinicio.

**Architecture:** La lógica vive en `backend/sat_sync.py` (planeación pura + `procesar_empresa`), reutilizando `crear_solicitud_ventana` y `avanzar_solicitud` de F2.1. `backend/worker.py` solo hace el ciclo: toma empresas activas con corrida vencida, las procesa una por una bajo un candado de Postgres y duerme. Cada empresa se procesa dentro de un `try/except`: una falla no detiene a las demás.

**Tech Stack:** Python 3.11, psycopg2 (`db`), PostgreSQL (advisory locks), `zoneinfo`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-03-f2-descarga-automatica-design.md` (entrega F2.2; secciones "Ciclo del worker", "Ventanas, límites y reintentos", "Fallas y salud", "Despliegue" y criterios de aceptación 2, 3, 4, 5, 7, 8, 11).

## Global Constraints

- Rama `ccr-69bc8121-eae6jv`, apilada sobre F2.1 (PR #17). Carril B: solo archivos de SAT e infraestructura (`backend/sat_sync.py`, `backend/worker.py`, `backend/routers/sat.py`, `Procfile`, `dev.sh`, `.env.example`, sus pruebas). En `backend/db.py`, `backend/main_api.py` y `docs/openapi.yaml` solo se agregan líneas. No se toca `cfdi_store.py` ni `cfdi_parser.py` (carril A).
- Migraciones solo en el rango 031–039. F2.2 no crea archivo nuevo: agrega `corrida_inicio` a `sat_sync_config` dentro de la 031, que aún no está integrada a `main` (`ADD COLUMN IF NOT EXISTS`, idempotente).
- La e.firma se descifra por empresa y solo para empresas con `activa = TRUE` (D8); nunca se escribe en logs, `error_msg` ni `auditoria`.
- Cada corrida automática deja `auditoria` con `usuario_id` nulo y `metadata.origen`.
- Ninguna solicitud cubre más de un mes natural (ya garantizado por `ventanas_mensuales`).
- Un reinicio del worker no repite trabajo ni duplica CFDI: el estado vive en `sat_solicitudes` y `sat_sync_config`.
- Sin parámetros idénticos repetidos hacia el SAT (límite de por vida, código 5002): al replanear no se vuelven a pedir los meses cerrados ya `descargado`.
- Fuera de F2.2: cancelaciones (F2.4), endpoints `sync/*` y pausa por vencimiento visible en API (F2.3), pantalla (F2.5). La pausa por e.firma vencida **sí** se implementa aquí en el worker, porque sin ella el worker llamaría al SAT con una e.firma inútil.
- Línea base: `python -m pytest` → 651 passed (71 con `-m db`).

## Review Focus

- El candado por empresa libera siempre (aun con excepción) y no queda tomado al devolver la conexión al pool (Task 3).
- Un reinicio a mitad de importación termina la solicitud sin duplicar CFDI (Task 5).
- Replanear tras un fallo no vuelve a pedir meses ya descargados (Task 2).
- La corrida diaria pide desde `ultima_exitosa − traslape` y no repite meses anteriores (Task 2).
- `ultima_exitosa` no avanza si alguna solicitud de la corrida terminó en `fallo` (Task 4).
- e.firma vencida → empresa `pausada`, sin llamadas al SAT, y las demás siguen (Task 4).
- Ningún texto de log, `error_msg` o `auditoria` contiene contraseña ni bytes de la e.firma (Task 6).

## Decisión que necesita el usuario

**¿Puede el worker avanzar las descargas manuales de empresas con la automatización apagada?** El spec dice (D4) que `/fiel/sync` dejaría de dormir en el proceso web y que el worker avanzaría esas solicitudes; pero el D8 dice que el worker solo descifra la e.firma de empresas con consentimiento. Son incompatibles. **Decisión por defecto de este plan: `/fiel/sync` y `/fiel/sync/avanzar` no cambian** (siguen avanzando en el proceso web y con el sondeo del navegador), y el worker solo atiende empresas activas. Si se prefiere que el worker también avance las manuales, basta quitar el filtro `activa` de `avanzar_pendientes` para solicitudes de origen `manual`, pero eso amplía el uso desatendido de la e.firma y debe aprobarlo quien la guarda.

---

### Task 1: Columna `corrida_inicio` y configuración de la corrida

**Files:**
- Modify: `database/migrations/031_sat_sync.sql`, `backend/tests/test_migracion_031.py`

- [ ] **Step 1: Prueba que falla** — `sat_sync_config` tiene la columna `corrida_inicio` (timestamptz, nula por defecto). Se agrega al conjunto de columnas que ya comprueba `test_031_se_puede_repetir_y_agrega_columnas_y_tabla`.
- [ ] **Step 2: Verificar que falla** — `python -m pytest backend/tests/test_migracion_031.py -v`.
- [ ] **Step 3: Agregar** `ALTER TABLE sat_sync_config ADD COLUMN IF NOT EXISTS corrida_inicio TIMESTAMPTZ;` después del `CREATE TABLE` de la 031 (así también cubre bases donde la tabla ya existía con la 031 anterior).
- [ ] **Step 4: Verificar** — pasa; `test_migraciones.py` en verde.
- [ ] **Step 5: Commit** — `feat: corrida_inicio en sat_sync_config`.

---

### Task 2: Planeación pura de las ventanas de una corrida

**Files:**
- Modify: `backend/sat_sync.py`
- Test: `backend/tests/test_sat_sync_planeacion.py`

**Interfaces:**
- Produces:
  - `@dataclass(frozen=True) VentanaPlan(tipo: str, inicio: date, fin: date, origen: str)`
  - `planear_corrida(*, hoy: date, carga_inicial_ok: bool, ultima_exitosa: date | None, traslape_dias: int, descargadas: set[tuple[str, date, date]]) -> list[VentanaPlan]`
  - `proxima_corrida(ahora: datetime, hora_local: str) -> datetime` (siguiente `hora_local` en `America/Mexico_City`, devuelta en UTC, siempre estrictamente posterior a `ahora`)

Reglas:
- **Inicial** (`carga_inicial_ok=False`): por cada tipo (`emitidos`, `recibidos`), cada mes desde enero del año anterior hasta el mes de `hoy` (el mes en curso termina en `hoy`). Se omiten las ventanas con `fin < hoy` que ya estén en `descargadas`. Origen `inicial`.
- **Diaria** (`carga_inicial_ok=True`): por tipo, desde `ultima_exitosa − traslape_dias` hasta `hoy`, partido por mes. Origen `diaria`. Sin `ultima_exitosa` (dato inconsistente) se trata como carga inicial.
- Orden determinista: por tipo y luego por fecha.

- [ ] **Step 1: Pruebas que fallan** (sin base de datos)
  - Inicial con `hoy=2026-10-04`: 2 tipos × 22 meses (2025-01 a 2026-10); última ventana de cada tipo `2026-10-01..2026-10-04`; todas con origen `inicial`.
  - Inicial con 3 meses cerrados ya en `descargadas` → no aparecen; el mes en curso **sí** aparece aunque esté en `descargadas` (su `fin` es `hoy`, no cerrado).
  - Diaria con `ultima_exitosa=2026-10-02`, traslape 7 → desde `2026-09-25` hasta `2026-10-04`, partido: `09-25..09-30` y `10-01..10-04`, por cada tipo; origen `diaria`.
  - Diaria cruzando de año, y con traslape que cae en el mes anterior.
  - `carga_inicial_ok=True` y `ultima_exitosa=None` → se planea como inicial.
  - `proxima_corrida`: con `ahora` antes de las 03:00 locales → hoy 03:00 local (convertido a UTC); después de las 03:00 → mañana; exactamente a las 03:00 → mañana (estrictamente posterior); resultado con `tzinfo` UTC; `hora_local` inválida cae a `03:00`.
- [ ] **Step 2: Verificar que fallan**.
- [ ] **Step 3: Implementar** las dos funciones y el dataclass, sin importar `db`.
- [ ] **Step 4: Verificar que pasan**.
- [ ] **Step 5: Commit** — `feat: planeación pura de corridas de descarga del SAT`.

---

### Task 3: Candado por empresa

**Files:**
- Modify: `backend/sat_sync.py`
- Test: `backend/tests/test_sat_sync_candado.py` (`@pytest.mark.db`)

**Interfaces:**
- Produces: `@contextmanager candado_empresa(empresa_id: str) -> Iterator[bool]`. Abre una conexión dedicada del pool, ejecuta `pg_try_advisory_lock(hashtext(%s))` y cede `True` si lo obtuvo o `False` si otro proceso lo tiene. Siempre ejecuta `pg_advisory_unlock` al salir (también ante excepción) antes de devolver la conexión.

- [ ] **Step 1: Pruebas que fallan** (Postgres real)
  - Dos usos anidados para la misma empresa: el interior cede `False`.
  - Empresas distintas no se bloquean entre sí.
  - Tras salir (con y sin excepción) el candado queda libre: un uso nuevo cede `True`.
  - Con el pool de 5 conexiones, mantener el candado de una empresa no impide que `db.execute` y `db.query_one` funcionen dentro del bloque.
- [ ] **Step 2: Verificar que fallan**.
- [ ] **Step 3: Implementar**. El candado es de **sesión** (no `xact`) porque el trabajo de la empresa usa otras conexiones y puede tardar minutos.
- [ ] **Step 4: Verificar que pasan**.
- [ ] **Step 5: Commit** — `feat: candado por empresa para la descarga automática`.

---

### Task 4: `procesar_empresa`

**Files:**
- Modify: `backend/sat_sync.py` (y `importar_paquetes` / `avanzar_solicitud`: parámetro `correr_pipeline: bool = True`)
- Test: `backend/tests/test_sat_sync_procesar.py`

**Interfaces:**
- Produces:
  - `procesar_empresa(empresa_id: str, *, ahora: datetime | None = None) -> str` que devuelve `'omitida'` (candado ocupado, inactiva o sin corrida vencida y sin pendientes), `'sincronizando'`, `'al_dia'`, `'pausada'` o `'error'`.
  - `avanzar_solicitud(..., correr_pipeline=True)` y `importar_paquetes(..., correr_pipeline=True)`: con `False` no ejecutan el pipeline; el worker lo corre una sola vez al cerrar la corrida.

Flujo (todo dentro de `candado_empresa`):
1. Leer `sat_sync_config`; si no existe o `activa = FALSE` → `'omitida'`.
2. e.firma: `estado_fiel`; si no hay o `vencida` → `estado='pausada'`, `motivo_pausa` ('Sin e.firma' / 'e.firma vencida'), auditoría `sync_pausada`, devolver `'pausada'` **sin** llamar al SAT. Si `obtener_signer` lanza `ValueError` → igual pausa con el motivo.
3. Si `proxima_corrida <= ahora` y no hay corrida en curso (`corrida_inicio IS NULL`): `corrida_inicio = ahora`, `estado = 'sincronizando'`, auditoría `sync_corrida_inicio`; calcular `descargadas` (solicitudes `descargado` de la empresa), `planear_corrida(...)` y crear cada ventana con `crear_solicitud_ventana(..., tolerar_transitorios=True)` respetando `config_sync().max_en_vuelo` (las que no caben se crean en vueltas siguientes: se re-planea en cada vuelta mientras `corrida_inicio` siga puesto, y `SolicitudActiva` significa "ya creada" y se ignora).
4. Reenviar las `pendiente` sin `id_solicitud_sat` cuyo `proximo_intento` venció (`enviar_pendiente`: mismo envío al SAT con los datos de la fila; éxito → `solicitado`; `SolicitudRechazada` → `fallo`; transitorio → `registrar_solicitud_fallida`).
5. Avanzar con `avanzar_solicitud(creds, fila, correr_pipeline=False)` cada solicitud activa con `id_solicitud_sat` y `proximo_intento` vencido o nulo.
6. **Cerrar corrida** cuando ya no quedan solicitudes activas creadas desde `corrida_inicio`:
   - Todas `descargado` → `ultima_exitosa = ahora`, `carga_inicial_ok = TRUE`, `estado = 'al_dia'`, `proxima_corrida = proxima_corrida(ahora, hora_local)`, `corrida_inicio = NULL`.
   - Alguna `fallo` → `estado = 'error'`, `ultima_exitosa` **no** cambia, `proxima_corrida` = la siguiente hora fija, `corrida_inicio = NULL`.
   - Correr `_correr_pipeline` una vez por periodo afectado (los `periodo_inicio` de las solicitudes `descargado` de la corrida con `cfdi_importados > 0`).
   - Auditoría `sync_corrida_fin` con conteos (`solicitudes`, `cfdi_importados`, `fallidas`).

- [ ] **Step 1: Pruebas que fallan** (DB y SAT simulados; `ahora` inyectado)
  - Empresa inactiva o sin config → `'omitida'`, cero llamadas al SAT y cero lecturas de la e.firma.
  - e.firma vencida → `pausada`, `motivo_pausa`, cero llamadas al SAT, auditoría `sync_pausada`.
  - Corrida vencida sin carga inicial → crea las ventanas del plan (origen `inicial`) sin pasar de `max_en_vuelo` activas; la vuelta siguiente crea las restantes.
  - Con carga inicial hecha: crea las diarias; `descargadas` evita repetir meses cerrados.
  - Todas `descargado` → `al_dia`, `ultima_exitosa = ahora`, `carga_inicial_ok`, `proxima_corrida` calculada, `corrida_inicio` nulo; pipeline ejecutado **una vez por periodo** (no por solicitud).
  - Una `fallo` → `error`; `ultima_exitosa` intacta; la siguiente corrida replanea sin los meses ya `descargado`.
  - Solicitud `pendiente` sin `id_solicitud_sat` y con `proximo_intento` vencido → se reenvía; rechazo definitivo → `fallo`.
  - Candado ocupado → `'omitida'` sin tocar nada.
  - Una excepción inesperada al crear o avanzar una solicitud no corrompe `sat_sync_config` (se registra y la empresa queda `sincronizando`).
- [ ] **Step 2: Verificar que fallan**.
- [ ] **Step 3: Implementar** `procesar_empresa`, `enviar_pendiente` y el parámetro `correr_pipeline` (por defecto `True`: los endpoints actuales no cambian).
- [ ] **Step 4: Verificar** — nuevas pruebas y `test_router_sat.py` en verde.
- [ ] **Step 5: Commit** — `feat: procesar_empresa del worker de descarga automática`.

---

### Task 5: Reinicio y concurrencia (integración)

**Files:**
- Test: `backend/tests/test_e2e_worker.py` (`@pytest.mark.db`; SAT simulado)

- [ ] **Step 1: Pruebas que fallan** (Postgres real, `solicitar_descarga`/`verificar_solicitud`/`descargar_paquete` simulados, un XML de ingreso válido de los fixtures)
  - **Reinicio**: primera pasada importa el paquete 1 de 2 y la función "muere" (excepción en el paquete 2); una segunda invocación de `procesar_empresa` retoma desde el paquete 2; el total de CFDI en `cfdi` es el esperado, sin duplicados.
  - **Candado**: dos `procesar_empresa` simultáneos (hilos) sobre la misma empresa → uno cede `'omitida'` y el paquete se descarga una sola vez.
  - **Idempotencia**: ejecutar la corrida completa dos veces con los mismos paquetes no duplica CFDI ni pagos.
  - Carga completa de punta a punta: config activa con `proxima_corrida = ahora` → `al_dia`, CFDI importados y pipeline ejecutado.
- [ ] **Step 2: Verificar que fallan o que exponen huecos**; corregir `procesar_empresa` en lo necesario.
- [ ] **Step 3: Verificar que pasan** — `python -m pytest -m db -v`.
- [ ] **Step 4: Commit** — `test: reinicio, candado e idempotencia del worker de descarga`.

---

### Task 6: `worker.py`, despliegue y seguridad

**Files:**
- Create: `backend/worker.py`
- Modify: `Procfile`, `dev.sh`, `.env.example`
- Test: `backend/tests/test_worker.py`, `backend/tests/test_sat_sync_seguridad.py`

**Interfaces:**
- Produces: `python -m backend.worker` y `ciclo(ahora=None) -> list[tuple[str, str]]` (pares `(empresa_id, resultado)`).

Comportamiento:
- Al arrancar: `db.init_db()`, y falla ruidosamente (salida con código 1 y mensaje claro) si falta o es inválida `FIEL_ENCRYPTION_KEY` (`fiel_store._get_fernet()`).
- `ciclo`: empresas con `activa = TRUE` y (`proxima_corrida <= ahora` o `corrida_inicio IS NOT NULL` o solicitudes activas); `procesar_empresa` por cada una dentro de `try/except` que registra la excepción y sigue.
- Bucle: `ciclo()` y espera `config_sync().intervalo_seg` en pasos cortos; `SIGTERM`/`SIGINT` terminan tras la empresa en curso.
- `Procfile`: `worker: python -m backend.worker`.
- `dev.sh`: levanta el worker junto al backend (si no hay `FIEL_ENCRYPTION_KEY` en `.env`, lo avisa y no lo levanta), guarda su PID y lo detiene en `cleanup`.
- `.env.example`: documentar `FIEL_ENCRYPTION_KEY` (con el comando para generarla) y `SAT_SYNC_INTERVALO_SEG`, `SAT_SYNC_HORA_LOCAL`, `SAT_SYNC_TRASLAPE_DIAS`, `SAT_SYNC_MESES_CANCELACION`, `SAT_SYNC_MAX_EN_VUELO`. **Nota**: a la fecha de este plan la herramienta de edición no tiene acceso de lectura a `.env.example` en el entorno de la sesión; si sigue bloqueado, esa línea se entrega como instrucción en el PR en vez de editarse.

- [ ] **Step 1: Pruebas que fallan**
  - `ciclo` procesa solo las empresas elegibles y devuelve su resultado; una empresa que lanza excepción no impide procesar la siguiente.
  - Arranque sin `FIEL_ENCRYPTION_KEY` sale con código 1 y mensaje claro (prueba del `main()` con la variable ausente).
  - **Seguridad**: se fuerza un error al descargar con una e.firma simulada de contraseña `SECRETO-FIEL` y bytes `BYTES-LLAVE`; ningún mensaje de log (`caplog`), `error_msg` ni `metadata` de `auditoria` contiene esos textos.
  - `Procfile` contiene la línea `worker:`; `dev.sh` pasa `bash -n`.
- [ ] **Step 2: Verificar que fallan**.
- [ ] **Step 3: Implementar** `worker.py` y los cambios de despliegue.
- [ ] **Step 4: Verificar** — `python -m pytest` completo en verde; arrancar el worker 10 s contra Postgres local y comprobar en el log que cicla y se detiene con Ctrl+C.
- [ ] **Step 5: Commit** — `feat: worker de descarga automática del SAT`.

---

### Task 7: Verificación y cierre

- [ ] **Step 1:** `python -m pytest` completo (con Postgres local) y `python -m pytest -m "not db"`; anotar conteos.
- [ ] **Step 2:** `migration-validator` sobre la 031 final (columna `corrida_inicio`).
- [ ] **Step 3:** Revisión del agente `dominio-fiscal` solo sobre lo que toque importación/pipeline si se modificó algo más que el parámetro `correr_pipeline`.
- [ ] **Step 4:** Actualizar la tabla "Estado" del plan maestro: F2.2 hecha; anotar la decisión sobre descargas manuales (pregunta abierta de arriba).
- [ ] **Step 5:** Actualizar el PR #17 (o abrir uno nuevo si #17 ya se integró) con el resumen de F2.2.

## Fuera de esta entrega

Endpoints `sync/estado`, `sync/config`, `sync/ahora` y activación con consentimiento (F2.3); cancelaciones y metadatos (F2.4); pantalla (F2.5).
