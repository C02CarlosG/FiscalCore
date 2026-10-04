# F2.4 — Cancelaciones — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que un CFDI cancelado en el SAT después de descargarse deje de contar como vigente: la corrida diaria pide los metadatos de cancelados de los meses recientes y marca `estado = 'cancelado'`, dejando un evento de auditoría por cada cambio.

**Architecture:** `backend/sat_fiel.py` ya sabe pedir `tipo_solicitud="Metadata"`; se agrega la descarga de paquetes de texto y un lector del archivo de metadatos (`parsear_metadata`, puro). `backend/sat_sync.py` planea las ventanas de cancelados dentro de la corrida diaria (`origen = 'cancelados'`), importa sus paquetes con `importar_paquetes_metadata` y marca los CFDI con `marcar_cancelados`. El worker y el resto del flujo (reintentos, partición, candado) no cambian.

**Tech Stack:** Python 3.11, satcfdi 26.8, psycopg2 (`db`), PostgreSQL, pytest.

**Spec:** `docs/superpowers/specs/2026-10-03-f2-descarga-automatica-design.md` (entrega F2.4; sección "Cancelaciones" y criterio 6).

## Decisiones

- **Formato de los metadatos.** `satcfdi` no trae lector. El paquete de metadatos es un ZIP con un `.txt` delimitado por `~` cuya primera línea es el encabezado (`Uuid~RfcEmisor~NombreEmisor~RfcReceptor~NombreReceptor~RfcPac~FechaEmision~FechaCertificacionSat~Monto~EfectoComprobante~Estatus~FechaCancelacion`; `Estatus` 1 = vigente, 0 = cancelado). El formato sale de descripciones públicas del SAT y **debe validarse contra un paquete real** (COPLASUR). Por eso el lector es **guiado por el encabezado** (no por posición), tolerante a mayúsculas, a un BOM y a columnas extra, y si no reconoce `Uuid` y `Estatus` falla con un error claro **sin marcar nada**.
- **Qué se marca.** Solo `vigente → cancelado` de CFDI que ya existen en la empresa (por UUID en mayúsculas). Nunca se crea un CFDI desde metadatos, nunca se "des-cancela" y no se tocan los `sustituido`.
- **Sin recálculo silencioso.** No se corre el pipeline por una cancelación y **no se toca `monto_cobrado`** de las facturas que un REP cancelado había cobrado (`cfdi_store.recalcular_cobrado` no mira el estado del REP; es del carril A). Cada cambio deja `cfdi_cancelado_posterior` en `auditoria` con UUID, periodo, tipo y direcciones; la alerta es de M3. Los cálculos de IVA/ISR (F5/F7) deben filtrar por `estado`.
- **Las cancelaciones no frenan la descarga.** Una ventana de cancelados que falla no deja la corrida en `error` ni detiene `ultima_exitosa`: es de mejor esfuerzo y su falla se informa en el evento `sync_corrida_fin`.
- **Solo en la corrida diaria.** La carga inicial baja XML vigentes; nada previo que cancelar. Los metadatos cubren el mes abierto y los `SAT_SYNC_MESES_CANCELACION` (3) anteriores.

## Global Constraints

- Carril B: `backend/sat_fiel.py`, `backend/sat_sync.py`, sus pruebas y la spec. No se editan `cfdi_store.py` ni `cfdi_parser.py`.
- Sin migraciones (31 ya trae `origen = 'cancelados'` y `tipo_solicitud = 'Metadata'`).
- La e.firma nunca aparece en logs, `error_msg` ni `auditoria`.
- Los metadatos son datos externos: se validan (UUID con formato, estatus conocido) y nunca se interpolan en SQL.
- Línea base: `python -m pytest` completo en verde antes de empezar.

## Review Focus

- Un metadato de un UUID que no existe en la empresa no crea nada y no falla (Task 2).
- Un CFDI ya cancelado no genera un segundo evento de auditoría (Task 2).
- Un archivo con encabezado desconocido no marca ni un CFDI (Task 1 y 2).
- La ventana de metadatos no "cubre" a la ventana de XML del mismo mes, ni al revés (Task 3).
- La corrida con una falla de cancelados termina `al_dia` (Task 4).

---

### Task 1: Descarga y lector de metadatos

**Files:** Modify `backend/sat_fiel.py`; Test `backend/tests/test_sat_fiel_metadata.py`.

**Interfaces:**
- `descargar_paquete(creds, id_paquete, extensiones=(".xml",)) -> list[bytes]` (el valor por defecto no cambia el comportamiento actual).
- `@dataclass(frozen=True) MetadataCFDI(uuid, rfc_emisor, rfc_receptor, efecto, estatus, fecha_cancelacion)` con `estatus` en `{'vigente', 'cancelado'}`.
- `parsear_metadata(contenido: bytes) -> list[MetadataCFDI]`.

- [x] **Step 1: Pruebas que fallan**
  - Paquete ZIP con un `.txt` y un `.xml`: con `extensiones=(".txt",)` entrega solo el `.txt`; el valor por defecto sigue entregando solo XML.
  - Lector: encabezado completo; BOM UTF-8; mayúsculas distintas en el encabezado; columnas extra y en otro orden; `Estatus` `0`/`1` y también `Cancelado`/`Vigente`; `FechaCancelacion` vacía o con fecha; líneas vacías al final; UUID en minúsculas se entrega en mayúsculas; líneas con menos columnas se omiten con un aviso, no truenan el archivo.
  - Archivo sin `Uuid` o sin `Estatus` en el encabezado → `FIELError("Formato de metadatos no reconocido…")`; archivo vacío → lista vacía.
  - `Estatus` desconocido (`7`) o UUID mal formado → esa fila se omite, el resto sigue.
- [x] **Step 2–4:** fallar, implementar, verificar.
- [x] **Step 5: Commit** — `feat: descargar y leer paquetes de metadatos del SAT`.

### Task 2: `marcar_cancelados`

**Files:** Modify `backend/sat_sync.py`; Test `backend/tests/test_sat_sync_cancelados.py` (`@pytest.mark.db`).

**Interfaces:** `marcar_cancelados(empresa_id, registros: list[MetadataCFDI]) -> int` (número de CFDI que pasaron a `cancelado`).

- [x] **Step 1: Pruebas que fallan** (Postgres real)
  - Un CFDI `vigente` que viene `cancelado` pasa a `cancelado` y deja un evento `cfdi_cancelado_posterior` (usuario nulo, `metadata` con uuid, periodo, tipo de comprobante, `fecha_emision` y `fecha_cancelacion`).
  - Un registro `vigente` no cambia nada; un UUID inexistente no crea ni falla; un CFDI de otra empresa con el mismo UUID no se toca.
  - Segunda aplicación: ya estaba `cancelado` → cero cambios y cero eventos nuevos.
  - Un CFDI `sustituido` no se toca.
  - No modifica `monto_cobrado` ni `estado_pago` de ninguna factura.
  - Muchos registros (500) se procesan sin una consulta por fila.
- [x] **Step 2–4:** fallar, implementar (un `UPDATE … WHERE uuid = ANY(%s) AND estado = 'vigente' RETURNING …`), verificar.
- [x] **Step 5: Commit** — `feat: marcar como cancelados los CFDI que el SAT reporta cancelados`.

### Task 3: Planeación de las ventanas de cancelados

**Files:** Modify `backend/sat_sync.py`; Test `backend/tests/test_sat_sync_planeacion.py`, `backend/tests/test_sat_sync_procesar.py`.

**Interfaces:** `VentanaPlan` gana `tipo_solicitud='CFDI'` y `estado_comprobante='Vigente'`; `planear_corrida(..., meses_cancelacion: int = 0)` agrega, solo en la corrida diaria, las ventanas `Metadata`/`Cancelado` (origen `cancelados`) de los últimos `meses_cancelacion + 1` meses por tipo.

- [x] **Step 1: Pruebas que fallan**: la carga inicial no pide cancelados; la diaria con `meses_cancelacion=3` pide 4 meses por tipo con `tipo_solicitud='Metadata'`, `estado_comprobante='Cancelado'`, origen `cancelados`; `meses_cancelacion=0` no agrega nada (compatibilidad); `_cubierta` distingue por `tipo_solicitud` y `estado_comprobante`; `descargadas` solo considera `tipo_solicitud='CFDI'`; `procesar_empresa` crea esas solicitudes con sus parámetros.
- [x] **Step 2–4:** fallar, implementar, verificar (las pruebas existentes de planeación no cambian).
- [x] **Step 5: Commit** — `feat: planear la descarga de metadatos de cancelados en la corrida diaria`.

### Task 4: Importar paquetes de metadatos y cerrar la corrida

**Files:** Modify `backend/sat_sync.py`; Test `backend/tests/test_sat_sync_cancelados.py`, `backend/tests/test_e2e_worker.py`.

**Interfaces:** `importar_paquetes_metadata(creds, solicitud_id, empresa_id, paquetes, desde=0, correr_pipeline=False) -> str`; `avanzar_solicitud` elige la importación según `solicitud["tipo_solicitud"]`.

- [x] **Step 1: Pruebas que fallan** (SAT simulado con un paquete de metadatos real en memoria): una solicitud `Metadata` baja su paquete, marca los CFDI y queda `descargado` con `cfdi_importados` = cancelados marcados; progreso por paquete y reintento de paquete como en XML; un archivo ilegible deja la solicitud en `fallo` con el motivo y **no marca nada**; el cierre de corrida no corre el pipeline por solicitudes de metadatos; una ventana de cancelados en `fallo` no deja la corrida en `error` y se informa en `sync_corrida_fin` (`cancelados_fallidas`); `_progreso` no cuenta esas fallas.
- [x] **Step 2–4:** fallar, implementar, verificar.
- [x] **Step 5: Commit** — `feat: importar metadatos de cancelados y cerrar la corrida sin frenar la descarga`.

### Task 5: Verificación y cierre

- [ ] `python -m pytest` completo y `npm test` en verde.
- [ ] Revisión del agente `dominio-fiscal` sobre el manejo de cancelaciones (efecto sobre cálculos, REP cancelado y `monto_cobrado`).
- [ ] Actualizar la spec (formato de metadatos y su validación pendiente), el plan maestro (fila de F2) y abrir el PR en borrador.

## Fuera de esta entrega

Pantalla (F2.5); la alerta en la campana por un cancelado posterior (M3); recalcular lo cobrado de una factura cuyo REP se canceló (decisión fiscal que requiere al carril A y a F5: ver "Sin recálculo silencioso").
