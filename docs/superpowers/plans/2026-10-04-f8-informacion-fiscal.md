# Plan F8 — Información fiscal (carril D)

Spec: `docs/superpowers/specs/2026-10-04-f8-informacion-fiscal-design.md`.
Rama: `claude/d-f8-informacion-fiscal` desde `origin/main`. PR: `D·F8: información fiscal`.

Cada tarea empieza con la prueba en rojo, luego el código, luego la verificación.
Fixtures: PDF sintéticos generados en memoria; nunca un PDF real del SAT.

## Tarea 1 — Parser de constancia: fecha, idCIF y estatus

- Prueba (`backend/tests/test_constancia_parser.py`): con texto "Lugar y Fecha de
  Emisión OAXACA DE JUAREZ, OAXACA A 03 DE OCTUBRE DE 2026", `idCIF: 12345678901`,
  "Estatus en el padrón: ACTIVO", `parsear_constancia` devuelve `fecha_emision =
  "2026-10-03"`, `id_cif`, `estatus_padron = "ACTIVO"`; las claves existentes siguen.
- Código: `backend/constancia_parser.py` (`extraer_texto` público; helpers nuevos).
- Verificación: `python -m pytest backend/tests/test_constancia_parser.py`.

## Tarea 2 — Módulo puro `informacion_fiscal.py`

- Pruebas (`backend/tests/test_informacion_fiscal.py`):
  - `buscar_rfc` con "RFC:", "Clave de R.F.C.:" y sin etiqueta.
  - `buscar_fecha` en letra y en número; mes inválido → `None`.
  - `detectar_tipo` para constancia, opinión y texto ajeno.
  - `parsear_opinion`: sentido positivo/negativo/inscrito sin obligaciones/no
    inscrito, folio y fecha tras "Revisión practicada el día".
  - `estado_opinion`: emitida 2026-10-03 → vigente hasta 2026-11-01 (vigente ese día,
    vencida el 02); solo la positiva tiene vigencia (regla 2.1.36 RMF 2026).
  - `validar_pdf`: sin `%PDF-`, ilegible, más de 10 páginas.
  - `analizar_documento`: RFC distinto, sin RFC, tipo cruzado, caso feliz.
- Código: `backend/informacion_fiscal.py`.
- Verificación: `python -m pytest backend/tests/test_informacion_fiscal.py`.

## Tarea 3 — Migración 060

- Prueba (`backend/tests/test_migracion_060.py`, `-m db`): `init_db()` dos veces;
  existen la tabla, sus columnas, el índice y el `UNIQUE`; el `CHECK` rechaza otro tipo.
- Código: `database/migrations/060_documentos_fiscales.sql` y la línea en
  `backend/db.py::init_db` (solo agregar).
- Verificación: `python -m pytest backend/tests/test_migracion_060.py` y revisión del
  agente `migration-validator`.

## Tarea 4 — Router

- Pruebas (`backend/tests/test_router_informacion_fiscal.py`, base mockeada):
  401 sin sesión; 403 sin acceso; 400 extensión; 413 tamaño; 422 tipo de ruta inválido;
  422 RFC ajeno sin `INSERT`; 201 con insert de bytes, sha256 y datos; 409 por
  `UniqueViolation`; resumen con `vigente`; PDF `inline` y `attachment`; 404 de
  documento de otra empresa; 204 al eliminar; auditoría en subir y eliminar.
- Código: `backend/routers/informacion_fiscal.py`, `include_router` en
  `backend/main_api.py`, rutas y esquemas en `docs/openapi.yaml`.
- Verificación: `python -m pytest -m "not db"` (incluye `test_openapi_sync.py`).

## Tarea 5 — Integración contra Postgres

- Prueba (`backend/tests/test_e2e_informacion_fiscal.py`, `-m db`): crear empresa y
  usuario, subir constancia y opinión sintéticas, listar, descargar idéntico byte por
  byte, repetir → 409, otro usuario → 403, eliminar → 204 y ya no aparece.
- Verificación: `python -m pytest -m db -k informacion_fiscal`.

## Tarea 6 — Frontend

- Pruebas (vitest):
  - `components/informacion-fiscal/DocumentoFiscalCard.test.tsx`: sin documento;
    opinión vigente y vencida; constancia con regímenes; validación local de
    extensión/tamaño; envía `FormData` a la ruta correcta; muestra el error del
    backend; Ver abre el visor con el blob; Descargar.
  - `HistorialDocumentos.test.tsx`: lista y elimina con confirmación.
- Código: `hooks/useInformacionFiscal.ts`, `components/informacion-fiscal/`
  (`tipos.ts`, `DocumentoFiscalCard.tsx`, `VisorPdfDialog.tsx`,
  `HistorialDocumentos.tsx`), página `app/(app)/empresas/[empresaId]/informacion-fiscal/page.tsx`
  y entrada en `Sidebar.tsx` (solo agregar).
- Verificación: `cd frontend && npm test && npx tsc --noEmit && npm run lint`.

## Tarea 7 — Cierre

- Traer `origin/main` con merge; `python -m pytest` y `npm test` completos.
- Revisión `dominio-fiscal` (vigencia y sentidos de la opinión) y `migration-validator`.
- Actualizar la fila de F8 en "Estado" del plan maestro.
- PR en borrador `D·F8: información fiscal (constancia y opinión de cumplimiento)`;
  avisar a la sesión coordinadora.
