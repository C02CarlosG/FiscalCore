# F3.6 — Etiquetas, comentarios y evidencias por CFDI (diseño)

Fecha: 2026-10-05. Carril A. Depende de F3.3 (visor) y F3.5b (listado por tipo). Migraciones 042 y 043.
Referencia: `2026-10-01-referencia-plataforma.md`, "CFDIs emitidos / recibidos" (columnas de etiquetas y
comentarios con "Agregar", icono de evidencia, casilla de selección para acciones en lote, selector de
etiquetas y acceso a evidencias al pie del visor).

## Alcance
1. **Etiquetas**: catálogo por empresa (nombre y color) y asignación a CFDI. Columna "Etiquetas" en el listado,
   selector en el visor, filtro por etiqueta.
2. **Comentarios**: texto libre por CFDI con autor y fecha (varios por CFDI, cronológicos). Columna con el conteo.
3. **Evidencias**: archivos adjuntos a un CFDI (PDF, imagen, hoja de cálculo, texto, XML). Subir, listar, descargar,
   eliminar. Cada alta, descarga y baja queda en `auditoria`.
4. **Selección en lote**: casilla por fila y "seleccionar la página"; acciones masivas de agregar o quitar etiqueta
   (hasta 500 CFDI por llamada).

No entra: PDF generado del CFDI; exportación de evidencias como trabajo en cola; etiquetas globales entre empresas.

## Decisiones
| # | Decisión | Motivo |
|---|---|---|
| D1 | Evidencias en Postgres (`bytea`), no en disco | El despliegue no garantiza disco persistente; un respaldo de la base ya las incluye; el tope (5 MB, 20 por CFDI) lo hace viable |
| D2 | Tipo permitido por **contenido** (firma de bytes) y por extensión; lista blanca | Un nombre o `Content-Type` los controla quien sube; el archivo se valida en el servidor |
| D3 | Descarga siempre como adjunto, `X-Content-Type-Options: nosniff`, nombre saneado | Una evidencia nunca se interpreta ni se muestra en línea desde el dominio de la API |
| D4 | Las etiquetas pertenecen a la empresa; un CFDI solo recibe etiquetas de su empresa | Aislamiento entre empresas |
| D5 | Rol: cualquier usuario con acceso a la empresa puede etiquetar y comentar; solo quien subió (o un admin) borra una evidencia o comentario | Misma regla que el resto de la API (`validar_acceso_empresa`) |
| D6 | Etiquetas y comentarios sobreviven a un reproceso del XML | Se enlazan por `cfdi_id`, no por el detalle extraído |

## Datos
- **042**: `etiquetas (id, empresa_id, nombre, color, created_at)` con `UNIQUE (empresa_id, lower(nombre))`;
  `cfdi_etiquetas (cfdi_id, etiqueta_id, usuario_id, created_at)` PK `(cfdi_id, etiqueta_id)`, borrado en cascada;
  `cfdi_comentarios (id, cfdi_id, empresa_id, usuario_id, texto, created_at)` con tope de largo.
- **043**: `cfdi_evidencias (id, cfdi_id, empresa_id, usuario_id, nombre, tipo_mime, tamano, sha256, contenido bytea,
  created_at)`; índice por `cfdi_id`; sin `contenido` en los listados (columna aparte en las consultas).

## API (`/api/v1/empresas/{empresa_id}`, sesión y `validar_acceso_empresa`)
- `GET/POST /etiquetas`, `PATCH/DELETE /etiquetas/{id}`.
- `POST /cfdis/etiquetas/lote` `{uuids: [...], agregar: [ids], quitar: [ids]}` (máx. 500 uuids, 10 etiquetas).
- `GET/POST /cfdis/{uuid}/comentarios`, `DELETE .../comentarios/{id}`.
- `GET/POST /cfdis/{uuid}/evidencias`, `GET .../evidencias/{id}` (descarga), `DELETE .../evidencias/{id}`.
- `GET /cfdis` acepta `etiqueta=<id>` y devuelve `etiquetas` y `comentarios` (conteo) y `evidencias` (conteo) por fila.
  `GET /cfdis/columnas` publica "Etiquetas", "Comentarios" y "Evidencias".

## Pantalla
Casilla por fila y en el encabezado; barra de acciones en lote al seleccionar; chips de etiquetas en la fila; en el
visor: selector de etiquetas, comentarios y lista de evidencias con subir/descargar/eliminar; filtro por etiqueta.

## Pruebas obligatorias
- Aislamiento: etiqueta, comentario o evidencia de otra empresa → 404/403 en todos los endpoints.
- Evidencias: tipo falso con extensión válida → 422; sobre el tope → 413; descarga con `Content-Disposition: attachment`
  y `nosniff`; nombre con `../` o saltos de línea saneado; el contenido no viaja en los listados.
- Lote: máximo, uuids de otra empresa se ignoran sin filtrarlos, idempotente.
- Auditoría de alta, descarga y baja de evidencias.
- Reproceso del XML no borra etiquetas ni comentarios.

## Riesgos
| Riesgo | Mitigación |
|---|---|
| Subida de archivo malicioso | Lista blanca por contenido, tope de tamaño, descarga como adjunto, sin ejecución ni vista en línea |
| Base que crece con evidencias | Tope por archivo y por CFDI; el tamaño se muestra; revisar si una empresa lo rebasa antes de pasar a almacenamiento de objetos |
| Filtro por etiqueta lento en listados grandes | Índice `(etiqueta_id, cfdi_id)` y subconsulta `EXISTS` sobre la página filtrada |
