# F2 — Descarga automática de XML del SAT

Fecha: 2026-10-03. Estado: borrador para revisión.
Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md` (fase F2; decisiones D7 y D8).

## Contexto

Hoy la descarga masiva funciona pero es manual y frágil:

- `POST /api/v1/sat/empresas/{id}/fiel/sync` pide un mes y lanza un `BackgroundTask`
  (`_sync_completo_bg`) que **duerme dentro del proceso web** hasta 30 minutos
  (60 × 30 s). Si el servidor se reinicia, el task muere; la solicitud queda en
  `solicitado` y solo `/fiel/sync/avanzar` (que llama el navegador) la rescata.
- Solo se pide `estado_comprobante="Vigente"`: un CFDI cancelado después de
  descargarse sigue contando como vigente.
- `sat_solicitudes.usuario_id` es obligatorio, así que nadie sin sesión puede crear
  una solicitud.
- La e.firma ya se guarda cifrada (`fiel_store`, Fernet) y la pantalla "Conexión SAT"
  ya permite guardarla, pedir el mes a mano y ver el historial.

Lo que **ya sirve y se reutiliza**: `sat_fiel.py` (solicitar, verificar, descargar),
`_avanzar_solicitud` (máquina de estados con UPDATE condicional contra pasadas
concurrentes y reintento de paquetes), `cfdi_store.insertar_cfdi` (idempotente por UUID,
pasa por el detalle fiscal de F1), `_correr_pipeline` de `ingesta`, `auditoria`.

## Objetivo

Que una empresa con e.firma guardada y automatización activada tenga sus CFDI emitidos
y recibidos al día sin que nadie pulse nada, que un reinicio no pierda trabajo, y que un
CFDI cancelado deje de contar.

## Alcance

### Entra

1. Proceso `worker` aparte que ejecuta trabajos de descarga desde Postgres.
2. Configuración de sincronización por empresa (activa, consentimiento, última y
   próxima corrida, estado de salud).
3. Carga inicial al activar: ejercicio en curso y el anterior, mes por mes.
4. Corrida diaria incremental con traslape.
5. Detección de cancelaciones (metadatos de los meses recientes).
6. Botón "Actualizar ahora".
7. Pantalla: interruptor de automatización con consentimiento, estado de la última
   descarga, historial con origen y errores del SAT; indicador en el menú.
8. Pausa automática ante e.firma vencida/revocada.
9. Auditoría de cada corrida automática.

### No entra (y dónde queda)

| Tema | Queda en |
|---|---|
| Alertas en la campana (e.firma por vencer, CFDI cancelado ya considerado en periodo cerrado) | M3. F2 solo deja el dato y el estado de salud |
| Fecha y "alcance" de cancelación | Se guarda lo que entregue el SAT; la pantalla que lo muestra es F3 |
| Ejecutar los cálculos de IVA/ISR tras importar | F5/F7. F2 solo corre el pipeline que hoy existe |
| Cola genérica de trabajos | No se construye: la tabla de solicitudes **es** la cola |
| Constancia y opinión de cumplimiento | F8 |

## Decisiones

| # | Decisión | Motivo | Si resulta equivocada |
|---|---|---|---|
| D1 | El worker avanza `sat_solicitudes` existentes; no hay tabla de trabajos nueva. Lo que se agrega es una tabla `sat_sync_config` por empresa que dice cuándo toca crear solicitudes | Las solicitudes ya tienen estados persistidos y retoman tras reinicio | Agregar tabla de trabajos no cambia el contrato de API |
| D2 | Un solo proceso worker con un ciclo (cada 60 s): crea solicitudes que tocan y avanza las pendientes | Sin Redis ni Celery (D7 del plan maestro); el volumen es de decenas de empresas | Escalar a N workers es seguro si el candado por empresa (D3) se respeta |
| D3 | Candado por empresa con `pg_try_advisory_lock(hashtext(empresa_id))` por corrida | Evita dos workers (o worker + `/avanzar` manual) sobre la misma empresa sin tabla ni expiración que mantener | Cambiar a columna `bloqueada_hasta` |
| D4 | `/fiel/sync` manual y `/fiel/sync/avanzar` **se conservan** (respaldo y entornos serverless), pero `/fiel/sync` deja de lanzar el loop dormido: solo crea la solicitud y el worker la avanza | Un solo camino de avance; se elimina el loop de 30 min en el proceso web | Mantener el loop si no hay worker en el hospedaje (ver riesgos) |
| D5 | Las corridas automáticas **no tienen usuario**: `sat_solicitudes.usuario_id` pasa a nulo y se agrega `origen` (`manual`, `inicial`, `diaria`, `cancelados`) | Lo exigía el plan maestro | — |
| D6 | Una solicitud por (empresa, tipo, mes, estado de comprobante). La carga inicial parte en meses; nunca se pide un rango mayor a un mes | Mantiene cada solicitud bajo los límites del SAT y permite retomar mes a mes | Ver "Ventanas" |
| D7 | La e.firma se descifra en memoria por corrida y no se guarda en ninguna variable global ni log | D8 del plan maestro | — |

## Datos — migración 031

Idempotente (`IF NOT EXISTS`, `DROP CONSTRAINT IF EXISTS`):

```sql
-- sat_solicitudes
ALTER TABLE sat_solicitudes ALTER COLUMN usuario_id DROP NOT NULL;
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS origen VARCHAR(12) NOT NULL DEFAULT 'manual'
    CHECK (origen IN ('manual','inicial','diaria','cancelados'));
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS estado_comprobante VARCHAR(10) NOT NULL DEFAULT 'Vigente';
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS tipo_solicitud VARCHAR(10) NOT NULL DEFAULT 'CFDI'
    CHECK (tipo_solicitud IN ('CFDI','Metadata'));
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS intentos INTEGER NOT NULL DEFAULT 0;
ALTER TABLE sat_solicitudes ADD COLUMN IF NOT EXISTS proximo_intento TIMESTAMPTZ;
-- evita duplicar la misma ventana en vuelo
CREATE UNIQUE INDEX IF NOT EXISTS uq_sat_solicitudes_ventana_activa
    ON sat_solicitudes (empresa_id, tipo, periodo_inicio, estado_comprobante, tipo_solicitud)
    WHERE estado IN ('pendiente','solicitado','en_proceso','terminado');

-- configuración por empresa
CREATE TABLE IF NOT EXISTS sat_sync_config (
    empresa_id          UUID PRIMARY KEY REFERENCES empresas(id) ON DELETE CASCADE,
    activa              BOOLEAN NOT NULL DEFAULT FALSE,
    consentimiento_por  UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    consentimiento_el   TIMESTAMPTZ,
    carga_inicial_ok    BOOLEAN NOT NULL DEFAULT FALSE,
    ultima_exitosa      TIMESTAMPTZ,
    proxima_corrida     TIMESTAMPTZ,
    estado              VARCHAR(12) NOT NULL DEFAULT 'inactiva'
        CHECK (estado IN ('inactiva','al_dia','sincronizando','pausada','error')),
    motivo_pausa        TEXT,
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

- Registrar `031` en `db.init_db()` como las anteriores.
- Si ya existen filas duplicadas que violen el índice único parcial, la migración no
  falla: el índice se crea con `WHERE` sobre estados activos y, antes, se marcan como
  `fallo` las activas repetidas más antiguas (el `migration-validator` revisa esto).
- Borrar la e.firma (`eliminar_fiel`) pone `activa = FALSE`, `estado = 'inactiva'`.

## Comportamiento

### Activar la automatización

`PUT /api/v1/sat/empresas/{id}/sync/config` con `{activa: true, consentimiento: true}`.

- 422 si no hay e.firma guardada, está vencida, o no se envía `consentimiento: true`.
- Guarda `consentimiento_por/el`, `activa = TRUE`, `estado = 'sincronizando'`, y crea las
  solicitudes de la carga inicial (origen `inicial`). Registra `auditoria`
  (`sync_activada`).
- Desactivar (`activa: false`) pausa de inmediato: el worker no crea ni avanza nada de
  esa empresa; las solicitudes en vuelo quedan como están. Registra `sync_desactivada`.
- Guardar una e.firma **nueva** del mismo RFC reanuda una empresa `pausada` por
  vencimiento sin pedir otro consentimiento; con otro RFC se rechaza (ya lo hace
  `guardar_fiel`).

### Ciclo del worker (`backend/worker.py`, `python -m backend.worker`)

Cada 60 s, en este orden:

1. **Crear trabajo** para empresas `activa` cuya `proxima_corrida <= now()`:
   - Sin `carga_inicial_ok`: una solicitud `CFDI` / `Vigente` por (tipo, mes) desde enero
     del ejercicio anterior hasta el mes en curso. Se crean como `pendiente` y se
     lanzan de a pocas (ver "Ventanas").
   - Con carga inicial: corrida **diaria**: por tipo, desde el mes de
     `ultima_exitosa − TRASLAPE` (7 días) hasta hoy, partido por mes, `Vigente`.
   - Corrida de **cancelados** (una vez al día, junto a la diaria): por tipo,
     `tipo_solicitud='Metadata'`, `estado_comprobante='Cancelado'`, del mes abierto y
     los `MESES_CANCELACION` (3) anteriores.
2. **Avanzar** cada solicitud pendiente cuyo `proximo_intento` ya venció, con el candado
   de la empresa, usando `_avanzar_solicitud` (movida a un módulo reutilizable
   `backend/sat_sync.py` para que router y worker compartan código).
3. **Cerrar corrida**: cuando no queda solicitud activa de la corrida, `ultima_exitosa =
   now()`, `proxima_corrida = mañana a la hora fija de la empresa` (por defecto 03:00
   hora de México), `estado = 'al_dia'`; la primera vez, `carga_inicial_ok = TRUE`.
   Si alguna terminó en `fallo` definitivo, `estado = 'error'` y `ultima_exitosa` **no**
   avanza (la siguiente corrida vuelve a cubrir esa ventana).
4. Correr el pipeline (`_correr_pipeline`) una vez por empresa y periodo afectado, no
   por solicitud.

El worker atrapa toda excepción por empresa: una e.firma corrupta o un SAT caído no
detiene a las demás. Al arrancar no necesita reconciliar nada: lo pendiente sigue en
`sat_solicitudes`.

### Ventanas, límites y reintentos

- Una solicitud nunca cubre más de un mes natural (D6). Si el SAT rechaza por volumen
  (resultado demasiado grande), la ventana se parte en dos mitades por fecha y se
  reintenta; el límite inferior es un día.
- **Concurrencia hacia el SAT**: máximo `MAX_SOLICITUDES_EN_VUELO` (valor inicial 4) por
  empresa, para no agotar el cupo de solicitudes. `5002` (solicitudes agotadas) no cuenta
  como fallo: se difiere la solicitud 1 h.
- **Reintentos**: `intentos` y `proximo_intento` con espera creciente (5 min, 15 min,
  1 h, 6 h); a los 4 intentos la solicitud queda `fallo` con el mensaje del SAT. Esto
  reemplaza el conteo "intento N de 3" que hoy viaja dentro de `error_msg` solo para
  los paquetes, que se conserva tal cual.
- **Sin información (5004)**: se trata como éxito con cero CFDI, como hoy.

### Cancelaciones

- La solicitud de cancelados pide metadatos (`Metadata`, `Cancelado`). Cada fila del
  paquete trae UUID y estatus; para cada UUID existente de la empresa se hace
  `UPDATE cfdi SET estado='cancelado'` (solo si estaba vigente) y se registra el cambio.
- Si el CFDI cancelado pertenece a un periodo que ya tiene cédula de IVA calculada, se
  guarda el dato (`cfdi.estado` + evento en `auditoria` con `accion =
  'cfdi_cancelado_posterior'`) pero **no se recalcula nada**; la alerta es de M3.
- El formato de los metadatos (paquete ZIP con `.txt` delimitado por `~`) lo lee un
  parser nuevo `parsear_metadata` en `sat_fiel.py`. Qué trae exactamente el SAT en ese
  paquete y si satcfdi lo expone se **verifica al empezar a implementar**; si no se
  puede, el fallback es pedir `CFDI` + `Cancelado` (XML) y marcar por UUID.

### Fallas y salud

| Situación | Efecto |
|---|---|
| SAT rechaza o falla una solicitud | Reintentos (arriba); al agotarlos, `fallo` visible con mensaje |
| e.firma vencida (`vigencia_fin < hoy`) | `estado = 'pausada'`, `motivo_pausa = 'e.firma vencida'`; no se intenta |
| SAT responde error de autenticación/certificado revocado | Igual que vencida, con el motivo del SAT |
| `FIEL_ENCRYPTION_KEY` ausente o inválida | El worker no arranca (falla ruidosa al inicio); la API responde 500 como hoy |
| Un paquete no se descarga | Comportamiento existente (3 intentos, la solicitud queda `terminado` y se retoma) |

## API

Todo bajo `/api/v1/sat/empresas/{empresa_id}`, con sesión y `validar_acceso_empresa`.
Se documenta en `docs/openapi.yaml` (lo exige `test_openapi_sync.py`).

| Método y ruta | Cuerpo / respuesta |
|---|---|
| `GET /sync/estado` | `{activa, estado, motivo_pausa, ultima_exitosa, proxima_corrida, carga_inicial_ok, progreso: {total, terminadas, fallidas}, consentimiento_por, consentimiento_el}` |
| `PUT /sync/config` | `{activa: bool, consentimiento: bool}` → mismo objeto que `GET /sync/estado` |
| `POST /sync/ahora` | Fuerza `proxima_corrida = now()`; 409 si ya hay una corrida en vuelo; 422 si no hay e.firma vigente. Límite 5/min |
| `GET /api/v1/sat/solicitudes?empresa_id=` (existente) | Se amplía con `origen`, `estado_comprobante`, `tipo_solicitud`, `intentos`, `proximo_intento` y se sube a 50 filas |

`/fiel/sync` y `/fiel/sync/avanzar` se mantienen (D4).

## Pantalla (extiende `/empresas/{id}/sat`)

- Tarjeta **Descarga automática**: interruptor (con diálogo de consentimiento en la
  primera activación: explica que el sistema usará la e.firma sin intervención y que se
  puede pausar o borrar en cualquier momento), estado con color (al día / sincronizando
  / pausada / error), última descarga exitosa, próxima corrida y barra de progreso de la
  carga inicial. Botón **Actualizar ahora**.
- **Historial** existente con columnas nuevas: origen, ventana (tipo y mes), intentos y
  mensaje del SAT visible en las fallidas.
- **Menú**: junto a la empresa activa, un indicador pequeño con el estado y la fecha de
  la última descarga; se oculta si la automatización está inactiva. (Toca el menú, que
  F3.2 también modifica: ver coordinación.)
- Estados: cargando, sin e.firma (la tarjeta invita a guardarla), pausada (con la acción
  para reemplazar la e.firma), error.
- Sondeo cada 15 s del estado mientras `estado = 'sincronizando'`; sin sondeo en los demás.

## Despliegue

- `Procfile`: `worker: python -m backend.worker`. Se verifica que el plan de hospedaje
  admita un segundo proceso (riesgo del plan maestro); si no, el worker puede correr
  como hilo del proceso web detrás de la variable `WORKER_EN_PROCESO_WEB=1`, que es un
  respaldo, no el diseño.
- `dev.sh` levanta el worker junto al backend y lo detiene con Ctrl+C.
- `.env.example`: documentar `FIEL_ENCRYPTION_KEY` (con el comando para generarla) y las
  variables nuevas: `SAT_SYNC_INTERVALO_SEG` (60), `SAT_SYNC_HORA_LOCAL` (03:00),
  `SAT_SYNC_TRASLAPE_DIAS` (7), `SAT_SYNC_MESES_CANCELACION` (3),
  `SAT_SYNC_MAX_EN_VUELO` (4).
- El Dockerfile ya instala lo necesario; no hay dependencias nuevas.

## Seguridad

- La e.firma sigue cifrada en reposo; el worker la descifra por corrida, en memoria, solo
  para empresas con `activa = TRUE`. Nada de ella va a logs, `error_msg` ni `auditoria`
  (se prueba con un caso que fuerza un error y revisa los textos).
- Consentimiento explícito y registrado (D8): sin `consentimiento: true` el endpoint
  rechaza. Quién y cuándo queda en `sat_sync_config`.
- Cada corrida automática escribe en `auditoria` (`usuario_id` nulo, `metadata.origen`):
  `sync_corrida_inicio`, `sync_corrida_fin` (con conteos) y `sync_pausada`.
- Los endpoints validan acceso a la empresa; el worker no expone puertos.
- Borrar la e.firma desactiva la automatización en la misma operación.

## Criterios de aceptación

Con datos sintéticos y un cliente SAT simulado (el SAT real solo en la verificación
manual con COPLASUR):

1. Activar sin consentimiento o sin e.firma vigente responde 422 y no crea solicitudes.
2. Activar crea una solicitud por (tipo, mes) del ejercicio actual y el anterior; ninguna
   cubre más de un mes.
3. **Reinicio**: matar el worker a mitad de una importación y volver a arrancarlo termina
   la solicitud sin duplicar CFDI (conteo igual al esperado) y sin intervención.
4. **Candado**: dos workers simultáneos sobre la misma empresa no importan el mismo
   paquete dos veces.
5. Corrida diaria: con `ultima_exitosa` de hace 2 días pide desde 9 días atrás (traslape
   de 7) y no vuelve a pedir meses anteriores.
6. Un CFDI vigente que aparece como cancelado en los metadatos queda `cancelado`; si su
   periodo tenía cédula calculada, no se recalcula y queda el evento de auditoría.
7. e.firma vencida: la empresa queda `pausada` con motivo, sin llamadas al SAT, y las
   demás empresas siguen avanzando.
8. Fallo del SAT: reintentos con la espera definida; al cuarto queda `fallo` con el
   mensaje del SAT visible en el historial; `ultima_exitosa` no avanza.
9. `5002` difiere sin contar intento; `5004` cierra con cero CFDI.
10. Desactivar detiene la creación y el avance; borrar la e.firma desactiva.
11. Ningún texto de log, `error_msg` o `auditoria` contiene la contraseña ni bytes de la
    e.firma (prueba dedicada).
12. Con COPLASUR, tras la carga inicial y para un mes cerrado, el conteo de CFDI por tipo
    coincide con el de la plataforma de referencia (verificación manual, mismo día).

Suite: `python -m pytest` completo y `npm test` en verde; `migration-validator` sobre la
031; `dominio-fiscal` sobre el manejo de cancelaciones (efecto sobre cálculos).

## Entregas

| Entrega | Contenido |
|---|---|
| F2.1 | Migración 031; extraer `_avanzar_solicitud` e importación a `backend/sat_sync.py` (sin cambio de comportamiento, con las pruebas existentes en verde); reintentos con `intentos`/`proximo_intento`; ventanas y partición por volumen |
| F2.2 | `worker.py` con candado, ciclo, carga inicial, corrida diaria y cierre de corrida; `Procfile`, `dev.sh`, `.env.example`; `/fiel/sync` deja de dormir |
| F2.3 | Endpoints `sync/estado`, `sync/config`, `sync/ahora`; pausa por vencimiento; auditoría |
| F2.4 | Cancelaciones: metadatos, parser, marcado y evento de auditoría |
| F2.5 | Pantalla: tarjeta de automatización, consentimiento, historial ampliado, indicador del menú |

Cada una con su plan en `docs/superpowers/plans/`, y todas dejan la aplicación
funcionando. F2.1 a F2.4 son backend y pueden revisarse sin tocar el frontend.

## Coordinación con F3.2 (otra sesión en paralelo)

- Migraciones: F2 usa **031**; F3.2, si necesita una, la **032**.
- `docs/openapi.yaml`: los dos agregan rutas distintas; conflictos se resuelven
  uniendo ambas.
- Menú lateral y layout: F3.2 lo reorganiza ("CFDIs" con Emitidos/Recibidos, periodo
  global). El indicador del menú de F2.5 se hace **al final** y sobre el menú ya
  integrado de F3.2 para no pelear el mismo archivo.
- `db.init_db()`: ambos agregan una línea al final; conflicto trivial.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| Límites del SAT (solicitudes por periodo, tamaño de resultado, máximo de paquetes) distintos a lo supuesto | Se verifican contra la documentación vigente al iniciar F2.1; los valores van en variables de entorno, no fijos; partición de ventanas ante rechazo por volumen |
| Los metadatos de cancelados no se pueden leer con satcfdi | Fallback documentado (XML de cancelados); se decide en F2.4 sin bloquear F2.1–F2.3 |
| El hospedaje no admite segundo proceso | `WORKER_EN_PROCESO_WEB` como respaldo; `/fiel/sync/avanzar` sigue existiendo |
| Fuga de la e.firma al operar desatendido | Sección Seguridad: consentimiento, memoria, auditoría, pausa y borrado |
| Dos corridas sobre la misma empresa | Advisory lock (D3) + índice único parcial + UPDATE condicional existente |
| Importación grande bloquea el ciclo de otras empresas | Se procesa un paquete por empresa por vuelta del ciclo; el progreso se guarda por paquete (ya ocurre) |
| Carga inicial de un RFC con cientos de miles de CFDI tarda días | Estado y progreso visibles; las ventanas se lanzan de a pocas; el listado (F3) muestra lo ya importado |

## Dudas abiertas

1. **Hora de la corrida diaria**: 03:00 hora de México por defecto; ¿se prefiere por
   empresa configurable desde la pantalla o fija global?
2. **Traslape y meses de cancelación** (7 días y 3 meses): valores iniciales razonables,
   a ajustar con datos reales de COPLASUR.
3. **Aviso al usuario** ante e.firma pausada o error hasta que exista la campana de M3:
   ¿solo el indicador del menú, o también correo? (Por defecto: solo indicador.)
