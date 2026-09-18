# Rediseño visual del frontend — sistema de diseño fintech

## Contexto

El frontend (`docs/superpowers/specs/2026-07-10-reescritura-frontend-design.md`) se
construyó como núcleo funcional mínimo: shadcn "new-york" sin personalizar, tablas HTML
nativas sin estilo, sin sidebar, header de 2 links. Cumple su función pero no transmite
el nivel de pulido que se espera de un producto fiscal pagado.

El usuario pidió adoptar el lenguaje visual de un dashboard fintech de referencia
(sidebar de navegación con iconos, empresa/workspace switcher, header con búsqueda y
avatar, stat cards con variación %, tabla de datos con badges de estado y paginación) y
adaptarlo a FiscalCore. Se validó una vista previa estática del Dashboard
(mockup en Artifact, aprobado) antes de escribir esta spec — la paleta, tipografía y
estructura de esta spec son las que se ven en ese mockup.

Esta spec cubre **todo el frontend existente**, no solo el shell: las 6 páginas ya
construidas entre `feat/frontend-nextjs` (base), `feat/frontend-ingesta` (ingesta CFDI/
banco) y `feat/frontend-conciliacion-banco` (conciliación banco-CFDI) se consolidan
primero y luego se rediseñan juntas.

## Alcance

Rediseño visual de las páginas y componentes ya existentes. **No se agrega ninguna
funcionalidad nueva de negocio** — cada página sigue llamando a los mismos endpoints y
hooks de TanStack Query que ya tiene; solo cambia el markup/estilo y, en el caso del
Dashboard, la ruta que usa.

| Página | Ruta (nueva) | Endpoint(s) | Cambia lógica de datos |
|---|---|---|---|
| Login | `/login` | `POST /api/v1/auth/login` | No |
| Empresas | `/empresas` | `GET /api/v1/empresas`, `POST /api/v1/mis-empresas` | No |
| Dashboard | `/empresas/[empresaId]/dashboard` | `GET /api/v1/dashboard/{id}?periodo=` | Sí — se mueve de `/dashboard` con `<select>` a ruta con `empresaId` |
| Ingesta | `/empresas/[empresaId]/ingesta` | `POST .../cfdi/upload`, `POST .../banco/upload` | No |
| Conciliación | `/empresas/[empresaId]/conciliacion` | `GET .../conciliaciones/cierre/{periodo}`, `GET .../conciliaciones/accionables` | No (página nueva a integrar desde `feat/frontend-conciliacion-banco`) |
| Cédula de IVA | `/empresas/[empresaId]/cedula-iva` | `GET .../cedula-iva/{periodo}` | No |

**Explícitamente fuera de esta fase:**
- Cualquier página o endpoint sin UI hoy (movimientos, emitidos/recibidos, DIOT, ISR
  provisional, deducciones, SAT/FIEL, admin).
- Paginación server-side (ningún endpoint usado la soporta salvo `movimientos`, que no
  está en el alcance).
- Gráficas / sparklines de tendencia (el endpoint de dashboard trae `tendencia_score[]`
  pero no se visualiza como gráfica en esta fase — solo el delta puntual entre los dos
  últimos periodos, como en el mockup).
- Dark mode automático por preferencia de sistema operativo — el toggle es manual
  (click), persistido en `localStorage`.

## Fase 0 — Consolidación de ramas

Antes de tocar diseño, se unifica el código disperso en una sola rama de trabajo:

```
git checkout -b feat/frontend-rediseno feat/frontend-ingesta
git merge feat/frontend-conciliacion-banco
```

Conflictos esperados (ambas ramas parten del mismo commit base `7d3bb5d` y tocan lo
mismo):
- `frontend/components/empresas/EmpresaList.tsx` — ambas ramas no deberían tocar este
  archivo directamente (conciliación solo agrega un link nuevo en la página de
  empresas o en el detalle), pero si hay conflicto se resuelve conservando ambos: los
  links a ingesta/cédula-iva (de la rama base) y el link a conciliación (de la rama de
  conciliación).
- `frontend/types/api.ts` — cada rama agrega sus propios tipos (`IngestaResponse` vs
  `ResumenConciliacion`/`ParConciliacion`); se conservan ambos bloques.

Verificación de la fase: `npm run test` (dentro de `frontend/`) en verde antes de
avanzar a la Fase 1. Esto aísla cualquier fallo posterior como causado por el
rediseño, no por el merge.

## Sistema de diseño

### Paleta

Definida como variables CSS en `app/globals.css`, reemplazando las variables neutras
de shadcn por defecto. Acento de marca (índigo) separado de los colores semánticos
(severidad/estado) para no confundir "marca" con "estado del dato".

**Light** (`:root`):
```css
--background: 240 33% 98%;      /* #F6F6FB */
--foreground: 248 20% 11%;      /* #18172A */
--card: 0 0% 100%;
--card-foreground: 248 20% 11%;
--border: 245 30% 92%;          /* #E6E5F1 */
--muted-foreground: 247 8% 45%; /* #6C6B80 */
--primary: 243 75% 59%;         /* #4F46E5 */
--primary-foreground: 0 0% 100%;
--accent: 246 78% 95%;          /* #EEECFD */
--accent-foreground: 244 62% 47%;
--ring: 243 75% 59%;
```

**Dark** (`.dark` / `[data-theme="dark"]`):
```css
--background: 253 22% 8%;       /* #0F0E17 */
--foreground: 250 43% 95%;      /* #F1F0FA */
--card: 249 24% 14%;            /* #17162A */
--border: 247 22% 20%;          /* #2A2940 */
--muted-foreground: 250 13% 68%;
--primary: 243 82% 71%;         /* #7C74F2 */
--primary-foreground: 253 22% 8%;
--accent: 250 40% 20%;
--accent-foreground: 245 100% 82%;
--ring: 243 82% 71%;
```

**Colores semánticos** (no son tokens shadcn estándar; se agregan como variables propias
`--severity-critico`, `--severity-alto`, `--severity-medio`, `--severity-bajo`,
`--status-ok`, `--status-pendiente`, `--status-error`, cada una con su versión `-soft`
para el fondo del badge):
- Crítico: `#DC2626` / fondo `#FDECEC` (dark: `#F87171` / `#3A1B1F`)
- Alto: `#EA580C` / fondo `#FDEEE4` (dark: `#FB923C` / `#3A2716`)
- Medio: `#D97706` / fondo `#FDF3E1` (dark: `#FBBF24` / `#3A2E10`)
- Bajo: `#2563EB` / fondo `#EAF0FE` (dark: `#60A5FA` / `#182A47`)
- OK / resuelto / conciliado exacto: `#059669` / fondo `#E4F5EE` (dark: `#34D399` / `#12302A`)
- Pendiente / parcial: `#D97706` / fondo `#FDF3E1` (mismo que "medio", reutilizado)
- Error / cancelado / sin match: `#DC2626` / fondo `#FDECEC` (mismo que "crítico")

### Tipografía

Tres familias vía Google Fonts (`app/layout.tsx`, `next/font/google`):
- **Sora** (500/600/700/800) — headings, nav, botones, labels de UI.
- **Public Sans** (400/500/600/700) — texto de cuerpo, celdas de tabla, formularios.
- **IBM Plex Mono** (400/500/600) — montos, RFC, folios, códigos de riesgo, fechas en
  tablas (`font-variant-numeric: tabular-nums`).

Se retira la fuente por defecto de Next (Geist/Inter) del layout raíz.

### Componentes shadcn a instalar

```
npx shadcn@latest add badge avatar dropdown-menu sheet separator tooltip skeleton dialog
```

- `badge` → base de `StatusBadge`.
- `avatar` → header y sidebar.
- `dropdown-menu` → menú de acciones por fila (tabla de empresas) y menú de usuario.
- `sheet` → sidebar en mobile (`<768px`).
- `separator` → divisores en sidebar/header.
- `tooltip` → labels de iconos sin texto (búsqueda, notificaciones).
- `skeleton` → estados de carga de stat cards y tablas mientras TanStack Query hace
  fetch (hoy las páginas no muestran loading state consistente).
- `dialog` → formulario de alta de empresa se mueve de inline a modal (`EmpresaForm`
  dentro de `Dialog`, disparado por el botón "Nueva empresa").

**Explícitamente no se instalan** `tabs` y `command`: ninguna pantalla del alcance los
necesita (YAGNI). La paginación no tiene primitivo en shadcn — se construye a mano
dentro de `DataTable` (ver más abajo).

### Toggle de tema

Sin dependencia nueva (`next-themes` no se agrega). Un componente `ThemeToggle.tsx`
propio: lee/escribe `data-theme` en `<html>` y persiste la elección en
`localStorage` bajo la clave `fiscalcore-theme`, con fallback a `prefers-color-scheme`
solo en el primer render (sin valor guardado). Mismo mecanismo que el mockup validado.

## Shell de la app

### Estandarización de rutas

Todas las páginas empresa-scoped pasan a vivir bajo `/empresas/[empresaId]/...`,
incluyendo Dashboard (hoy en `/dashboard` con un `<select>` nativo desconectado de la
URL). Es un requisito del shell, no solo estético: el `Sidebar` necesita `empresaId`
en la ruta para saber qué item de nav resaltar y para que los links de navegación
tengan un destino determinístico.

- `app/(app)/dashboard/page.tsx` se **mueve** a
  `app/(app)/empresas/[empresaId]/dashboard/page.tsx`.
- El selector de empresa por `<select>` se elimina de la página; la empresa activa
  ahora viene de la URL (leída con `useParams()`), igual que en Ingesta/Cédula IVA.
- `app/(app)/empresas/page.tsx` (el listado) es la única página que NO cuelga de
  `[empresaId]` — sigue siendo la raíz para elegir/crear empresa.

### `EmpresaProvider` + `EmpresaSwitcher`

- `components/providers/EmpresaProvider.tsx`: contexto de React que guarda
  `{ empresaId, empresas }`. `empresaId` se deriva de la URL (`useParams()`) cuando
  existe; si el usuario navega a `/empresas` (sin id), el switcher usa la última
  empresa vista, leída de `localStorage` (`fiscalcore-last-empresa`) solo para
  pre-seleccionar en el switcher, nunca para redirigir automáticamente.
- `components/layout/EmpresaSwitcher.tsx`: botón en el sidebar que abre un
  `DropdownMenu` con la lista de empresas (de `useEmpresas()`, ya existente). Al
  elegir una, navega con `router.push` a la misma sub-ruta en la que ya está el
  usuario (ej. si está en `/empresas/A/ingesta` y cambia a empresa B, va a
  `/empresas/B/ingesta`); si no hay sub-ruta reconocible (viene de `/empresas` o
  `/login`), navega a `/empresas/{id}/dashboard`.

### `Sidebar.tsx`

`components/layout/Sidebar.tsx`, fijo a la izquierda en desktop (`w-64`), dentro de un
`Sheet` en mobile (`<768px`) disparado por un botón hamburguesa en el header.

Contenido, de arriba a abajo:
1. Logo/wordmark "FiscalCore" (ícono simple + texto, sin imagen externa).
2. `EmpresaSwitcher`.
3. Nav (`lucide-react`, ya está en `package.json`):
   - `LayoutGrid` — Dashboard → `/empresas/{id}/dashboard`
   - `Building2` — Empresas → `/empresas` (siempre habilitado, no depende de `empresaId`)
   - `Upload` — Ingesta → `/empresas/{id}/ingesta`
   - `GitBranch` — Conciliación → `/empresas/{id}/conciliacion`
   - `FileText` — Cédula de IVA → `/empresas/{id}/cedula-iva`
   - Los 4 items que dependen de `empresaId` se renderizan `disabled` (opacidad
     reducida, sin `href`) cuando no hay empresa seleccionada.
   - Item activo: fondo `--accent`, texto `--accent-foreground` (mismo patrón del
     mockup).
4. Al fondo: `ThemeToggle`, luego chip de usuario (avatar con iniciales + nombre +
   botón de logout que reusa la lógica ya existente en `AppHeader.tsx`).

### `Header.tsx`

`components/layout/Header.tsx`, sticky arriba del contenido:
- Breadcrumb generado a partir del pathname (`Panel > Dashboard`, `Panel > Cédula de
  IVA`, etc.) — mapeo estático de segmento de ruta a label, no requiere metadata nueva
  por página.
- Buscador (`Input` con ícono `Search`): filtra la lista de empresas ya cargada por
  `useEmpresas()` y navega al seleccionar una — no es decorativo ni pega a un
  endpoint nuevo de búsqueda.
- Ícono de notificaciones (`Bell`): placeholder visual sin badge de conteo real (no
  hay endpoint de notificaciones); se deja sin funcionalidad, documentado como tal
  en un comentario corto en el componente.
- `Avatar` con `DropdownMenu` (perfil deshabilitado por ahora / logout).

### `app/(app)/layout.tsx`

Se reescribe para componer el shell:

```tsx
<EmpresaProvider>
  <AuthGuard>
    <div className="flex min-h-screen">
      <Sidebar />
      <div className="flex-1 flex flex-col">
        <Header />
        <main className="flex-1 p-6">{children}</main>
      </div>
    </div>
  </AuthGuard>
</EmpresaProvider>
```

`AuthGuard.tsx` deja de renderizar `<AppHeader/>` — pasa a ser puramente una guardia de
sesión (valida token, llama `GET /api/v1/auth/me`, redirige a `/login` si falla) y
renderiza `children` sin envoltura visual. `components/layout/AppHeader.tsx` se
**elimina** (reemplazado por `Sidebar.tsx` + `Header.tsx`).

## Componentes compartidos nuevos

Todos en `components/shared/`.

### `StatCard.tsx`

```ts
type StatCardProps = {
  label: string
  value: string          // ya formateado por el caller (moneda, %, puntos)
  icon: LucideIcon
  tone?: "default" | "critico" | "alto" | "ok"   // color del ícono/fondo del ícono
  delta?: { value: string; direction: "up" | "down"; label: string }  // ej. "+4 pts", "vs. Jul 2026"
}
```
Sin lógica de fetch — recibe todo ya calculado desde la página. Igual estructura que
las 4 cards del mockup: label, ícono en esquina superior derecha, valor grande en
`IBM Plex Mono`, línea de delta opcional con flecha.

### `StatusBadge.tsx`

```ts
type StatusValue =
  | "critico" | "alto" | "medio" | "bajo"                 // severidad de riesgo
  | "pendiente" | "resuelto"                               // estado de riesgo
  | "exacto" | "parcial" | "sin_cfdi" | "sin_movimiento"    // tipo_match de conciliación
```
Mapa interno `StatusValue → { label, className }` usando los tokens semánticos de la
sección anterior. Valor no reconocido → variante `secondary` de shadcn (gris neutro)
como fallback, nunca un crash.

### `DataTable.tsx`

Genérico sobre `components/ui/table.tsx`, sin librería nueva (no se agrega
`@tanstack/react-table`, sería sobre-ingeniería para tablas de <50 filas sin paginación
server-side):

```ts
type Column<T> = {
  key: string
  header: string
  cell: (row: T) => React.ReactNode
  sortValue?: (row: T) => string | number   // si se omite, columna no es sortable
  searchable?: boolean                       // incluye esta columna en el filtro de texto
}

type DataTableProps<T> = {
  data: T[]
  columns: Column<T>[]
  getRowId: (row: T) => string
  selectable?: boolean       // muestra columna de checkboxes
  searchPlaceholder?: string // si hay >=1 columna searchable, muestra input de filtro
  pageSize?: number          // default 8
  emptyMessage: string
}
```
Estado interno (`useState`): página actual, columna+dirección de orden, texto de
búsqueda, filas seleccionadas. Todo client-side sobre el array `data` ya cargado por
el hook de la página — no dispara requests nuevos.

## Rediseño página por página

Ningún hook de datos (`useDashboard`, `useEmpresas`, `useConciliaciones`, `useCedulaIva`,
`useSubirCfdi`/`useSubirBanco`) cambia — solo el markup que consume sus resultados.

### Login (`app/login/page.tsx`)
Restyle ligero: `Card` centrada con la nueva paleta/tipografía, sin cambios de campos
ni de validación.

### Dashboard (`app/(app)/empresas/[empresaId]/dashboard/page.tsx`)
- Fila de 4 `StatCard`: Score fiscal actual (`score_actual`, delta = diferencia entre
  los dos últimos puntos de `tendencia_score[]` si hay ≥2, si no se omite el delta),
  Riesgos abiertos (`riesgos_abiertos.length`), Monto en riesgo
  (`resumen_riesgos.monto_total_en_riesgo` formateado MXN), % Conciliación bancaria
  (`indicadores.pct_conciliacion`).
- `ResumenRiesgos.tsx` se reduce a una segunda fila de 4 `StatCard` pequeñas
  (críticos/altos/medios/bajos), sin delta — conserva su test existente actualizado
  a la nueva salida visual en vez de eliminarse.
- `RiesgosTable.tsx` migra de `<table>` nativa a `DataTable<RiesgoAbierto>`:
  columnas Severidad (`StatusBadge`, sortable por rank crítico>alto>medio>bajo),
  Riesgo (`nombre`, sortable + searchable), Estado (`StatusBadge` — dato ya viaja en
  `RiesgoAbierto.estado` y hoy no se pinta en ningún lado), Monto afectado (sortable
  numérico), Descripción (searchable). `selectable={false}` (no hay acciones masivas
  sobre riesgos en esta fase). `emptyMessage="No hay riesgos abiertos en este
  periodo."`

### Empresas (`app/(app)/empresas/page.tsx`)
- `EmpresaForm` se mueve de inline a dentro de un `Dialog`, disparado por un botón
  "Nueva empresa" en el header de la página (patrón "Create Invoice" del mockup).
- `EmpresaList.tsx` migra a `DataTable<Empresa>`: columnas RFC (sortable,
  `font-mono`), Razón social (sortable + searchable), Régimen fiscal, y columna final
  de Acciones con `DropdownMenu` (trigger `MoreHorizontal`) agrupando los links a
  Ingesta/Cédula de IVA/Conciliación que hoy están sueltos. `selectable={false}`.
  `emptyMessage="Aún no hay empresas registradas."` (mismo texto que hoy).

### Ingesta (`app/(app)/empresas/[empresaId]/ingesta/page.tsx`)
No es una pantalla de tabla — se mantiene el layout de 2 formularios apilados, restyled:
`CfdiUploadForm`/`BancoUploadForm` pasan de `<form className="rounded-lg border p-4">`
a `Card`/`CardHeader`(`CardTitle`)/`CardContent`, mismos campos e inputs.
`IngestaResultado.tsx` se convierte en un bloque tipo alerta dentro de `Card`: ícono
`CheckCircle2` (verde) si `errores.length === 0`, `AlertTriangle` (ámbar) si hay
errores, reemplazando la lista `<ul className="text-amber-700">` actual.

### Conciliación (`app/(app)/empresas/[empresaId]/conciliacion/page.tsx`)
Página nueva a integrar desde `feat/frontend-conciliacion-banco` en la Fase 0, luego
rediseñada junto con el resto:
- `ResumenConciliacion.tsx` se reduce a mapear `resumen` (exacto/parcial/sin_cfdi/
  sin_movimiento/pct_conciliado) a un array de `StatCard`, sin delta (el endpoint no
  trae comparación histórica).
- `ParesTable.tsx` migra a `DataTable<ParConciliacion>`: columnas Tipo
  (`StatusBadge status={par.tipo_match}`, reutilizando el `TIPO_LABEL` ya existente en
  el componente), Fecha, Concepto (searchable), RFC detectado, Monto movimiento, Monto
  CFDI, Diferencia (numérica, clase condicional rojo/verde). `selectable={true}` (sin
  acciones masivas todavía, mismo patrón visual que Riesgos). `emptyMessage` igual al
  actual.

### Cédula de IVA (`app/(app)/empresas/[empresaId]/cedula-iva/page.tsx`)
**No se usa `DataTable`** aquí — son 10 filas fijas clave-valor sin necesidad real de
orden/filtro/paginación; forzarlo sería sobre-ingeniería. Se envuelve en
`Card`/`CardHeader("Cédula de IVA")`/`CardContent`, y la tabla interna pasa de
`<table>` nativa a los primitivos shadcn `Table/TableBody/TableRow/TableCell` (mismo
array `filas`, mismo `formatMoney`).

## Impacto en tests Vitest

**Se rompen y se reescriben junto con su componente:**
- `components/layout/AppHeader.test.tsx` → se elimina (componente eliminado). Se crean
  `components/layout/Sidebar.test.tsx` (5 items de nav, estado disabled/enabled según
  `empresaId`) y `components/layout/Header.test.tsx` (breadcrumb, buscador, avatar/
  logout).
- `components/dashboard/RiesgosTable.test.tsx` → la firma pública
  `RiesgosTable({riesgos})` no cambia, se actualiza el assert de empty-state a la
  nueva estructura y se agrega un caso para la columna Estado.
- `components/empresas/EmpresaList.test.tsx` → los asserts que buscan
  `getByRole("link", { name: "Ingesta" })` deben primero abrir el `DropdownMenu`
  (`userEvent.click` sobre el trigger) antes de poder hacer el assert.
- `components/cedula-iva/CedulaIvaTable.test.tsx` → los `getByText(...)` sobre labels y
  montos no cambian (mismo contenido textual), solo el contenedor.
- `components/ingesta/IngestaResultado.test.tsx` → se actualiza el assert de clase CSS
  de la lista de errores al nuevo esquema de íconos.

**No se rompen (se corren tal cual tras la Fase 0):** `AuthGuard.test.tsx`,
`app/login/page.test.tsx`, `app/page.test.tsx`, todos los hooks (`useDashboard`,
`useConciliaciones`, etc.), `lib/api-client.test.ts`, `lib/auth.test.ts`,
`lib/query-client.test.tsx`.

**Tests nuevos:** `StatCard.test.tsx`, `StatusBadge.test.tsx` (cubre al menos un valor
de cada familia + fallback), `DataTable.test.tsx` (empty state, orden asc/desc,
filtro de texto sobre las columnas marcadas `searchable`, paginación con fixture
>`pageSize` filas, selección de checkbox), `EmpresaSwitcher.test.tsx`,
`EmpresaProvider.test.tsx` (persistencia en `localStorage`).

## Verificación

- **Fase 0**: `npm run test` en verde inmediatamente después del merge.
- **Fase 1 (sistema de diseño)**: `npm run test` (no debería romper nada, son tokens
  CSS + dependencias nuevas); `npm run build` como smoke test de que los componentes
  shadcn recién instalados compilan.
- **Fase 2 (shell)**: `npm run test -- Sidebar Header AuthGuard EmpresaProvider`; con
  backend local levantado (`./dev.sh` o `python -m uvicorn backend.main_api:app
  --reload --port 8000`) y `npm run dev` en `frontend/`, login manual y verificar
  sidebar con 5 items, breadcrumb dinámico, logout.
- **Fase 3 (componentes compartidos)**: `npm run test -- StatCard StatusBadge
  DataTable` antes de integrarlos en ninguna página.
- **Fase 4 (páginas)**: por cada página migrada, `npm run test -- <Componente>` +
  smoke visual manual (crear empresa de prueba, subir CFDI/estado de cuenta de
  ejemplo, revisar Dashboard/Conciliación/Cédula IVA con datos reales).
- **Cierre**: `npm run test` completo en verde + `npm run build` (catch de rutas
  rotas por el movimiento de `dashboard/page.tsx`) + recorrido manual end-to-end
  (login → empresa → ingesta → dashboard → conciliación → cédula IVA → logout) en
  light/dark y desktop/mobile (sidebar como `Sheet`).

## Fuera de alcance / decisiones pendientes

- Merge de esta rama de rediseño a `main` — no ocurre en esta fase; requiere decisión
  aparte sobre plataforma de deploy (pendiente desde la spec de julio).
- Gráfica real de `tendencia_score[]` (solo se usa el delta puntual).
- Notificaciones funcionales (el ícono del header queda como placeholder visual).
- Acciones masivas sobre filas seleccionadas en `DataTable` (el checkbox de selección
  se deja listo visualmente pero sin acción asociada, salvo que el usuario pida
  agregarla).

