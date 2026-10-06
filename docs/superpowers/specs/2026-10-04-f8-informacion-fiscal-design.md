# F8 — Información fiscal: constancia de situación fiscal y opinión de cumplimiento

Fecha: 2026-10-04. Carril D. Estado: en implementación.
Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md` (fase F8, decisión D4).

## Objetivo

Que el contador guarde, por empresa, la **constancia de situación fiscal** (CSF) y la
**opinión del cumplimiento de obligaciones fiscales** (32-D) del SAT, las vea en
pantalla, las descargue y sepa de un vistazo si la opinión sigue vigente y en qué
sentido salió. Equivale a "Sincroniza SAT → Información Fiscal" de la plataforma de
referencia, sin copiar su marca ni sus textos.

## Alcance

Entra:

- Carga manual del PDF (decisión D4), uno por tipo de documento cada vez.
- Validaciones en el backend: extensión, tipo de contenido, firma `%PDF-`, tamaño,
  número de páginas, que el PDF se pueda leer, que el documento sea del tipo que se
  dice (una opinión no se acepta como constancia) y que el RFC del documento sea el
  de la empresa.
- Datos que se leen del PDF y se muestran: RFC, nombre o razón social, fecha de
  emisión; en la constancia, regímenes, código postal, estatus en el padrón e idCIF;
  en la opinión, sentido y folio.
- Historial por empresa y tipo: el último documento es el vigente para la pantalla,
  los anteriores se conservan para consulta y se pueden eliminar.
- Visor dentro de la app y descarga del PDF original, sin cambios.
- Auditoría de carga y eliminación.

No entra:

- Descarga automática desde el portal del SAT (D4: se evalúa aparte).
- Opiniones de IMSS e INFONAVIT (mismo diseño, otro tipo; se agregan si se piden).
- Actualizar los datos de la empresa (régimen, código postal) con lo leído de la
  constancia: `empresas` es del carril B. Queda como pedido entre carriles si se
  quiere después.
- Alertas por opinión vencida o negativa: es M3 (carril B), que puede leer la tabla
  nueva.

## Reglas fiscales

| Regla | Fundamento | Cómo se aplica |
|---|---|---|
| La opinión del cumplimiento se emite en sentido **positivo**, **negativo**, **en suspensión de actividades** o **inscrito sin obligaciones**. El portal también puede mostrar **no inscrito**, aunque no es un sentido de la regla | Art. 32-D CFF; regla 2.1.36 de la RMF 2026 (2.1.37 en RMF anteriores) | Se lee del texto. Si menciona varios sentidos gana el más desfavorable (negativo > suspensión > no inscrito > inscrito sin obligaciones > positivo), para no presentar nunca como positiva una opinión que podría no serlo. Si no se identifica, queda "no identificado" y el documento se acepta igual. El sentido sale del PDF subido y no se verifica contra el SAT; la pantalla lo advierte |
| Solo la opinión **positiva** tiene vigencia: **30 días naturales** a partir de su emisión | Regla 2.1.36 de la RMF 2026 | Que el día de emisión cuente como el primero es una **interpretación**, no texto expreso: `vigente_hasta = fecha_emision + 29 días` y vigente si `hoy <= vigente_hasta`. Es la lectura que no sobrestima la vigencia frente a un tercero que aplique la estricta. Cualquier otro sentido, o un sentido no identificado, da `vigente = false` con su `motivo`. "Hoy" es la fecha en la Ciudad de México. Se calcula al consultar, no se guarda |
| La constancia no tiene vencimiento legal | Art. 27 CFF (inscripción y actualización en el RFC) | Solo se muestra su antigüedad en días. Muchos clientes y bancos piden una de menos de 30 días; la pantalla lo señala como aviso, no como vencimiento |
| El RFC del documento debe ser el de la empresa | Validación de integridad de FiscalCore (D4) | Se compara el RFC etiquetado del documento, en mayúsculas y sin espacios, contra `empresas.rfc`; si difiere o no se encuentra, 422 |

## Datos

Migración `060_documentos_fiscales.sql` (rango del carril D, idempotente):

```sql
CREATE TABLE IF NOT EXISTS documentos_fiscales (
    id             UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    empresa_id     UUID NOT NULL REFERENCES empresas(id) ON DELETE CASCADE,
    tipo           VARCHAR(20) NOT NULL CHECK (tipo IN ('constancia', 'opinion')),
    nombre_archivo VARCHAR(255) NOT NULL,
    contenido      BYTEA NOT NULL,
    tamano_bytes   INTEGER NOT NULL,
    sha256         CHAR(64) NOT NULL,
    rfc            VARCHAR(13) NOT NULL,
    fecha_emision  DATE,
    datos          JSONB NOT NULL DEFAULT '{}'::jsonb,
    usuario_id     UUID REFERENCES usuarios(id) ON DELETE SET NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (empresa_id, tipo, sha256)
);
CREATE INDEX IF NOT EXISTS idx_documentos_fiscales_empresa
    ON documentos_fiscales (empresa_id, tipo, created_at DESC);
```

- El PDF se guarda en Postgres (`BYTEA`), no en disco: el contenedor de despliegue es
  efímero y así el archivo se borra junto con la empresa. Con el tope de 5 MB y
  documentos de 1 a 3 páginas (100–400 KB en la práctica) el volumen es chico.
- `datos` guarda solo lo que la pantalla muestra: razón social (en persona física,
  nombre y apellidos), regímenes, código postal, estatus, idCIF, sentido y folio. No se
  guardan la CURP ni las obligaciones.
- Documento vigente = el de `fecha_emision` más reciente por empresa y tipo (nulas al
  final; a igual fecha, el último subido). Subir hoy una opinión vieja no reemplaza a
  la más reciente.
- `contenido` lleva `CHECK (octet_length(contenido) <= 5242880)` y `tamano_bytes > 0`
  como defensa en la base del tope del backend.
- El mismo PDF (mismo `sha256`) dos veces para la misma empresa y tipo responde 409.

## Módulos

- `backend/constancia_parser.py` (existente, del carril D): se agregan `fecha_emision`,
  `id_cif` y `estatus_padron` al resultado de `parsear_constancia`, y se expone
  `extraer_texto`. Lo que ya devuelve no cambia (lo usa `/api/v1/constancia/parsear`).
- `backend/informacion_fiscal.py` (nuevo, puro, sin base de datos; reutiliza `constancia_parser.RFC_PATRON`):
  - `validar_pdf(contenido)` — firma `%PDF-`, legible, no cifrado, máximo 10 páginas.
  - `detectar_tipo(texto)` — `constancia`, `opinion` o `None`.
  - `buscar_rfc(texto)` — RFC tras la etiqueta `RFC` o `R.F.C.` (la opinión usa
    "Clave de R.F.C.").
  - Fechas "03 DE OCTUBRE DE 2026" y "03/10/2026" (`constancia_parser.fecha_en_texto`), solo tras un ancla ("Fecha de Emisión", "practicada el día"); sin ancla queda nula. Una fecha posterior a hoy se rechaza (422).
  - `parsear_opinion(texto)` — RFC, razón social, fecha de emisión, sentido, folio.
  - `analizar_documento(tipo, contenido, rfc_empresa)` — orquesta lo anterior y
    lanza `DocumentoInvalido(mensaje)` ante cualquier regla rota.
  - `estado_opinion(fecha_emision, sentido, hoy)`, `antiguedad_dias(...)` y `hoy_mexico()`.
- `backend/routers/informacion_fiscal.py` (nuevo): rutas delgadas; acceso por
  `validar_acceso_empresa`, auditoría con `registrar_evento` (se importa de B sin
  editarlo). La lectura del PDF corre fuera del event loop (`run_in_threadpool`) y la
  carga está limitada a 20 por minuto. El PDF se entrega con `Content-Security-Policy: sandbox`.

## API

Prefijo `/api/v1/informacion-fiscal/empresas/{empresa_id}`. Todas requieren sesión y
acceso a la empresa (403 si no lo tiene, 404 si la empresa no existe).

| Método y ruta | Qué hace | Respuestas |
|---|---|---|
| `GET /` | Documento vigente de cada tipo (fecha de emisión más reciente): `{"constancia": Documento \| null, "opinion": Documento \| null}` | 200 |
| `GET /documentos?tipo=` | Historial (sin el PDF), más reciente primero; `tipo` opcional | 200, 422 tipo inválido |
| `POST /documentos/{tipo}` (multipart `archivo`) | Valida, lee y guarda | 201 `Documento`; 400 extensión o tipo de contenido; 413 tamaño; 409 ya cargado; 422 PDF ilegible, de otro tipo o de otro RFC |
| `GET /documentos/{documento_id}/pdf?descargar=` | El PDF tal cual se subió. `inline` por defecto (visor), `attachment` con `descargar=true` | 200 `application/pdf`, 404 |
| `DELETE /documentos/{documento_id}` | Elimina el documento | 204, 404 |

`Documento`:

```json
{
  "id": "uuid", "tipo": "opinion", "nombre_archivo": "32D.pdf", "tamano_bytes": 81234,
  "rfc": "ACM010101AA1", "fecha_emision": "2026-10-03", "created_at": "2026-10-04T10:00:00+00:00",
  "datos": {"razon_social": "…", "sentido": "positivo", "folio": "26NA1234567"},
  "antiguedad_dias": 1,
  "vigente_hasta": "2026-11-01",
  "vigente": true,
  "motivo": null
}
```

`vigente_hasta`, `vigente` y `motivo` solo tienen valor en la opinión (en la constancia son `null`).
`motivo` explica un `vigente = false`: `sentido_no_positivo`, `sentido_no_identificado`,
`sin_fecha` o `vencida`.
Un `documento_id` de otra empresa responde 404, igual que uno inexistente.

Mensajes de 422 (los ve el usuario tal cual):

- "No se pudo leer el PDF. Sube el archivo que descargaste del SAT, no una foto ni un escaneo."
- "El PDF está protegido con contraseña."
- "El archivo no parece una constancia de situación fiscal." / "…una opinión del cumplimiento de obligaciones fiscales."
- "No se encontró el RFC en el documento."
- "El documento es del RFC XXX, pero la empresa es YYY." (ambos se comparan sin espacios ni guiones)
- "La fecha de emisión del documento (…) es posterior a hoy; …"

## Pantalla

Ruta `/empresas/{id}/informacion-fiscal`, entrada "Información fiscal" en el menú
lateral, grupo Fiscal. Componentes en `frontend/components/informacion-fiscal/`:

- `DocumentoFiscalCard` (una por tipo): estado del último documento (para la opinión,
  insignia de sentido y "Vigente hasta 01/11/2026" o "Vencida hace N días"; para la
  constancia, regímenes, CP y antigüedad), botones **Ver** y **Descargar**, y el
  formulario para subir uno nuevo con el error del backend tal cual.
- `VisorPdfDialog`: pide el PDF con la sesión (`apiDescargar`), lo muestra en un
  `iframe` con URL de objeto y la libera al cerrar.
- `HistorialDocumentos`: lista de cargas anteriores con ver, descargar y eliminar
  (con confirmación).

Validación previa en el navegador (solo por comodidad, el backend decide): extensión
`.pdf` y tamaño máximo de 5 MB.

## Régimen fiscal de la empresa desde la constancia (2026-10-06)

Pedido del punto de control de paridad: que los avisos de «régimen no soportado» de ISR
desaparezcan al cargar la constancia.

- **Nombre → clave.** Cada régimen que lee la constancia se traduce a su clave de
  `c_RegimenFiscal` (sin acentos ni mayúsculas, del nombre más específico al más
  general: «…con ingresos a través de Plataformas Tecnológicas» es 625, no 612).
- **Guardado al subir.** Si la empresa no tiene régimen y la constancia trae uno
  principal, se guarda solo en `empresas.regimen_fiscal` con el formato que lee ISR
  («612 - Personas Físicas…»). No cuentan como principales 605, 608, 611, 614, 615 y 616
  (sueldos, demás ingresos, dividendos, intereses, premios, sin obligaciones). Con dos
  principales (p. ej. 612 y 606) no se guarda nada y decide una persona.
- **Nunca sobrescribe** un régimen capturado. Si la constancia vigente trae otro,
  `GET …/regimen` lo devuelve como `sugerido` y la tarjeta «Régimen fiscal» lo ofrece.
- **`PUT …/regimen {codigo}`.** Cualquier miembro con acceso a la empresa puede guardar
  una clave del catálogo (422 si no existe).
- **Auditoría.** `informacion_fiscal.regimen` con `de`, `a` y `origen`
  (`constancia` o `manual`).
- **Carril B.** Se escribe la columna `empresas.regimen_fiscal` desde rutas del carril D,
  como autorizó la coordinación; anotado en «Pedidos entre carriles».

## Criterios de aceptación

1. Subir una constancia sintética con RFC `ACM010101AA1` a la empresa de ese RFC
   responde 201 con `fecha_emision`, regímenes y CP leídos.
2. La misma constancia en una empresa con otro RFC responde 422 con ambos RFC en el
   mensaje; no se guarda nada.
3. Una opinión subida como constancia (y al revés) responde 422.
4. Un archivo `.pdf` que no empieza con `%PDF-`, uno de más de 5 MB y uno de más de 10
   páginas se rechazan sin guardar.
5. Opinión positiva emitida el 2026-10-03: `vigente_hasta = 2026-11-01`, vigente el
   2026-11-01 y vencida el 2026-11-02. Una opinión negativa, en suspensión o sin sentido
   identificado nunca sale vigente.
6. El PDF descargado es idéntico byte por byte al subido.
7. Un usuario sin acceso a la empresa recibe 403 en todas las rutas; un documento de
   otra empresa da 404.
8. La pantalla muestra el estado, abre el visor, descarga y sube un documento nuevo,
   mostrando el error del backend cuando lo rechaza.

## Pruebas

- Unitarias de `informacion_fiscal.py` y `constancia_parser.py` con PDF sintéticos
  generados en memoria (no se commitean PDF reales; ya existe el generador mínimo en
  `test_constancia_parser.py`).
- Router con base mockeada (`test_router_informacion_fiscal.py`).
- Integración `-m db`: migración 060 idempotente y ciclo subir → listar → descargar →
  eliminar contra Postgres.
- Vitest de `DocumentoFiscalCard` y de la página.

## Riesgos

| Riesgo | Mitigación |
|---|---|
| El texto real de los PDF del SAT difiere de los ejemplos públicos usados para las expresiones | Lectura tolerante (acentos, mayúsculas, "RFC"/"R.F.C."); sentido y fecha pueden quedar nulos sin rechazar el documento. Carlos valida con un PDF real en local antes de integrar (sin commitearlo) |
| PDF escaneado sin texto | Se rechaza con mensaje claro: sin texto no se puede comprobar el RFC |
| PDF malicioso o enorme | Firma, tamaño (5 MB) y páginas (10) se revisan antes de abrirlo a fondo; el PDF nunca se ejecuta en el servidor y en el navegador se muestra en el visor nativo |
