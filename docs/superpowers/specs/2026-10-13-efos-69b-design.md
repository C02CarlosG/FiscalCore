# EFOS — cruce de CFDI recibidos contra la lista 69-B del SAT

Fecha: 2026-10-13. Estado: spec pendiente de revisión. Origen: auditoría de ezaudita
(`comparativo/ezaudita/09_efos.json`) y plan maestro, fase **M3** (parte EFOS).

## Objetivo

Que FiscalCore avise qué proveedores de la empresa están en la lista de contribuyentes del
artículo 69-B del CFF (operaciones inexistentes, «EFOS»), muestre los CFDI recibidos de esos
emisores y mantenga la lista al día sin intervención manual.

## Contexto

- ezaudita tiene una pantalla EFOS con el esqueleto del listado de CFDI limitado a emisores
  en la lista, una fecha de «última actualización del listado EFOS» y un botón para ver el
  listado completo.
- FiscalCore ya reserva la columna «Lista 69-B» en Proveedores
  (`frontend/components/proveedores/ProveedoresPantalla.tsx`) y el listado de CFDI
  (`backend/cfdi_listado.py`) está diseñado para reutilizarse aquí (spec F3).
- El plan maestro difiere EFOS a M3; D9 pospone el envío de correos, así que las alertas por
  correo quedan fuera.

## La fuente: hechos verificados (2026-10-13)

El SAT publica el listado completo como CSV en
`http://omawww.sat.gob.mx/cifras_sat/Documents/Listado_completo_69-B.csv`. Se descargó a una
carpeta aislada y se analizó:

| Hecho | Valor |
|---|---|
| Tamaño | 4,566,277 bytes |
| Transporte | **Solo HTTP**: el HTTPS agotó el tiempo de espera (40 s) |
| Codificación | `cp1252` (no UTF-8) |
| Preámbulo | 2 líneas antes de la cabecera. La primera dice «Información actualizada al 31 de diciembre de 2025» |
| Cabecera | 20 columnas: `No`, `RFC`, `Nombre del Contribuyente`, `Situación del contribuyente` y 16 de oficios y fechas de publicación (SAT y DOF) para las etapas presunto, desvirtuado, definitivo y sentencia favorable |
| Filas / RFC únicos | 14,234 filas / 14,055 RFC |
| Situaciones | Definitivo 11,270 · Sentencia Favorable 1,638 · Presunto 986 · Desvirtuado 340 |
| RFC repetidos | 82 RFC en más de una fila; en 55 la situación difiere (p. ej. `AAS110331G59`: Definitivo en la fila 155 y Sentencia Favorable en la 156) |
| RFC genérico | `XXXXXXXXXXXX` aparece y no identifica a nadie |
| Frescura | El archivo dice 31/dic/2025; ezaudita mostraba su lista al 31/ago/2026. **La lista del SAT puede ir meses por detrás** |

Estos hechos mandan sobre cualquier suposición: el diseño los trata explícitamente.

## Decisiones (tomadas con Carlos, 2026-10-13)

| # | Decisión |
|---|---|
| E1 | Fuente: descarga **automática semanal** por el worker, más **carga manual de respaldo** y botón «Actualizar ahora», ambos solo para administradores de la plataforma |
| E2 | Riesgo: **Presunto** = riesgo alto; **Definitivo** = riesgo crítico. **Desvirtuado** y **Sentencia Favorable** se muestran como informativos, sin alerta |
| E3 | No se calcula el efecto legal por fecha de emisión frente a fecha de publicación: se muestran las fechas y el contador decide |
| E4 | Duplicados: la **situación vigente** de un RFC es la de su fila con mayor `No` (el SAT enumera cronológicamente). Se conservan todas las filas como historial |

## Alcance

Entra:
1. Importación de la lista (automática, forzada y manual) con bitácora.
2. Cruce de CFDI **recibidos** por RFC del emisor.
3. Pantalla «EFOS» y filtro `efos` en el listado de CFDI.
4. Columna «Lista 69-B» en Proveedores.
5. Estado de la lista (fecha del archivo, fecha de importación, antigüedad) visible al usuario.

No entra:
- Correos y campana de alertas (M3, aparte).
- Efecto legal por fechas (E3).
- Excluir operaciones con EFOS de DIOT o IVA.
- Cruzar CFDI **emitidos** (los clientes en la lista no tienen consecuencia fiscal para el emisor).
- Consulta del RFC contra el servicio individual del SAT.

## Diseño

### Datos (migración `073_efos_69b.sql`, idempotente)

La 072 es el criterio de efectivo (PR en curso); esta usa **073**.

- `efos_importaciones`: `id`, `origen` (`automatica` | `manual`), `usuario_id` (nulo si automática),
  `fecha_archivo DATE` (la de «actualizada al», nula si no se pudo leer), `sha256 TEXT`,
  `filas INT`, `rfc_unicos INT`, `estado` (`correcta` | `fallida` | `sin_cambios`), `mensaje TEXT`, `creado_en`.
- `efos_lista`: `importacion_id` (FK), `no_sat INT`, `rfc VARCHAR(13)` (mayúsculas), `nombre TEXT`,
  `situacion` con CHECK en (`Presunto`, `Desvirtuado`, `Definitivo`, `Sentencia Favorable`),
  fechas de publicación por etapa (`fecha_presunto_sat`, `fecha_desvirtuado_sat`,
  `fecha_definitivo_sat`, `fecha_sentencia_sat` y sus equivalentes DOF) y los oficios como texto.
  `UNIQUE (importacion_id, no_sat)`; índice en `(rfc)`.
- `efos_vigente` (vista): por RFC, la fila con mayor `no_sat` de la **última importación correcta**.
- Solo se conserva `efos_lista` de la última importación correcta (se reemplaza en la misma
  transacción); `efos_importaciones` conserva todo el historial.

### Importación (`backend/efos.py`, módulo propio, sin FastAPI)

Parser puro `parsear(contenido: bytes) -> ResultadoParseo` y `importar(...)` con SQL.

1. Decodifica `cp1252`; si falla, error claro (no se prueba otra codificación en silencio).
2. Localiza la cabecera por contenido (`RFC` y `Situación`), no por número de línea fijo; la
   primera línea del preámbulo se analiza para extraer `fecha_archivo` (mes en español).
3. Valida la cabecera: las 20 columnas esperadas, en ese orden.
4. Por fila: `RFC` con formato válido (`[A-ZÑ&]{3,4}\d{6}[A-Z0-9]{3}`) y distinto de `XXXXXXXXXXXX`;
   `situacion` dentro de las cuatro conocidas; fechas `dd/mm/aaaa` o vacío. Una fila inválida se
   descarta y se cuenta; si descartadas > 1 % de las filas, **la importación falla**.
5. Salvaguardas contra un archivo manipulado o roto (la descarga es HTTP sin TLS):
   - tamaño máximo 50 MB;
   - se rechaza si el número de filas válidas cae más de **20 %** respecto a la última importación
     correcta;
   - se registra el SHA-256; un archivo idéntico al anterior no reemplaza nada (se anota «sin cambios»);
   - todo el reemplazo es una sola transacción: si algo falla, la lista anterior queda intacta.
6. Los valores leídos del CSV viajan siempre como parámetros SQL; nunca se interpolan.

**Worker.** Un hilo/ciclo nuevo en `backend/worker.py` revisa cada hora si la última importación
automática tiene más de 7 días y, de ser así, descarga y llama a `importar`. Un fallo se registra en
`efos_importaciones` (estado `fallida`) y se reintenta en el siguiente ciclo sin afectar la descarga
de CFDI. URL configurable por `EFOS_URL` (por defecto la del SAT), con tiempo máximo de 60 s.

### API (`backend/routers/efos.py`)

- `GET /api/v1/efos/estado` (cualquier usuario autenticado): `{hay_lista, fecha_archivo, importada_en, filas,
  rfc_unicos, dias_de_antiguedad, desactualizada, ultimo_intento}` (`desactualizada` si la fecha del archivo
  tiene más de 45 días o no hay lista).
- `POST /api/v1/admin/efos/importar` (administrador de plataforma): fuerza la descarga ahora.
- `POST /api/v1/admin/efos/subir` (administrador de plataforma): sube el CSV a mano. Se valida el tipo
  y el tamaño en el límite del backend (CLAUDE.md, Seguridad).
- **El listado de CFDI de EFOS no tiene endpoint propio**: sale de `GET /api/v1/empresas/{id}/cfdis`
  (y `/resumen`, `/exportar`) con el nuevo filtro `efos=todos|en_lista|presunto|definitivo` (solo
  recibidos), de modo que lista, conteos, totales y exportación coinciden por construcción.
- **Proveedores**: cada ítem de `GET /api/v1/empresas/{id}/proveedores` trae `efos`
  (`{situacion, riesgo, fecha_publicacion}` o `null`).

Las operaciones de administración quedan en `auditoria` con usuario, origen y resultado. Todo se
documenta en `docs/openapi.yaml` (`test_openapi_sync.py`).

### Cruce

- Por **RFC del emisor** de cada CFDI recibido (`UPPER(TRIM(c.rfc_emisor))`) contra `efos_vigente.rfc`.
- Se agrega al catálogo de columnas de CFDI recibidos la columna `situacion_69b`.
- Se agrega al listado de CFDI el filtro `efos` (valores `todos`, `en_lista`, `presunto`, `definitivo`)
  reutilizando `condiciones()` de `cfdi_listado.py`, para que lista, conteos y acumulado coincidan.
- Solo CFDI vigentes (un cancelado no genera efecto).

### Pantalla

- Entrada de menú «EFOS» y página `empresas/[empresaId]/efos` con el esqueleto del listado de CFDI
  (periodo, búsqueda, totales periodo/acumulado, tabla, editor de columnas), columna «Situación 69-B»
  con insignia (Presunto = alto, Definitivo = crítico, Desvirtuado/Sentencia Favorable = informativo)
  y las fechas de publicación de la etapa vigente.
- Franja con el estado de la lista: «Lista del SAT actualizada al DD/MM/AAAA · importada el …» y un
  aviso destacado cuando `desactualizada`.
- Estado vacío: «Ningún proveedor de esta empresa está en la lista 69-B», con la fecha de la lista.
- Proveedores: la columna «Lista 69-B» muestra la misma insignia (o «—»).
- Para administradores de plataforma: botones «Actualizar ahora» y «Subir CSV» en la franja de estado.

## Criterios de aceptación

1. **Parser**, con un CSV de muestra sintético (no se versiona el archivo real del SAT) que reproduce:
   preámbulo de 2 líneas, cp1252 con acentos y `Ñ`, un RFC repetido con situación distinta, el RFC
   genérico y una fila con RFC inválido: devuelve las filas esperadas, descarta la genérica y la
   inválida, y calcula `fecha_archivo`.
2. **Duplicados:** para `AAS110331G59` (Definitivo → Sentencia Favorable) `efos_vigente` devuelve
   Sentencia Favorable y el historial conserva ambas filas.
3. Una importación cuya cabecera no es la esperada, con más de 1 % de filas inválidas o con una caída
   de más de 20 % de filas **falla y deja intacta** la lista anterior (se comprueba el contenido de
   `efos_lista` antes y después).
4. Un archivo idéntico (mismo SHA-256) no reemplaza la lista y queda anotado «sin cambios».
5. Un CFDI recibido de un RFC **Definitivo** aparece en la pantalla con riesgo crítico; de un
   **Presunto**, con riesgo alto; de un **Desvirtuado** o **Sentencia Favorable**, como informativo y sin
   alerta; un CFDI **cancelado** no aparece; un CFDI **emitido** por la empresa nunca aparece.
6. Totales de la pantalla = suma de los mismos CFDI del listado con el filtro `efos`; el acumulado
   respeta el ejercicio.
7. Solo un administrador de la plataforma puede importar o subir (403 en otro caso); todo queda en
   `auditoria`.
8. `desactualizada` es verdadero con la lista del 31/dic/2025 al 13/oct/2026 y falso con una lista
   de hace 10 días.
9. El worker no descarga si la última importación automática tiene menos de 7 días, y un fallo de
   red no detiene el ciclo de descarga de CFDI.

## Riesgos y cómo se tratan

- **HTTP sin TLS:** un atacante en la red podría alterar el archivo. Se mitiga con las salvaguardas de
  la importación y la carga manual; no se puede resolver del lado de FiscalCore mientras el SAT no
  sirva HTTPS. Se documenta en la pantalla de administración.
- **Lista del SAT atrasada:** se muestra siempre su fecha y se avisa. La carga manual permite usar un
  listado más reciente obtenido por otra vía.
- **Falsos positivos por RFC repetido:** resueltos por E4 y visibles en el historial.
- **Cambio de formato del SAT:** la cabecera exacta hace que falle ruidosamente, no en silencio.

## Verificación

`python -m pytest` completo (unitarias y `-m db`), `npm test` en verde, revisión del cambio de la
migración 073 y revisión fiscal de la regla de riesgo (E2/E3) antes de integrar.
