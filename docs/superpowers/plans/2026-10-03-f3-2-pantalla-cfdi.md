# F3.2 — Pantalla única de CFDI — Implementation Plan

> **Para quien implemente:** cada tarea va con prueba primero (se escribe, se ve fallar, se implementa, se ve pasar). Los pasos usan casillas `- [ ]` para llevar el avance.

**Goal:** Reemplazar las cuatro pantallas de CFDI (Visor SAT, Emitidos, Recibidos, Nómina) por una sola pantalla de Emitidos y otra de Recibidos que consumen la API de F3.1: pestañas por tipo con conteo, totales del periodo y del acumulado, tabla paginada y ordenada en el servidor, y todo el estado en la URL. El periodo pasa a ser global.

**Architecture:** Estado de la pantalla en los parámetros de la URL (funciones puras de lectura/escritura, probadas sin React). Un hook de periodo global resuelve `URL → último periodo usado de la empresa → mes actual`. Tres hooks de TanStack Query (`columnas`, `resumen`, `listado`) con los mismos parámetros. Componentes chicos y sin estado propio (barra, pestañas, totales, tabla) que componen `CfdiPantalla`.

**Tech Stack:** Next.js (App Router), TypeScript, TanStack Query, Tailwind + shadcn/ui, Vitest + Testing Library. Backend: un campo nuevo (`rol`) en la respuesta del login.

**Spec:** `docs/superpowers/specs/2026-10-02-f3-listado-cfdi-design.md` — entrega F3.2 (secciones "Pantalla", "Correcciones incluidas" y criterios de aceptación 8). Plan maestro: `2026-10-01-paridad-y-mejoras-roadmap.md`.

## Alcance de esta entrega

**Entra:** periodo global; estado en la URL; barra (periodo, búsqueda, estado, método, sub-filtro de PPD); pestañas con conteo; totales; tabla con paginación en servidor, orden por columna y columnas por defecto del catálogo; estados de carga, vacío y error; advertencias de anticipos; retiro de las pantallas Visor SAT y Nómina; correcciones chicas.

**No entra (queda en su entrega):** conceptos desplegables, visor y descarga del XML (F3.3); editor de columnas, filtro avanzado y exportar (F3.4); columnas y totales propios de Nómina y Pago, y cancelados desde el SAT (F3.5). En F3.2 las cinco pestañas usan las columnas y totales de comprobante que ya entrega la API.

**Decisión sobre Nómina:** la pantalla vieja de Nómina solo muestra total, recibos, vigentes, canceladas y una lista de 6 columnas. La pestaña Nómina de la pantalla nueva ya cubre todo eso, así que se retira en esta entrega sin perder información. Los endpoints viejos del backend (`/emitidos`, `/recibidos`, `/cfdi/visor`, `/cfdi/nomina`) **no** se tocan: se retiran al terminar F3.5, como dice la spec.

## Global Constraints

- Rama de la sesión `ccr-687232b3-zez9ts`, creada desde `main` (PR #11 a #18 ya integrados).
- Línea base antes de empezar: `python -m pytest` → 596 passed; `npm test` → 137 passed.
- Todo el estado de la pantalla vive en la URL; los valores por defecto **no** se escriben en ella (URL corta). Cambiar cualquier filtro regresa `pagina` a 1.
- Fechas siempre `dd/mm/aaaa` (con hora `dd/mm/aaaa hh:mm` para `fecha_hora`). Las fechas del API vienen en ISO sin zona y **no** se pasan por `new Date()` (el navegador las desplazaría de zona): se formatean por texto.
- Importes en `es-MX` con `Intl.NumberFormat`; `null` se muestra como guion (`—`), nunca como cero.
- Los hooks de datos no se ejecutan sin `empresaId` y `periodo` válidos.
- Cada paso de interfaz con texto visible lleva su prueba con Testing Library; los mocks de `next/navigation` siguen el patrón de `Sidebar.test.tsx`.
- Sin dependencias nuevas.

## Review Focus

- Recargar con filtros aplicados reproduce la misma vista (criterio 8 de la spec) — Task 2 y Task 6.
- Cambiar de filtro regresa a la página 1; cambiar solo la página no toca los filtros — Task 2.
- Una fecha ISO sin zona se muestra con el día correcto, sin desplazarse — Task 1.
- El periodo recordado de una empresa no se usa en otra — Task 1 y Task 2.
- El score del dashboard es el del periodo elegido, no el último de la tendencia — Task 4.
- Quitar el Visor SAT y Nómina no deja enlaces rotos (menú, redirecciones, pruebas e2e) — Task 7.

---

### Task 1: Utilidades de periodo y de formato

**Files:**
- Create: `frontend/lib/periodo.ts`, `frontend/lib/periodo.test.ts`
- Create: `frontend/lib/formato.ts`, `frontend/lib/formato.test.ts`

**Interfaces (produce):**
- `esPeriodoValido(p: string): boolean` — `YYYY-MM` entre 2000 y 2099, mes 01–12.
- `periodoActual(hoy?: Date): string`.
- `etiquetaPeriodo("2026-09") → "2026 - Septiembre"`.
- `periodoRecordado(empresaId): string | null` y `recordarPeriodo(empresaId, periodo): void` — `localStorage` con `try/catch`, llave `fiscalcore-periodo-<empresaId>`.
- `resolverPeriodo({ url, empresaId, hoy? }): string` — URL válida, si no el recordado válido, si no el mes actual.
- `formatearFecha("2026-09-05") → "05/09/2026"`; `formatearFechaHora("2026-09-05T13:07:09") → "05/09/2026 13:07"`; `formatearMoneda(1234.5) → "$1,234.50"`; todos devuelven `"—"` ante `null`, `undefined` o texto que no sea fecha.

- [ ] **Step 1: Pruebas que fallan** — casos: periodos válidos e inválidos (`2026-13`, `26-09`, `""`); etiqueta de los 12 meses; `resolverPeriodo` con URL válida, URL inválida con recordado, ambos ausentes, y recordado de **otra** empresa ignorado; `localStorage` que lanza excepción no rompe; fecha `2026-12-31T23:30:00` conserva el día 31 (sin conversión de zona); `null` → `—`.
- [ ] **Step 2:** `cd frontend && npx vitest run lib/periodo.test.ts lib/formato.test.ts` → FAIL (módulos inexistentes).
- [ ] **Step 3:** Implementar ambos módulos. Las fechas se formatean cortando el texto ISO (`slice`), no con `Date`.
- [ ] **Step 4:** Mismo comando → PASS.
- [ ] **Step 5:** Commit `feat: utilidades de periodo y formato para el listado de CFDI`.

### Task 2: Estado de la URL y periodo global

**Files:**
- Create: `frontend/lib/cfdi-url.ts`, `frontend/lib/cfdi-url.test.ts`
- Create: `frontend/hooks/useUrlParams.ts`
- Create: `frontend/hooks/usePeriodoGlobal.ts`, `frontend/hooks/usePeriodoGlobal.test.tsx`

**Interfaces (produce):**
```ts
export type CfdiEstadoUrl = {
  periodo: string; tipo: "I" | "E" | "T" | "N" | "P";
  estado: "vigente" | "cancelado" | "todos"; metodo: "PUE" | "PPD" | "todos";
  pago: "pendientes" | "pagadas" | "todos"; q: string; filtros: string;
  orden: string; dir: "asc" | "desc"; pagina: number; porPagina: 30 | 50 | 100;
};
export function leerEstado(params: URLSearchParams, periodo: string): CfdiEstadoUrl;   // valores inválidos → default
export function escribirEstado(actual: URLSearchParams, parche: Partial<CfdiEstadoUrl>): URLSearchParams;
export function consultaApi(estado: CfdiEstadoUrl, direccion: "emitidos" | "recibidos"): URLSearchParams;
```
- `escribirEstado` omite los valores por defecto, regresa `pagina` a 1 salvo que el parche traiga `pagina`, y quita `pago` cuando `metodo` no es `PPD`.
- `usePeriodoGlobal(empresaId): [periodo, setPeriodo]` — resuelve con `resolverPeriodo`; si la URL no trae periodo válido, lo agrega con `router.replace`; al elegir uno lo guarda con `recordarPeriodo`.

- [ ] **Step 1: Pruebas que fallan** — `leerEstado` con URL vacía (todos los defaults), con valores válidos y con basura (`tipo=X`, `pagina=-3`, `por_pagina=999` → defaults); `escribirEstado` omite defaults, reinicia página, conserva `periodo`, quita `pago` si el método deja de ser PPD; `consultaApi` envía `direccion`, `periodo`, `dir` y `por_pagina` con los nombres de la API; el hook agrega `?periodo=` cuando falta y no lo hace si ya es válido; elegir periodo lo guarda para esa empresa y no para otra.
- [ ] **Step 2:** `npx vitest run lib/cfdi-url.test.ts hooks/usePeriodoGlobal.test.tsx` → FAIL.
- [ ] **Step 3:** Implementar (`useUrlParams` envuelve `useRouter`, `usePathname` y `useSearchParams`, y hace `router.replace(..., { scroll: false })`).
- [ ] **Step 4:** → PASS. **Step 5:** Commit `feat: estado del listado en la URL y periodo global`.

### Task 3: Tipos y hooks de datos

**Files:**
- Modify: `frontend/types/api.ts` (tipos nuevos al final del bloque de CFDI)
- Create: `frontend/hooks/useCfdis.ts`, `frontend/hooks/useCfdis.test.tsx`
- Create: `frontend/hooks/usePeriodos.ts`

**Interfaces (produce):**
- Tipos `CfdiColumna`, `CfdiColumnasResponse`, `CfdiFila` (`Record<string, string | number | boolean | null | string[]>`), `CfdiListadoResponse`, `CfdiTotalesBloque`, `CfdiResumenResponse`, con la forma exacta que devuelve `backend/cfdi_listado.py`.
- `useCfdiColumnas(empresaId, direccion, tipo)`, `useCfdiResumen(empresaId, direccion, estado)`, `useCfdiListado(empresaId, direccion, estado)` — la llave de la consulta incluye todos los parámetros; el listado usa `placeholderData: keepPreviousData` para no parpadear al paginar.
- `usePeriodos(empresaId)` → `{ periodos: string[] }` desde `GET /api/v1/empresas/{id}/periodos`.

- [ ] **Step 1: Pruebas que fallan** — con `apiFetch` simulado: la URL pedida lleva `direccion`, `periodo`, `tipo`, `pagina` y `por_pagina`; no se pide nada sin `empresaId`; al cambiar de página se conservan las filas anteriores mientras llegan las nuevas.
- [ ] **Step 2:** `npx vitest run hooks/useCfdis.test.tsx` → FAIL. **Step 3:** Implementar. **Step 4:** PASS.
- [ ] **Step 5:** Commit `feat: hooks de datos del listado de CFDI`.

### Task 4: Selector de periodo y periodo global en las otras pantallas

**Files:**
- Create: `frontend/components/shared/PeriodSelector.tsx`, `frontend/components/shared/PeriodSelector.test.tsx`
- Modify: `frontend/app/(app)/empresas/[empresaId]/{dashboard,conciliacion,cedula-iva}/page.tsx`
- Modify: `frontend/app/(app)/empresas/[empresaId]/dashboard/page.tsx` (score del periodo)
- Create: `frontend/lib/score.ts`, `frontend/lib/score.test.ts`
- Delete: `frontend/components/shared/PeriodFilter.tsx` (queda sin usos al terminar la Task 6)

**Interfaces:**
- `PeriodSelector({ value, onChange, periodosConDatos })` — selector (Radix `Select`) con "2026 - Septiembre"; ofrece los periodos con datos más el mes actual, sin repetir, del más reciente al más antiguo; incluye `value` aunque no esté en la lista.
- `scoreDelPeriodo(tendencia, periodo) → { score: number | null, delta: { puntos, contra } | null }` — el score es el del periodo elegido; el delta se calcula contra el periodo anterior de la tendencia; si el periodo no aparece en la tendencia, `score: null`.

- [ ] **Step 1: Pruebas que fallan** — el selector muestra las etiquetas largas, no repite el mes actual si ya viene en la lista, y llama a `onChange` con `YYYY-MM`; `scoreDelPeriodo` con periodo en medio de la tendencia (no el último), con el primero (sin delta) y ausente (`null`).
- [ ] **Step 2:** `npx vitest run components/shared/PeriodSelector.test.tsx lib/score.test.ts` → FAIL. **Step 3:** Implementar.
- [ ] **Step 4:** Reemplazar `useState("") + PeriodFilter` por `usePeriodoGlobal + PeriodSelector` en Dashboard, Conciliación y Cédula de IVA, y quitar el texto "Selecciona un periodo" (siempre hay uno). Actualizar sus pruebas existentes, si las hay.
- [ ] **Step 5:** `npx vitest run` completo → PASS. **Step 6:** Commit `feat: periodo global compartido y score del dashboard por periodo`.

### Task 5: Componentes del listado

**Files (cada uno con su `.test.tsx`):**
- Create: `frontend/components/cfdi/CfdiTabs.tsx` — pestañas `Ingreso, Egreso, Traslado, Nómina, Pago` con conteo; `role="tablist"`, la activa con `aria-selected`.
- Create: `frontend/components/cfdi/CfdiToolbar.tsx` — selector de periodo, búsqueda con espera de 300 ms, estado (Vigentes / Cancelados / Todos), método (Todos / PUE / PPD) y, solo con PPD, "Pendientes de pago / Pagadas / Todas".
- Create: `frontend/components/cfdi/CfdiTotales.tsx` — dos renglones (Periodo, Acumulado) con las cifras de `totales`; `null` → guion.
- Create: `frontend/components/cfdi/CfdiTabla.tsx` — columnas con `visible_por_defecto` del catálogo; formato por `tipo_dato` (`moneda`, `fecha`, `fecha_hora`, `booleano`, `lista`, resto texto); encabezado ordenable con `aria-sort`; pie con "1–30 de 507", página anterior/siguiente y tamaño de página 30/50/100; estados de carga (esqueleto), vacío ("No hay CFDI con estos filtros" + botón "Limpiar filtros") y error (mensaje + "Reintentar").

- [ ] **Step 1: Pruebas que fallan** — Tabs: conteos visibles, clic llama a `onChange("E")`. Toolbar: escribir en la búsqueda llama a `onChange` una sola vez tras 300 ms; el sub-filtro de PPD aparece solo con método PPD. Totales: cifras con formato de moneda; `null` muestra guion y nunca `$0.00`. Tabla: una fila con fecha ISO muestra `dd/mm/aaaa`; importe con formato; clic en un encabezado ordenable pide `orden` y alterna `dir`; columna no ordenable no es botón; vacío, error y carga; "Siguiente" deshabilitado en la última página.
- [ ] **Step 2:** `npx vitest run components/cfdi` → FAIL. **Step 3:** Implementar los cuatro componentes sin estado propio (reciben datos y callbacks).
- [ ] **Step 4:** PASS. **Step 5:** Commit `feat: componentes del listado de CFDI (pestañas, barra, totales, tabla)`.

### Task 6: Pantalla y páginas de Emitidos y Recibidos

**Files:**
- Create: `frontend/components/cfdi/CfdiPantalla.tsx`, `frontend/components/cfdi/CfdiPantalla.test.tsx`
- Modify: `frontend/app/(app)/empresas/[empresaId]/cfdi/emitidos/page.tsx` y `.../recibidos/page.tsx` (cada una renderiza `<CfdiPantalla direccion=... />` dentro de `Suspense`, que exige `useSearchParams`)
- Modify: `frontend/app/(app)/empresas/[empresaId]/cfdi/page.tsx` → redirige a `cfdi/emitidos` conservando el periodo.

**Comportamiento:**
- Lee el estado de la URL, pide columnas, resumen y listado, y pinta barra, pestañas, advertencias de anticipos (solo emitidos, con `role="alert"`), totales y tabla.
- Cambiar el tipo cambia las columnas (el catálogo depende del tipo) y regresa a la página 1.
- Un error del listado no oculta la barra ni las pestañas.

- [ ] **Step 1: Pruebas que fallan** — con la API simulada: abrir con `?tipo=E&metodo=PPD&pagina=2` pide exactamente esos parámetros (criterio de recarga); clic en otra pestaña escribe `tipo` y quita `pagina`; una advertencia de anticipo se muestra en emitidos y no en recibidos; empresa sin CFDI muestra el estado vacío y totales con guiones; error del listado muestra reintento y conserva la barra.
- [ ] **Step 2:** `npx vitest run components/cfdi/CfdiPantalla.test.tsx` → FAIL. **Step 3:** Implementar y conectar las páginas.
- [ ] **Step 4:** `npx tsc --noEmit && npm run lint` → limpios. **Step 5:** PASS.
- [ ] **Step 6:** Commit `feat: pantalla única de CFDI para emitidos y recibidos`.

### Task 7: Retiro de pantallas viejas, menú y correcciones chicas

**Files:**
- Delete: `frontend/app/(app)/empresas/[empresaId]/cfdi/nomina/page.tsx`; `frontend/components/cfdi/{EmitidosPanel,RecibidosPanel,NominaPanel,VisorSatPanel}.tsx` y sus pruebas; `useEmitidos`, `useRecibidos`, `useVisorSat`, `useNominaCfdi` de `hooks/useCfdi.ts` (y sus pruebas); los tipos que queden sin uso en `types/api.ts`.
- Modify: `frontend/components/layout/Sidebar.tsx` (+ prueba) — grupo "CFDIs" con **Emitidos** y **Recibidos**; el rol bajo el nombre sale de la sesión.
- Modify: `frontend/components/layout/Header.tsx` (+ prueba) — se quita la campana hasta M3.
- Modify: `frontend/components/ui/table.tsx` y `frontend/components/shared/DataTable.tsx` — el estilo de `TableHead` (11 px, negritas, mayúsculas) pasa a la base para que todas las tablas coincidan.
- Modify: `frontend/components/conciliacion/ParesTable.tsx`, `frontend/components/sat/{FielCard,DescargaSatCard}.tsx` — fechas con `formatearFecha`/`formatearFechaHora`.
- Modify: `frontend/lib/auth.ts`, `frontend/types/api.ts` — `rol` en `LoginResponse` y en `Session`.
- Modify: `backend/routers/auth.py` — el login devuelve `rol`. Test en `backend/tests/test_router_auth.py`; documentar en `docs/openapi.yaml`.
- Modify: pruebas e2e de `frontend/e2e/` que visiten las pantallas retiradas.

- [ ] **Step 1: Pruebas que fallan** — Sidebar: el grupo se llama "CFDIs", tiene solo Emitidos y Recibidos, y el rol se muestra como "Administrador" o "Contador" (sin rol en una sesión vieja no muestra la línea); Header: no hay botón de notificaciones; backend: el login de un usuario `admin` devuelve `rol: "admin"` y el de un contador `rol: "contador"`; formato: las fechas de Conciliación y de la tarjeta SAT salen `dd/mm/aaaa`.
- [ ] **Step 2:** `python -m pytest backend/tests/test_router_auth.py -q` y `npx vitest run` → FAIL en lo nuevo.
- [ ] **Step 3:** Implementar los cambios y eliminar lo retirado. `grep -rn "useVisorSat\|useNominaCfdi\|cfdi/nomina\|VisorSat" frontend --include=*.ts --include=*.tsx` no debe devolver nada.
- [ ] **Step 4:** Todo en verde. **Step 5:** Commits separados por tema: `feat: el login devuelve el rol del usuario`, `refactor: retirar las pantallas Visor SAT y Nómina`, `fix: fechas dd/mm/aaaa, encabezados uniformes y campana oculta`.

### Task 8: Verificación y PR

- [ ] `python -m pytest` completo con Postgres (`docker compose up -d db`) → sin saltadas.
- [ ] `cd frontend && npm test && npx tsc --noEmit && npm run lint` → verde.
- [ ] Levantar el stack local, cargar CFDI de prueba y recorrer con Playwright (`frontend/scripts/capturas.cjs`): periodo recordado entre pantallas, pestañas con conteo, recarga con filtros, paginación y orden. Guardar las capturas fuera del repositorio.
- [ ] Revisar la API contra la pantalla: los conteos de las pestañas y los totales de `Ingreso` coinciden con una consulta directa a la base.
- [ ] Actualizar el plan maestro: F3.2 hecha, y anotar la decisión sobre Nómina.
- [ ] Abrir el PR como borrador, con la lista de lo que **no** se verificó (comparación contra la plataforma de referencia, que requiere los CFDI reales del mismo día).
