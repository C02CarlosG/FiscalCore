# Rediseño visual del frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rediseñar visualmente el frontend Next.js de FiscalCore (6 páginas + shell)
al estilo de un dashboard fintech (sidebar, stat cards, tablas con badges y
paginación), sin agregar funcionalidad de negocio nueva — mismos endpoints, mismos
hooks de TanStack Query, solo cambia el markup/estilo y la ruta del Dashboard.

**Architecture:** Se consolidan primero las 3 ramas de frontend dispersas
(`feat/frontend-ingesta` + `feat/frontend-conciliacion-banco`) en una rama nueva. Se
establece un sistema de diseño (tokens CSS + tipografía + primitivos shadcn) y un
shell de app (Sidebar/Header/EmpresaProvider) reutilizable, luego 3 componentes
compartidos con lógica genérica (`StatCard`, `StatusBadge`, `DataTable`), y por
último se migra cada página existente a ese sistema.

**Tech Stack:** Next.js 14 (App Router) + TypeScript, Tailwind CSS + shadcn/ui
("new-york"), TanStack Query, lucide-react, Vitest + React Testing Library.

**Spec:** `docs/superpowers/specs/2026-09-16-frontend-rediseno-design.md`

## Global Constraints

- Todo el trabajo ocurre dentro de `frontend/` (rutas de este plan son relativas a
  `frontend/` salvo que se indique lo contrario).
- Ningún hook de datos existente (`useEmpresas`, `useDashboard`, `useCedulaIva`,
  `useSubirCfdi`/`useSubirBanco`, `useConciliacionResumen`/
  `useConciliacionesAccionables`) cambia su firma ni su query key.
- No se agrega `@tanstack/react-table`, `next-themes` ni `@radix-ui/react-checkbox`
  (YAGNI — ver spec, sección "Componentes shadcn a instalar").
- Dark mode se activa con la clase `.dark` en `<html>` (ya configurado en
  `tailwind.config.ts` como `darkMode: ["class"]`) — no con un atributo
  `data-theme`.
- Todo commit sigue Conventional Commits (`feat:`, `fix:`, `chore:`, `docs:`),
  imperativo y acotado, con el pie `Co-Authored-By: Claude Sonnet 5
  <noreply@anthropic.com>` según la config de este repo.
- Verificar cada tarea con `npm run test -- <patrón>` (dentro de `frontend/`) antes
  de continuar a la siguiente.

---

## Fase 0 — Consolidación de ramas

### Task 1: Crear rama de rediseño y mergear conciliación

**Files:**
- Modify (merge, resuelve conflicto): `frontend/components/empresas/EmpresaList.tsx`
- Modify (merge, resuelve conflicto): `frontend/types/api.ts`

**Interfaces:**
- Produces: rama local `feat/frontend-rediseno`, con `git worktree` en
  `.worktrees/feat-frontend-rediseno` (mismo patrón que el worktree existente de
  `feat/frontend-ingesta`), conteniendo el código combinado de ingesta +
  conciliación que todas las tareas siguientes modifican.

- [ ] **Step 1: Crear la rama y el worktree**

```bash
cd /c/Users/carlo/Project_Development/FiscalCore
git worktree add .worktrees/feat-frontend-rediseno -b feat/frontend-rediseno feat/frontend-ingesta
cd .worktrees/feat-frontend-rediseno
```

- [ ] **Step 2: Mergear conciliación**

```bash
git merge feat/frontend-conciliacion-banco
```

Esto falla con conflictos exactamente en dos archivos (ya verificado con
`git merge-tree`): `frontend/components/empresas/EmpresaList.tsx` y
`frontend/types/api.ts`.

- [ ] **Step 3: Resolver el conflicto en `EmpresaList.tsx`**

El conflicto queda en el bloque de links dentro de la última `<td>`. Edita el
archivo para que la celda de acciones tenga los 3 links (Ingesta, de la rama
`feat/frontend-ingesta`; Cédula de IVA, común a ambas; Conciliación, de la rama de
conciliación), en ese orden:

```tsx
            <td className="py-2 space-x-3">
              <Link
                className="text-blue-600 hover:underline"
                href={`/empresas/${empresa.id}/ingesta`}
              >
                Ingesta
              </Link>
              <Link
                className="text-blue-600 hover:underline"
                href={`/empresas/${empresa.id}/cedula-iva`}
              >
                Cédula de IVA
              </Link>
              <Link
                className="text-blue-600 hover:underline"
                href={`/empresas/${empresa.id}/conciliacion`}
              >
                Conciliación
              </Link>
            </td>
```

- [ ] **Step 4: Resolver el conflicto en `types/api.ts`**

Ambas ramas agregan interfaces distintas al final del archivo — se conservan las
dos, sin resolver a favor de ninguna. El archivo debe terminar así (después de
`export interface CedulaIva { ... }`):

```ts
export interface IngestaResponse {
  mensaje: string;
  registros_procesados: number;
  errores: string[];
  periodo: string;
}

export interface ConciliacionResumen {
  total: number;
  exacto: number;
  parcial: number;
  sin_cfdi: number;
  sin_movimiento: number;
  pct_conciliado: number;
}

export interface ParConciliacion {
  id: string;
  tipo_match: "sin_cfdi" | "parcial";
  monto_movimiento: number | null;
  monto_cfdi: number | null;
  diferencia: number | null;
  porcentaje_match: number | null;
  periodo: string;
  movimiento_id: string | null;
  mov_fecha: string | null;
  concepto: string | null;
  mov_monto: number | null;
  mov_tipo: string | null;
  rfc_detectado: string | null;
}

export interface ConciliacionesAccionables {
  total: number;
  pares: ParConciliacion[];
}
```

- [ ] **Step 5: Marcar como resueltos y completar el merge**

```bash
git add frontend/components/empresas/EmpresaList.tsx frontend/types/api.ts
git commit --no-edit
```

- [ ] **Step 6: Instalar dependencias y verificar que la suite pasa completa**

```bash
cd frontend
npm install
npm run test
```

Expected: todos los tests pasan (incluyendo `ParesTable.test.tsx`,
`useConciliaciones.test.tsx` que llegan del merge). Si algo falla aquí, es un
problema del merge — resuélvelo antes de seguir; no continúes a la Fase 1 con la
suite en rojo.

- [ ] **Step 7: Commit (si Step 5 no lo generó ya como merge commit)**

El merge commit de Step 5 ya registra este trabajo — no se necesita un commit
adicional salvo que Step 6 haya requerido cambios de código, en cuyo caso:

```bash
git add -A
git commit -m "fix: resolver incompatibilidades post-merge de frontend-conciliacion-banco

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Fase 1 — Sistema de diseño

### Task 2: Tokens de color, radios y tipografía

**Files:**
- Modify: `frontend/app/globals.css`
- Modify: `frontend/tailwind.config.ts`
- Modify: `frontend/app/layout.tsx`

**Interfaces:**
- Produces: clases Tailwind `bg-severity-critico`, `bg-severity-critico-soft`,
  `text-severity-critico` (y análogas para `alto`/`medio`/`bajo`), `bg-status-ok`,
  `bg-status-ok-soft`, `text-status-ok` (y análogas para `pendiente`/`error`) —
  usadas por `StatusBadge` en la Fase 3. Variables de fuente CSS `--font-sora`,
  `--font-public-sans`, `--font-mono` aplicadas globalmente.

- [ ] **Step 1: Reemplazar los tokens de color en `globals.css`**

Reemplaza el contenido completo del archivo:

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 240 33% 98%;
    --foreground: 248 20% 11%;
    --card: 0 0% 100%;
    --card-foreground: 248 20% 11%;
    --popover: 0 0% 100%;
    --popover-foreground: 248 20% 11%;
    --primary: 243 75% 59%;
    --primary-foreground: 0 0% 100%;
    --secondary: 245 30% 95%;
    --secondary-foreground: 248 20% 11%;
    --muted: 245 30% 95%;
    --muted-foreground: 247 8% 45%;
    --accent: 246 78% 95%;
    --accent-foreground: 244 62% 47%;
    --destructive: 0 72% 51%;
    --destructive-foreground: 0 0% 98%;
    --border: 245 30% 92%;
    --input: 245 30% 88%;
    --ring: 243 75% 59%;
    --radius: 0.625rem;

    --severity-critico: #DC2626;
    --severity-critico-soft: #FDECEC;
    --severity-alto: #EA580C;
    --severity-alto-soft: #FDEEE4;
    --severity-medio: #D97706;
    --severity-medio-soft: #FDF3E1;
    --severity-bajo: #2563EB;
    --severity-bajo-soft: #EAF0FE;
    --status-ok: #059669;
    --status-ok-soft: #E4F5EE;
    --status-pendiente: #D97706;
    --status-pendiente-soft: #FDF3E1;
    --status-error: #DC2626;
    --status-error-soft: #FDECEC;
  }

  .dark {
    --background: 253 22% 8%;
    --foreground: 250 43% 95%;
    --card: 249 24% 14%;
    --card-foreground: 250 43% 95%;
    --popover: 249 24% 14%;
    --popover-foreground: 250 43% 95%;
    --primary: 243 82% 71%;
    --primary-foreground: 253 22% 8%;
    --secondary: 247 22% 18%;
    --secondary-foreground: 250 43% 95%;
    --muted: 247 22% 18%;
    --muted-foreground: 250 13% 68%;
    --accent: 250 40% 20%;
    --accent-foreground: 245 100% 82%;
    --destructive: 0 63% 60%;
    --destructive-foreground: 0 0% 98%;
    --border: 247 22% 20%;
    --input: 247 22% 22%;
    --ring: 243 82% 71%;

    --severity-critico: #F87171;
    --severity-critico-soft: #3A1B1F;
    --severity-alto: #FB923C;
    --severity-alto-soft: #3A2716;
    --severity-medio: #FBBF24;
    --severity-medio-soft: #3A2E10;
    --severity-bajo: #60A5FA;
    --severity-bajo-soft: #182A47;
    --status-ok: #34D399;
    --status-ok-soft: #12302A;
    --status-pendiente: #FBBF24;
    --status-pendiente-soft: #3A2E10;
    --status-error: #F87171;
    --status-error-soft: #3A1B1F;
  }
}

@layer base {
  * {
    @apply border-border;
  }
  body {
    @apply bg-background text-foreground;
  }
}
```

- [ ] **Step 2: Extender `tailwind.config.ts` con los colores semánticos**

En `theme.extend.colors`, agrega dos entradas nuevas después de `card` (deja el
resto del archivo igual):

```ts
        severity: {
          critico: {
            DEFAULT: "var(--severity-critico)",
            soft: "var(--severity-critico-soft)",
          },
          alto: {
            DEFAULT: "var(--severity-alto)",
            soft: "var(--severity-alto-soft)",
          },
          medio: {
            DEFAULT: "var(--severity-medio)",
            soft: "var(--severity-medio-soft)",
          },
          bajo: {
            DEFAULT: "var(--severity-bajo)",
            soft: "var(--severity-bajo-soft)",
          },
        },
        status: {
          ok: { DEFAULT: "var(--status-ok)", soft: "var(--status-ok-soft)" },
          pendiente: {
            DEFAULT: "var(--status-pendiente)",
            soft: "var(--status-pendiente-soft)",
          },
          error: {
            DEFAULT: "var(--status-error)",
            soft: "var(--status-error-soft)",
          },
        },
```

También agrega, dentro de `theme.extend` (fuera de `colors`), la familia
tipográfica:

```ts
      fontFamily: {
        sans: ["var(--font-public-sans)", "system-ui", "sans-serif"],
        display: ["var(--font-sora)", "var(--font-public-sans)", "system-ui"],
        mono: ["var(--font-mono)", "ui-monospace", "monospace"],
      },
```

- [ ] **Step 3: Configurar las fuentes en `app/layout.tsx`**

Reemplaza el archivo completo:

```tsx
import type { Metadata } from "next";
import { Sora, Public_Sans, IBM_Plex_Mono } from "next/font/google";
import "./globals.css";
import { QueryProvider } from "@/components/providers/QueryProvider";

const sora = Sora({
  subsets: ["latin"],
  weight: ["500", "600", "700", "800"],
  variable: "--font-sora",
});
const publicSans = Public_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700"],
  variable: "--font-public-sans",
});
const plexMono = IBM_Plex_Mono({
  subsets: ["latin"],
  weight: ["400", "500", "600"],
  variable: "--font-mono",
});

export const metadata: Metadata = {
  title: "FiscalCore",
  description: "CFDI Intelligence",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="es" className={`${sora.variable} ${publicSans.variable} ${plexMono.variable}`}>
      <body className="font-sans antialiased">
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 4: Verificar que compila y los tests siguen en verde**

```bash
npm run build
npm run test
```

Expected: build sin errores, suite completa en verde (este paso solo toca tokens
CSS y fuentes, ningún componente cambia su markup todavía).

- [ ] **Step 5: Commit**

```bash
git add app/globals.css tailwind.config.ts app/layout.tsx
git commit -m "feat: nueva paleta de marca y tipografía (Sora/Public Sans/IBM Plex Mono)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 3: Instalar primitivos shadcn nuevos

**Files:**
- Create (vía CLI): `frontend/components/ui/badge.tsx`
- Create (vía CLI): `frontend/components/ui/avatar.tsx`
- Create (vía CLI): `frontend/components/ui/dropdown-menu.tsx`
- Create (vía CLI): `frontend/components/ui/sheet.tsx`
- Create (vía CLI): `frontend/components/ui/separator.tsx`
- Create (vía CLI): `frontend/components/ui/tooltip.tsx`
- Create (vía CLI): `frontend/components/ui/skeleton.tsx`
- Create (vía CLI): `frontend/components/ui/dialog.tsx`

**Interfaces:**
- Produces: `Badge` (usado por `StatusBadge`, Task 11), `Avatar`/`AvatarFallback`
  (Sidebar/Header, Tasks 7-8), `DropdownMenu*` (EmpresaSwitcher Task 6, Header Task
  8, acciones de `EmpresaList` Task 16), `Sheet*` (Sidebar mobile, Task 7),
  `Dialog*` (alta de empresa, Task 16).

- [ ] **Step 1: Ejecutar el CLI de shadcn**

Todas las dependencias Radix que estos componentes requieren
(`@radix-ui/react-avatar`, `-dialog`, `-dropdown-menu`, `-separator`, `-tooltip`)
ya están en `package.json` — el CLI solo genera los wrappers en `components/ui/`.

```bash
npx shadcn@latest add badge avatar dropdown-menu sheet separator tooltip skeleton dialog
```

Si el CLI pregunta por sobrescribir `components.json` o algún archivo existente,
responde que no — ya está configurado (`style: "new-york"`, `baseColor: "neutral"`).

- [ ] **Step 2: Verificar que los 8 archivos se crearon**

```bash
ls components/ui/badge.tsx components/ui/avatar.tsx components/ui/dropdown-menu.tsx \
   components/ui/sheet.tsx components/ui/separator.tsx components/ui/tooltip.tsx \
   components/ui/skeleton.tsx components/ui/dialog.tsx
```

Expected: los 8 paths existen, sin error "No such file".

- [ ] **Step 3: Verificar que compila**

```bash
npm run build
```

Expected: build sin errores (estos componentes no se usan todavía en ninguna
página, así que un fallo aquí es un problema de instalación, no de integración).

- [ ] **Step 4: Commit**

```bash
git add components/ui/badge.tsx components/ui/avatar.tsx components/ui/dropdown-menu.tsx \
        components/ui/sheet.tsx components/ui/separator.tsx components/ui/tooltip.tsx \
        components/ui/skeleton.tsx components/ui/dialog.tsx components.json package.json package-lock.json
git commit -m "chore: instalar primitivos shadcn (badge, avatar, dropdown-menu, sheet, separator, tooltip, skeleton, dialog)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 4: `ThemeToggle`

**Files:**
- Create: `frontend/components/shared/ThemeToggle.tsx`
- Create: `frontend/components/shared/ThemeToggle.test.tsx`

**Interfaces:**
- Produces: `ThemeToggle()` — componente sin props, usado por `Sidebar` (Task 7).
  Lee/escribe la clase `dark` en `document.documentElement` y persiste la
  elección en `localStorage` bajo la clave `"fiscalcore-theme"`.

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, expect, it, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ThemeToggle } from "./ThemeToggle";

describe("ThemeToggle", () => {
  beforeEach(() => {
    document.documentElement.classList.remove("dark");
    window.localStorage.clear();
  });

  it("shows 'Modo claro' by default and toggles to dark on click", async () => {
    const user = userEvent.setup();
    render(<ThemeToggle />);

    expect(screen.getByText("Modo claro")).toBeInTheDocument();

    await user.click(screen.getByRole("button"));

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByText("Modo oscuro")).toBeInTheDocument();
    expect(window.localStorage.getItem("fiscalcore-theme")).toBe("dark");
  });

  it("reads a previously saved dark preference on mount", () => {
    window.localStorage.setItem("fiscalcore-theme", "dark");
    render(<ThemeToggle />);

    expect(document.documentElement.classList.contains("dark")).toBe(true);
    expect(screen.getByText("Modo oscuro")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Correr el test y confirmar que falla**

Run: `npm run test -- ThemeToggle`
Expected: FAIL — `Cannot find module './ThemeToggle'`.

- [ ] **Step 3: Implementar `ThemeToggle`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";

const STORAGE_KEY = "fiscalcore-theme";

function readStoredTheme(): "light" | "dark" | null {
  try {
    const value = window.localStorage.getItem(STORAGE_KEY);
    return value === "dark" || value === "light" ? value : null;
  } catch {
    return null;
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<"light" | "dark">("light");

  useEffect(() => {
    const stored = readStoredTheme();
    const initial =
      stored ??
      (window.matchMedia("(prefers-color-scheme: dark)").matches
        ? "dark"
        : "light");
    setTheme(initial);
    document.documentElement.classList.toggle("dark", initial === "dark");
  }, []);

  function toggle() {
    const next = theme === "dark" ? "light" : "dark";
    setTheme(next);
    document.documentElement.classList.toggle("dark", next === "dark");
    try {
      window.localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // localStorage no disponible (modo privado); el toggle sigue funcionando en memoria.
    }
  }

  return (
    <button
      type="button"
      onClick={toggle}
      className="flex items-center gap-2 rounded-lg border border-border px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground"
    >
      {theme === "dark" ? (
        <Moon className="h-3.5 w-3.5" />
      ) : (
        <Sun className="h-3.5 w-3.5" />
      )}
      {theme === "dark" ? "Modo oscuro" : "Modo claro"}
    </button>
  );
}
```

- [ ] **Step 4: Correr el test y confirmar que pasa**

Run: `npm run test -- ThemeToggle`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add components/shared/ThemeToggle.tsx components/shared/ThemeToggle.test.tsx
git commit -m "feat: agregar ThemeToggle con persistencia en localStorage

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Fase 2 — Shell de la app

### Task 5: `EmpresaProvider`

**Files:**
- Create: `frontend/components/providers/EmpresaProvider.tsx`
- Create: `frontend/components/providers/EmpresaProvider.test.tsx`

**Interfaces:**
- Consumes: `useEmpresas()` de `frontend/hooks/useEmpresas.ts` (ya existente,
  devuelve `UseQueryResult<Empresa[]>`).
- Produces: `EmpresaProvider({ children })`, `useEmpresaContext()` retornando
  `{ empresaId: string | null, empresas: Empresa[]; setLastEmpresaId: (id: string) => void }`.
  `empresaId` se deriva de `useParams()` (`params.empresaId` si la ruta lo trae).
  Usado por `EmpresaSwitcher` (Task 6) y `Sidebar` (Task 7).

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EmpresaProvider, useEmpresaContext } from "./EmpresaProvider";
import type { Empresa } from "@/types/api";

const mockParams = vi.fn();
vi.mock("next/navigation", () => ({
  useParams: () => mockParams(),
}));

vi.mock("@/hooks/useEmpresas", () => ({
  useEmpresas: () => ({
    data: [
      { id: "e1", rfc: "AAA010101AAA", razon_social: "Acme SA de CV" } as Empresa,
    ],
  }),
}));

function Consumer() {
  const { empresaId, empresas } = useEmpresaContext();
  return (
    <p>
      {empresaId ?? "sin-empresa"} / {empresas.length} empresas
    </p>
  );
}

function renderWithClient(ui: React.ReactNode) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("EmpresaProvider", () => {
  beforeEach(() => {
    mockParams.mockReturnValue({});
    window.localStorage.clear();
  });

  it("expone empresaId=null y la lista de empresas cuando la URL no trae empresaId", () => {
    renderWithClient(
      <EmpresaProvider>
        <Consumer />
      </EmpresaProvider>,
    );
    expect(screen.getByText("sin-empresa / 1 empresas")).toBeInTheDocument();
  });

  it("expone el empresaId de la URL cuando existe", () => {
    mockParams.mockReturnValue({ empresaId: "e1" });
    renderWithClient(
      <EmpresaProvider>
        <Consumer />
      </EmpresaProvider>,
    );
    expect(screen.getByText("e1 / 1 empresas")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Correr el test y confirmar que falla**

Run: `npm run test -- EmpresaProvider`
Expected: FAIL — `Cannot find module './EmpresaProvider'`.

- [ ] **Step 3: Implementar `EmpresaProvider`**

```tsx
"use client";

import { createContext, useContext, useEffect, useMemo } from "react";
import { useParams } from "next/navigation";
import { useEmpresas } from "@/hooks/useEmpresas";
import type { Empresa } from "@/types/api";

const LAST_EMPRESA_KEY = "fiscalcore-last-empresa";

interface EmpresaContextValue {
  empresaId: string | null;
  empresas: Empresa[];
  setLastEmpresaId: (id: string) => void;
}

const EmpresaContext = createContext<EmpresaContextValue | null>(null);

export function EmpresaProvider({ children }: { children: React.ReactNode }) {
  const params = useParams<{ empresaId?: string }>();
  const { data: empresas } = useEmpresas();
  const empresaId = params.empresaId ?? null;

  useEffect(() => {
    if (!empresaId) return;
    try {
      window.localStorage.setItem(LAST_EMPRESA_KEY, empresaId);
    } catch {
      // localStorage no disponible; el switcher simplemente no pre-selecciona.
    }
  }, [empresaId]);

  function setLastEmpresaId(id: string) {
    try {
      window.localStorage.setItem(LAST_EMPRESA_KEY, id);
    } catch {
      // no-op
    }
  }

  const value = useMemo(
    () => ({ empresaId, empresas: empresas ?? [], setLastEmpresaId }),
    [empresaId, empresas],
  );

  return (
    <EmpresaContext.Provider value={value}>{children}</EmpresaContext.Provider>
  );
}

export function useEmpresaContext(): EmpresaContextValue {
  const ctx = useContext(EmpresaContext);
  if (!ctx) {
    throw new Error("useEmpresaContext debe usarse dentro de <EmpresaProvider>");
  }
  return ctx;
}

export function readLastEmpresaId(): string | null {
  try {
    return window.localStorage.getItem(LAST_EMPRESA_KEY);
  } catch {
    return null;
  }
}
```

- [ ] **Step 4: Correr el test y confirmar que pasa**

Run: `npm run test -- EmpresaProvider`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add components/providers/EmpresaProvider.tsx components/providers/EmpresaProvider.test.tsx
git commit -m "feat: agregar EmpresaProvider para exponer la empresa activa desde la URL

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 6: `EmpresaSwitcher`

**Files:**
- Create: `frontend/components/layout/EmpresaSwitcher.tsx`
- Create: `frontend/components/layout/EmpresaSwitcher.test.tsx`

**Interfaces:**
- Consumes: `useEmpresaContext()` (Task 5) para `{ empresaId, empresas,
  setLastEmpresaId }`; `Empresa` de `@/types/api`.
- Produces: `EmpresaSwitcher()` — sin props, usado por `Sidebar` (Task 7). Al elegir
  una empresa navega manteniendo la sub-ruta actual, o a `/empresas/{id}/dashboard`
  si la ruta actual no tiene una sub-ruta reconocible.

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmpresaSwitcher } from "./EmpresaSwitcher";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import type { Empresa } from "@/types/api";

const pushMock = vi.fn();
const mockPathname = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => mockPathname(),
}));

vi.mock("@/components/providers/EmpresaProvider", () => ({
  useEmpresaContext: vi.fn(),
}));

const empresaA = { id: "e1", rfc: "AAA010101AAA", razon_social: "Acme SA de CV" } as Empresa;
const empresaB = { id: "e2", rfc: "BBB020202BBB", razon_social: "Beta SA de CV" } as Empresa;

describe("EmpresaSwitcher", () => {
  beforeEach(() => {
    pushMock.mockClear();
    vi.mocked(useEmpresaContext).mockReturnValue({
      empresaId: "e1",
      empresas: [empresaA, empresaB],
      setLastEmpresaId: vi.fn(),
    });
  });

  it("navega a la misma sub-ruta al cambiar de empresa", async () => {
    mockPathname.mockReturnValue("/empresas/e1/ingesta");
    const user = userEvent.setup();
    render(<EmpresaSwitcher />);

    await user.click(screen.getByRole("button"));
    await user.click(screen.getByRole("menuitem", { name: /Beta SA de CV/ }));

    expect(pushMock).toHaveBeenCalledWith("/empresas/e2/ingesta");
  });

  it("navega a dashboard cuando no hay sub-ruta reconocible", async () => {
    mockPathname.mockReturnValue("/empresas");
    const user = userEvent.setup();
    render(<EmpresaSwitcher />);

    await user.click(screen.getByRole("button"));
    await user.click(screen.getByRole("menuitem", { name: /Beta SA de CV/ }));

    expect(pushMock).toHaveBeenCalledWith("/empresas/e2/dashboard");
  });
});
```

- [ ] **Step 2: Correr el test y confirmar que falla**

Run: `npm run test -- EmpresaSwitcher`
Expected: FAIL — `Cannot find module './EmpresaSwitcher'`.

- [ ] **Step 3: Implementar `EmpresaSwitcher`**

```tsx
"use client";

import { useRouter, usePathname } from "next/navigation";
import { Building2, ChevronsUpDown } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";

const SUB_RUTAS = ["dashboard", "ingesta", "conciliacion", "cedula-iva"];

function resolverDestino(pathname: string, empresaId: string, nuevoId: string): string {
  const segmentos = pathname.split("/").filter(Boolean);
  const idx = segmentos.indexOf(empresaId);
  const subRuta = idx >= 0 ? segmentos[idx + 1] : undefined;
  const destino = subRuta && SUB_RUTAS.includes(subRuta) ? subRuta : "dashboard";
  return `/empresas/${nuevoId}/${destino}`;
}

export function EmpresaSwitcher() {
  const router = useRouter();
  const pathname = usePathname();
  const { empresaId, empresas, setLastEmpresaId } = useEmpresaContext();

  const activa = empresas.find((e) => e.id === empresaId);

  function elegir(id: string) {
    setLastEmpresaId(id);
    router.push(resolverDestino(pathname, empresaId ?? "", id));
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button
          type="button"
          className="flex w-full items-center gap-2.5 rounded-xl border border-border bg-card px-2.5 py-2 text-left hover:bg-accent"
        >
          <span className="flex h-8 w-8 flex-none items-center justify-center rounded-lg bg-accent text-xs font-bold text-accent-foreground">
            {activa ? activa.razon_social.slice(0, 2).toUpperCase() : <Building2 className="h-4 w-4" />}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-sm font-semibold">
              {activa ? activa.razon_social : "Selecciona una empresa"}
            </span>
            {activa && (
              <span className="block truncate font-mono text-xs text-muted-foreground">
                {activa.rfc}
              </span>
            )}
          </span>
          <ChevronsUpDown className="h-4 w-4 flex-none text-muted-foreground" />
        </button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="start" className="w-64">
        {empresas.map((empresa) => (
          <DropdownMenuItem key={empresa.id} onSelect={() => elegir(empresa.id)}>
            <span className="truncate">{empresa.razon_social}</span>
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
```

- [ ] **Step 4: Correr el test y confirmar que pasa**

Run: `npm run test -- EmpresaSwitcher`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add components/layout/EmpresaSwitcher.tsx components/layout/EmpresaSwitcher.test.tsx
git commit -m "feat: agregar EmpresaSwitcher al shell

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 7: `Sidebar`

**Files:**
- Create: `frontend/components/layout/Sidebar.tsx`
- Create: `frontend/components/layout/Sidebar.test.tsx`

**Interfaces:**
- Consumes: `useEmpresaContext()` (Task 5), `EmpresaSwitcher` (Task 6),
  `ThemeToggle` (Task 4), `loadSession`/`clearSession` de `@/lib/auth` (ya
  existentes), `Sheet`/`SheetContent` de `components/ui/sheet.tsx` (Task 3).
- Produces: `Sidebar({ mobileOpen, onMobileOpenChange }: { mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void })` — usado por
  `app/(app)/layout.tsx` (Task 9), que posee el estado `mobileOpen`.

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "./Sidebar";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import { saveSession, getToken } from "@/lib/auth";
import type { LoginResponse } from "@/types/api";

const replaceMock = vi.fn();
const mockPathname = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => mockPathname(),
}));

vi.mock("@/components/providers/EmpresaProvider", () => ({
  useEmpresaContext: vi.fn(),
}));

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "ana@example.com",
  nombre: "Ana Torres",
  empresas: [],
};

describe("Sidebar", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    mockPathname.mockReturnValue("/empresas/e1/dashboard");
    window.localStorage.clear();
    vi.mocked(useEmpresaContext).mockReturnValue({
      empresaId: "e1",
      empresas: [],
      setLastEmpresaId: vi.fn(),
    });
  });

  it("renders the 5 nav items with links scoped to the active empresa", () => {
    render(<Sidebar mobileOpen={false} onMobileOpenChange={() => {}} />);

    expect(screen.getByRole("link", { name: /Dashboard/ })).toHaveAttribute(
      "href",
      "/empresas/e1/dashboard",
    );
    expect(screen.getByRole("link", { name: /Empresas/ })).toHaveAttribute(
      "href",
      "/empresas",
    );
    expect(screen.getByRole("link", { name: /Ingesta/ })).toHaveAttribute(
      "href",
      "/empresas/e1/ingesta",
    );
    expect(screen.getByRole("link", { name: /Conciliación/ })).toHaveAttribute(
      "href",
      "/empresas/e1/conciliacion",
    );
    expect(screen.getByRole("link", { name: /Cédula de IVA/ })).toHaveAttribute(
      "href",
      "/empresas/e1/cedula-iva",
    );
  });

  it("disables empresa-scoped items when there is no empresa selected", () => {
    vi.mocked(useEmpresaContext).mockReturnValue({
      empresaId: null,
      empresas: [],
      setLastEmpresaId: vi.fn(),
    });
    render(<Sidebar mobileOpen={false} onMobileOpenChange={() => {}} />);

    expect(
      screen.queryByRole("link", { name: /Dashboard/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Empresas/ })).toBeInTheDocument();
  });

  it("clears the session and redirects to /login on logout", async () => {
    saveSession(loginResponse);
    const user = userEvent.setup();
    render(<Sidebar mobileOpen={false} onMobileOpenChange={() => {}} />);

    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

    expect(getToken()).toBeNull();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });
});
```

- [ ] **Step 2: Correr el test y confirmar que falla**

Run: `npm run test -- components/layout/Sidebar`
Expected: FAIL — `Cannot find module './Sidebar'`.

- [ ] **Step 3: Implementar `Sidebar`**

```tsx
"use client";

import Link from "next/link";
import { useRouter, usePathname } from "next/navigation";
import {
  Building2,
  FileText,
  GitBranch,
  LayoutGrid,
  LogOut,
  Upload,
} from "lucide-react";
import { Sheet, SheetContent } from "@/components/ui/sheet";
import { EmpresaSwitcher } from "@/components/layout/EmpresaSwitcher";
import { ThemeToggle } from "@/components/shared/ThemeToggle";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import { clearSession, loadSession } from "@/lib/auth";

const NAV_ITEMS = [
  { slug: "dashboard", label: "Dashboard", icon: LayoutGrid, requiresEmpresa: true },
  { slug: "empresas", label: "Empresas", icon: Building2, requiresEmpresa: false },
  { slug: "ingesta", label: "Ingesta", icon: Upload, requiresEmpresa: true },
  { slug: "conciliacion", label: "Conciliación", icon: GitBranch, requiresEmpresa: true },
  { slug: "cedula-iva", label: "Cédula de IVA", icon: FileText, requiresEmpresa: true },
] as const;

function isActive(pathname: string, slug: string): boolean {
  if (slug === "empresas") return pathname === "/empresas";
  return pathname.includes(`/${slug}`);
}

function SidebarBody() {
  const router = useRouter();
  const pathname = usePathname();
  const { empresaId } = useEmpresaContext();
  const session = typeof window !== "undefined" ? loadSession() : null;

  function handleLogout() {
    clearSession();
    router.replace("/login");
  }

  const iniciales = (session?.nombre ?? session?.email ?? "?")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <div className="flex h-full flex-col gap-5 p-3.5">
      <div className="flex items-center gap-2 px-1.5 py-1 font-display text-[17px] font-bold">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg bg-primary text-primary-foreground">
          <FileText className="h-4 w-4" />
        </span>
        FiscalCore
      </div>

      <EmpresaSwitcher />

      <nav className="flex flex-1 flex-col gap-0.5">
        {NAV_ITEMS.map((item) => {
          const Icon = item.icon;
          const disabled = item.requiresEmpresa && !empresaId;
          const href = item.slug === "empresas" ? "/empresas" : `/empresas/${empresaId}/${item.slug}`;
          const active = isActive(pathname, item.slug);

          if (disabled) {
            return (
              <span
                key={item.slug}
                className="flex cursor-not-allowed items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium text-muted-foreground/40"
              >
                <Icon className="h-4 w-4" />
                {item.label}
              </span>
            );
          }

          return (
            <Link
              key={item.slug}
              href={href}
              className={`flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
              }`}
            >
              <Icon className="h-4 w-4" />
              {item.label}
            </Link>
          );
        })}
      </nav>

      <div className="flex flex-col gap-2.5 border-t border-border pt-3.5">
        <ThemeToggle />
        <div className="flex items-center gap-2.5 px-1">
          <span className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/60 text-xs font-bold text-primary-foreground">
            {iniciales}
          </span>
          <span className="min-w-0 flex-1">
            <span className="block truncate text-xs font-semibold">
              {session?.nombre ?? session?.email ?? "Usuario"}
            </span>
            <span className="block truncate text-[11px] text-muted-foreground">
              Contador
            </span>
          </span>
          <button
            type="button"
            onClick={handleLogout}
            aria-label="Cerrar sesión"
            className="flex-none text-muted-foreground hover:text-destructive"
          >
            <LogOut className="h-4 w-4" />
          </button>
        </div>
      </div>
    </div>
  );
}

interface SidebarProps {
  mobileOpen: boolean;
  onMobileOpenChange: (open: boolean) => void;
}

export function Sidebar({ mobileOpen, onMobileOpenChange }: SidebarProps) {
  return (
    <>
      <aside className="hidden w-64 flex-none border-r border-border bg-card lg:flex">
        <SidebarBody />
      </aside>
      <Sheet open={mobileOpen} onOpenChange={onMobileOpenChange}>
        <SheetContent side="left" className="w-64 p-0">
          <SidebarBody />
        </SheetContent>
      </Sheet>
    </>
  );
}
```

Nota: el `aria-label="Cerrar sesión"` en el botón satisface
`getByRole("button", { name: "Cerrar sesión" })` del test aunque el botón
solo tenga el ícono `LogOut` como contenido visible.

- [ ] **Step 4: Correr el test y confirmar que pasa**

Run: `npm run test -- components/layout/Sidebar`
Expected: PASS (3 tests). Nota: `Sidebar` renderiza `SidebarBody` dos veces
(el `<aside>` de desktop y el `Sheet` de mobile), pero como los 3 tests montan
el componente con `mobileOpen={false}`, el contenido del `Sheet` (basado en
`@radix-ui/react-dialog`) no llega a montarse en el DOM — solo existe la copia
del `<aside>`, así que cada `getByRole` encuentra una única coincidencia.

- [ ] **Step 5: Commit**

```bash
git add components/layout/Sidebar.tsx components/layout/Sidebar.test.tsx
git commit -m "feat: agregar Sidebar con navegación mapeada a empresa activa

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 8: `Header`

**Files:**
- Create: `frontend/components/layout/Header.tsx`
- Create: `frontend/components/layout/Header.test.tsx`

**Interfaces:**
- Consumes: `useEmpresaContext()` (Task 5), `loadSession`/`clearSession` de
  `@/lib/auth`.
- Produces: `Header({ onMenuClick }: { onMenuClick: () => void })` — usado por
  `app/(app)/layout.tsx` (Task 9); `onMenuClick` abre el `Sheet` del `Sidebar` en
  mobile.

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Header } from "./Header";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import { saveSession, getToken } from "@/lib/auth";
import type { Empresa, LoginResponse } from "@/types/api";

const replaceMock = vi.fn();
const pushMock = vi.fn();
const mockPathname = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: pushMock }),
  usePathname: () => mockPathname(),
}));

vi.mock("@/components/providers/EmpresaProvider", () => ({
  useEmpresaContext: vi.fn(),
}));

const empresaA = { id: "e1", rfc: "AAA010101AAA", razon_social: "Acme SA de CV" } as Empresa;

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "ana@example.com",
  nombre: "Ana Torres",
  empresas: [],
};

describe("Header", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    pushMock.mockClear();
    mockPathname.mockReturnValue("/empresas/e1/dashboard");
    window.localStorage.clear();
    vi.mocked(useEmpresaContext).mockReturnValue({
      empresaId: "e1",
      empresas: [empresaA],
      setLastEmpresaId: vi.fn(),
    });
  });

  it("shows the breadcrumb label for the current route", () => {
    render(<Header onMenuClick={() => {}} />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("navigates to the matched empresa on search", async () => {
    const user = userEvent.setup();
    render(<Header onMenuClick={() => {}} />);

    await user.type(screen.getByPlaceholderText(/Buscar empresa/), "Acme");
    await user.click(screen.getByRole("option", { name: /Acme SA de CV/ }));

    expect(pushMock).toHaveBeenCalledWith("/empresas/e1/dashboard");
  });

  it("clears the session and redirects to /login on logout", async () => {
    saveSession(loginResponse);
    const user = userEvent.setup();
    render(<Header onMenuClick={() => {}} />);

    await user.click(screen.getByRole("button", { name: /Ana Torres/ }));
    await user.click(screen.getByRole("menuitem", { name: "Cerrar sesión" }));

    expect(getToken()).toBeNull();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });
});
```

- [ ] **Step 2: Correr el test y confirmar que falla**

Run: `npm run test -- components/layout/Header`
Expected: FAIL — `Cannot find module './Header'`.

- [ ] **Step 3: Implementar `Header`**

```tsx
"use client";

import { useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import { Bell, Menu, Search } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import { clearSession, loadSession } from "@/lib/auth";

const LABELS: Record<string, string> = {
  dashboard: "Dashboard",
  empresas: "Empresas",
  ingesta: "Ingesta",
  conciliacion: "Conciliación",
  "cedula-iva": "Cédula de IVA",
};

function breadcrumbLabel(pathname: string): string {
  const segmentos = pathname.split("/").filter(Boolean);
  for (let i = segmentos.length - 1; i >= 0; i -= 1) {
    if (LABELS[segmentos[i]]) return LABELS[segmentos[i]];
  }
  return "Panel";
}

export function Header({ onMenuClick }: { onMenuClick: () => void }) {
  const router = useRouter();
  const pathname = usePathname();
  const { empresas } = useEmpresaContext();
  const [query, setQuery] = useState("");
  const session = typeof window !== "undefined" ? loadSession() : null;

  function handleLogout() {
    clearSession();
    router.replace("/login");
  }

  const resultados =
    query.trim().length > 0
      ? empresas.filter(
          (e) =>
            e.razon_social.toLowerCase().includes(query.toLowerCase()) ||
            e.rfc.toLowerCase().includes(query.toLowerCase()),
        )
      : [];

  const iniciales = (session?.nombre ?? session?.email ?? "?")
    .split(" ")
    .map((p) => p[0])
    .slice(0, 2)
    .join("")
    .toUpperCase();

  return (
    <header className="flex h-14 flex-none items-center gap-4 border-b border-border bg-card px-4 lg:px-6">
      <button
        type="button"
        onClick={onMenuClick}
        aria-label="Abrir menú"
        className="text-muted-foreground lg:hidden"
      >
        <Menu className="h-5 w-5" />
      </button>

      <div className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <span>Panel</span>
        <span>/</span>
        <span className="font-medium text-foreground">
          {breadcrumbLabel(pathname)}
        </span>
      </div>

      <div className="relative ml-auto hidden max-w-xs flex-1 sm:block">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
        <input
          type="text"
          placeholder="Buscar empresa, RFC…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          className="w-full rounded-lg border border-border bg-background py-1.5 pl-8 pr-3 text-sm outline-none focus:ring-1 focus:ring-ring"
        />
        {resultados.length > 0 && (
          <ul
            role="listbox"
            className="absolute left-0 right-0 top-full z-20 mt-1 rounded-lg border border-border bg-popover p-1 shadow-md"
          >
            {resultados.map((empresa) => (
              <li key={empresa.id} role="presentation">
                <button
                  type="button"
                  role="option"
                  aria-selected={false}
                  onClick={() => {
                    setQuery("");
                    router.push(`/empresas/${empresa.id}/dashboard`);
                  }}
                  className="w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-accent"
                >
                  {empresa.razon_social}
                </button>
              </li>
            ))}
          </ul>
        )}
      </div>

      <button
        type="button"
        aria-label="Notificaciones"
        className="relative text-muted-foreground hover:text-foreground"
      >
        {/* Sin badge de conteo: no hay endpoint de notificaciones todavía. */}
        <Bell className="h-4.5 w-4.5" />
      </button>

      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={session?.nombre ?? "Cuenta"}
            className="flex h-8 w-8 flex-none items-center justify-center rounded-full bg-gradient-to-br from-primary to-primary/60 text-xs font-bold text-primary-foreground"
          >
            {iniciales}
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem disabled>Perfil</DropdownMenuItem>
          <DropdownMenuItem onSelect={handleLogout}>
            Cerrar sesión
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    </header>
  );
}
```

- [ ] **Step 4: Correr el test y confirmar que pasa**

Run: `npm run test -- components/layout/Header`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add components/layout/Header.tsx components/layout/Header.test.tsx
git commit -m "feat: agregar Header con breadcrumb, buscador de empresas y logout

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 9: Componer el shell en `app/(app)/layout.tsx` y simplificar `AuthGuard`

**Files:**
- Modify: `frontend/components/auth/AuthGuard.tsx`
- Modify: `frontend/components/auth/AuthGuard.test.tsx`
- Modify: `frontend/app/(app)/layout.tsx`
- Delete: `frontend/components/layout/AppHeader.tsx`
- Delete: `frontend/components/layout/AppHeader.test.tsx`

**Interfaces:**
- Consumes: `Sidebar` (Task 7), `Header` (Task 8), `EmpresaProvider` (Task 5).
- Produces: `AuthGuard` deja de importar/renderizar `AppHeader` — pasa a ser
  puramente una guardia de sesión que renderiza `children` sin envoltura visual.

- [ ] **Step 1: Actualizar `AuthGuard.test.tsx`**

El único cambio es que ya no se puede asumir que `AuthGuard` monta un `<header>`
propio; los 3 tests existentes (redirige sin sesión, renderiza children con
sesión válida, limpia sesión en 401) ya no dependen de eso — no requieren cambios
de aserciones, solo se quita cualquier mock de `AppHeader` si existiera (no lo
hay en el archivo actual). Verifica que el archivo queda igual al leído en la
exploración previa; si es idéntico, no hay nada que tocar en este Step.

- [ ] **Step 2: Simplificar `AuthGuard.tsx`**

```tsx
"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { getToken, clearSession } from "@/lib/auth";
import { apiFetch, ApiError } from "@/lib/api-client";

type GuardStatus = "checking" | "authorized" | "unauthorized";

export function AuthGuard({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [status, setStatus] = useState<GuardStatus>("checking");

  useEffect(() => {
    let active = true;

    async function verify() {
      const token = getToken();
      if (!token) {
        setStatus("unauthorized");
        router.replace("/login");
        return;
      }
      try {
        await apiFetch("/api/v1/auth/me");
        if (active) setStatus("authorized");
      } catch (err) {
        if (active) {
          if (err instanceof ApiError && err.status === 401) {
            clearSession();
          }
          setStatus("unauthorized");
          router.replace("/login");
        }
      }
    }

    verify();
    return () => {
      active = false;
    };
  }, [router]);

  if (status !== "authorized") {
    return null;
  }

  return <>{children}</>;
}
```

(Único cambio real respecto al archivo actual: se quita el `import` y el
`<AppHeader />` — el resto de la lógica de verificación de sesión es idéntica.)

- [ ] **Step 3: Eliminar `AppHeader`**

```bash
git rm components/layout/AppHeader.tsx components/layout/AppHeader.test.tsx
```

- [ ] **Step 4: Reescribir `app/(app)/layout.tsx`**

```tsx
"use client";

import { useState } from "react";
import { AuthGuard } from "@/components/auth/AuthGuard";
import { EmpresaProvider } from "@/components/providers/EmpresaProvider";
import { Sidebar } from "@/components/layout/Sidebar";
import { Header } from "@/components/layout/Header";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <EmpresaProvider>
      <AuthGuard>
        <div className="flex h-screen overflow-hidden bg-background">
          <Sidebar mobileOpen={mobileOpen} onMobileOpenChange={setMobileOpen} />
          <div className="flex min-w-0 flex-1 flex-col">
            <Header onMenuClick={() => setMobileOpen(true)} />
            <main className="flex-1 overflow-y-auto p-4 lg:p-6">
              {children}
            </main>
          </div>
        </div>
      </AuthGuard>
    </EmpresaProvider>
  );
}
```

`EmpresaProvider` envuelve a `AuthGuard` (no al revés) porque `useEmpresas()`
dentro de `EmpresaProvider` ya maneja su propio estado de carga/error vía
TanStack Query — no depende de que `AuthGuard` ya haya confirmado la sesión, y
así el `Sidebar`/`Header` (que llaman `useEmpresaContext()`) nunca se montan sin
el provider encima, incluso durante el "checking" inicial del guard (en ese
estado `AuthGuard` retorna `null`, así que `Sidebar`/`Header` tampoco se montan
todavía — el orden de anidamiento no cambia el comportamiento visible, solo
importa que `EmpresaProvider` esté siempre presente cuando `children` se
renderiza).

- [ ] **Step 5: Verificar**

```bash
npm run test
npm run build
```

Expected: suite completa en verde, build sin errores. Con el backend local
levantado (`./dev.sh` desde la raíz del repo) y `npm run dev` en `frontend/`,
inicia sesión manualmente y confirma: el sidebar aparece con los 5 items, el
botón hamburguesa (en viewport angosto, `<1024px`) abre el `Sheet`, el
breadcrumb cambia según la ruta, y "Cerrar sesión" (desde el sidebar o desde el
avatar del header) redirige a `/login`.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: componer Sidebar+Header en el layout protegido, simplificar AuthGuard

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 10: Mover Dashboard a `/empresas/[empresaId]/dashboard`

**Files:**
- Delete: `frontend/app/(app)/dashboard/page.tsx`
- Create: `frontend/app/(app)/empresas/[empresaId]/dashboard/page.tsx`
- Create: `frontend/app/(app)/empresas/[empresaId]/dashboard/page.test.tsx`

**Interfaces:**
- Consumes: `useDashboard(empresaId, periodo)` (ya existente, sin cambios de
  firma), `ResumenRiesgos`/`RiesgosTable` (sin cambios en este task — se
  rediseñan en la Fase 4, Task 15).

Este task solo mueve la ruta y quita el `<select>` de empresa (ahora redundante
porque el `Sidebar`/`EmpresaSwitcher` ya resuelven la empresa activa vía URL). El
contenido visual de la página no cambia todavía.

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import DashboardPage from "./page";
import { useDashboard } from "@/hooks/useDashboard";

vi.mock("next/navigation", () => ({
  useParams: () => ({ empresaId: "e1" }),
}));

vi.mock("@/hooks/useDashboard", () => ({
  useDashboard: vi.fn(),
}));

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.mocked(useDashboard).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any);
  });

  it("does not render a company selector", () => {
    render(<DashboardPage />);
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("calls useDashboard with the empresaId from the URL", () => {
    render(<DashboardPage />);
    expect(useDashboard).toHaveBeenCalledWith("e1", "");
  });
});
```

- [ ] **Step 2: Correr el test y confirmar que falla**

Run: `npm run test -- app/\(app\)/empresas/\[empresaId\]/dashboard`
Expected: FAIL — el archivo `page.tsx` en esa ruta todavía no existe.

- [ ] **Step 3: Eliminar la página vieja y crear la nueva**

```bash
git rm "app/(app)/dashboard/page.tsx"
mkdir -p "app/(app)/empresas/[empresaId]/dashboard"
```

Contenido de `app/(app)/empresas/[empresaId]/dashboard/page.tsx`:

```tsx
"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useDashboard } from "@/hooks/useDashboard";
import { ResumenRiesgos } from "@/components/dashboard/ResumenRiesgos";
import { RiesgosTable } from "@/components/dashboard/RiesgosTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function DashboardPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");

  const dashboard = useDashboard(params.empresaId, periodo);

  return (
    <main className="mx-auto max-w-4xl space-y-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      <div className="space-y-2">
        <Label htmlFor="periodo">Periodo (YYYY-MM)</Label>
        <Input
          id="periodo"
          placeholder="2026-07"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
        />
      </div>

      {dashboard.isLoading && <p>Cargando dashboard...</p>}
      {dashboard.isError && (
        <ErrorState
          message="No se pudo cargar el dashboard."
          onRetry={() => dashboard.refetch()}
        />
      )}
      {dashboard.data && (
        <>
          <ResumenRiesgos resumen={dashboard.data.resumen_riesgos} />
          <RiesgosTable riesgos={dashboard.data.riesgos_abiertos} />
        </>
      )}
    </main>
  );
}
```

Nota: se quita el `max-w-4xl space-y-6 p-6` del `<main>` original a favor de
`mx-auto max-w-4xl space-y-6` — el padding `p-6` ya lo aporta el `<main>` del
layout (Task 9), duplicarlo dejaría doble espaciado.

- [ ] **Step 4: Correr el test y confirmar que pasa**

Run: `npm run test -- app/\(app\)/empresas/\[empresaId\]/dashboard`
Expected: PASS (2 tests).

- [ ] **Step 5: Correr la suite completa y build**

```bash
npm run test
npm run build
```

Expected: verde completo, sin rutas rotas.

- [ ] **Step 6: Commit**

```bash
git add -A
git commit -m "feat: mover Dashboard a /empresas/[empresaId]/dashboard

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Fase 3 — Componentes compartidos

### Task 11: `StatusBadge`

**Files:**
- Create: `frontend/components/shared/StatusBadge.tsx`
- Create: `frontend/components/shared/StatusBadge.test.tsx`

**Interfaces:**
- Consumes: `Badge` de `components/ui/badge.tsx` (Task 3); clases Tailwind
  `severity-*`/`status-*` (Task 2).
- Produces: `StatusBadge({ status }: { status: string })` — usado por
  `RiesgosTable` (Task 15) y `ParesTable` (Task 18). Acepta cualquier string
  (no un union literal estricto) porque el campo `estado` de riesgos viene del
  backend como texto libre; valores no reconocidos caen en un badge neutro con
  el texto capitalizado, nunca un crash.

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each([
    ["critico", "Crítico"],
    ["alto", "Alto"],
    ["medio", "Medio"],
    ["bajo", "Bajo"],
    ["abierto", "Pendiente"],
    ["resuelto", "Resuelto"],
    ["exacto", "Exacto"],
    ["parcial", "Match parcial"],
    ["sin_cfdi", "Sin CFDI"],
    ["sin_movimiento", "Sin movimiento"],
  ])("renders the label for status %s", (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("falls back to a capitalized neutral badge for an unknown status", () => {
    render(<StatusBadge status="desconocido" />);
    expect(screen.getByText("Desconocido")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Correr el test y confirmar que falla**

Run: `npm run test -- StatusBadge`
Expected: FAIL — `Cannot find module './StatusBadge'`.

- [ ] **Step 3: Implementar `StatusBadge`**

```tsx
import { Badge } from "@/components/ui/badge";

const STATUS_MAP: Record<string, { label: string; className: string }> = {
  critico: { label: "Crítico", className: "bg-severity-critico-soft text-severity-critico" },
  alto: { label: "Alto", className: "bg-severity-alto-soft text-severity-alto" },
  medio: { label: "Medio", className: "bg-severity-medio-soft text-severity-medio" },
  bajo: { label: "Bajo", className: "bg-severity-bajo-soft text-severity-bajo" },
  abierto: { label: "Pendiente", className: "bg-status-pendiente-soft text-status-pendiente" },
  pendiente: { label: "Pendiente", className: "bg-status-pendiente-soft text-status-pendiente" },
  resuelto: { label: "Resuelto", className: "bg-status-ok-soft text-status-ok" },
  cerrado: { label: "Resuelto", className: "bg-status-ok-soft text-status-ok" },
  exacto: { label: "Exacto", className: "bg-status-ok-soft text-status-ok" },
  parcial: { label: "Match parcial", className: "bg-status-pendiente-soft text-status-pendiente" },
  sin_cfdi: { label: "Sin CFDI", className: "bg-status-error-soft text-status-error" },
  sin_movimiento: { label: "Sin movimiento", className: "bg-status-error-soft text-status-error" },
};

function capitalizar(texto: string): string {
  return texto.charAt(0).toUpperCase() + texto.slice(1);
}

export function StatusBadge({ status }: { status: string }) {
  const entry = STATUS_MAP[status];

  if (!entry) {
    return (
      <Badge variant="secondary" className="font-medium">
        {capitalizar(status.replace(/_/g, " "))}
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className={`border-transparent font-medium ${entry.className}`}
    >
      {entry.label}
    </Badge>
  );
}
```

- [ ] **Step 4: Correr el test y confirmar que pasa**

Run: `npm run test -- StatusBadge`
Expected: PASS (11 tests).

- [ ] **Step 5: Commit**

```bash
git add components/shared/StatusBadge.tsx components/shared/StatusBadge.test.tsx
git commit -m "feat: agregar StatusBadge para severidad/estado/tipo_match

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 12: `StatCard`

**Files:**
- Create: `frontend/components/shared/StatCard.tsx`
- Create: `frontend/components/shared/StatCard.test.tsx`

**Interfaces:**
- Consumes: `Card`/`CardContent` de `components/ui/card.tsx` (ya existente).
- Produces: `StatCard({ label, value, icon, tone, delta }: StatCardProps)` —
  usado por Dashboard (Task 15) y Conciliación (Task 18).

```ts
export type StatCardProps = {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: "default" | "critico" | "alto" | "ok";
  delta?: { value: string; direction: "up" | "down"; label: string };
};
```

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrendingUp } from "lucide-react";
import { StatCard } from "./StatCard";

describe("StatCard", () => {
  it("renders the label and value", () => {
    render(<StatCard label="Score fiscal actual" value="78/100" icon={TrendingUp} />);
    expect(screen.getByText("Score fiscal actual")).toBeInTheDocument();
    expect(screen.getByText("78/100")).toBeInTheDocument();
  });

  it("renders an upward delta in the ok color", () => {
    render(
      <StatCard
        label="Score fiscal actual"
        value="78/100"
        icon={TrendingUp}
        delta={{ value: "+4 pts", direction: "up", label: "vs. Jul 2026" }}
      />,
    );
    const delta = screen.getByText("+4 pts");
    expect(delta).toBeInTheDocument();
    expect(delta.className).toContain("status-ok");
    expect(screen.getByText("vs. Jul 2026")).toBeInTheDocument();
  });

  it("renders a downward delta in the error color", () => {
    render(
      <StatCard
        label="Monto en riesgo"
        value="$284,320"
        icon={TrendingUp}
        delta={{ value: "+8.2%", direction: "down", label: "vs. Jul 2026" }}
      />,
    );
    expect(screen.getByText("+8.2%").className).toContain("status-error");
  });

  it("renders without a delta section when none is provided", () => {
    render(<StatCard label="Riesgos abiertos" value="12" icon={TrendingUp} />);
    expect(screen.queryByText(/vs\./)).not.toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Correr el test y confirmar que falla**

Run: `npm run test -- StatCard`
Expected: FAIL — `Cannot find module './StatCard'`.

- [ ] **Step 3: Implementar `StatCard`**

```tsx
import type { LucideIcon } from "lucide-react";
import { ArrowDown, ArrowUp } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";

export type StatCardProps = {
  label: string;
  value: string;
  icon: LucideIcon;
  tone?: "default" | "critico" | "alto" | "ok";
  delta?: { value: string; direction: "up" | "down"; label: string };
};

const TONE_CLASSES: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "bg-severity-bajo-soft text-severity-bajo",
  critico: "bg-severity-critico-soft text-severity-critico",
  alto: "bg-severity-alto-soft text-severity-alto",
  ok: "bg-status-ok-soft text-status-ok",
};

export function StatCard({ label, value, icon: Icon, tone = "default", delta }: StatCardProps) {
  return (
    <Card>
      <CardContent className="p-4.5">
        <div className="mb-2.5 flex items-center justify-between">
          <span className="text-xs font-semibold text-muted-foreground">{label}</span>
          <span className={`flex h-7 w-7 items-center justify-center rounded-lg ${TONE_CLASSES[tone]}`}>
            <Icon className="h-3.5 w-3.5" />
          </span>
        </div>
        <p className="font-mono text-2xl font-semibold tracking-tight">{value}</p>
        {delta && (
          <p
            className={`mt-1.5 flex items-center gap-1 text-xs font-semibold ${
              delta.direction === "up" ? "text-status-ok" : "text-status-error"
            }`}
          >
            {delta.direction === "up" ? (
              <ArrowUp className="h-3 w-3" />
            ) : (
              <ArrowDown className="h-3 w-3" />
            )}
            {delta.value}
            <span className="font-normal text-muted-foreground">{delta.label}</span>
          </p>
        )}
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 4: Correr el test y confirmar que pasa**

Run: `npm run test -- StatCard`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add components/shared/StatCard.tsx components/shared/StatCard.test.tsx
git commit -m "feat: agregar StatCard

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 13: `DataTable`

**Files:**
- Create: `frontend/components/shared/DataTable.tsx`
- Create: `frontend/components/shared/DataTable.test.tsx`

**Interfaces:**
- Consumes: `Table`/`TableHeader`/`TableBody`/`TableRow`/`TableHead`/`TableCell`
  de `components/ui/table.tsx` (ya existente).
- Produces: `DataTable<T>({ data, columns, getRowId, selectable,
  searchPlaceholder, pageSize, emptyMessage }: DataTableProps<T>)` — usado por
  `RiesgosTable` (Task 15), `EmpresaList` (Task 16) y `ParesTable` (Task 18).

Refinamiento respecto a la spec: como `cell` devuelve `React.ReactNode` (no
texto), una columna `searchable` necesita además un extractor de texto plano.
Se agrega `searchValue?: (row: T) => string`; si se omite en una columna
`searchable`, se usa `String(sortValue(row))` como fallback.

```ts
export type DataTableColumn<T> = {
  key: string;
  header: string;
  cell: (row: T) => React.ReactNode;
  sortValue?: (row: T) => string | number;
  searchable?: boolean;
  searchValue?: (row: T) => string;
  align?: "left" | "right";
};

export type DataTableProps<T> = {
  data: T[];
  columns: DataTableColumn<T>[];
  getRowId: (row: T) => string;
  selectable?: boolean;
  searchPlaceholder?: string;
  pageSize?: number;
  emptyMessage: string;
};
```

- [ ] **Step 1: Escribir el test que falla**

```tsx
import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataTable, type DataTableColumn } from "./DataTable";

interface Fila {
  id: string;
  nombre: string;
  monto: number;
}

const columns: DataTableColumn<Fila>[] = [
  { key: "nombre", header: "Nombre", cell: (f) => f.nombre, sortValue: (f) => f.nombre, searchable: true },
  { key: "monto", header: "Monto", cell: (f) => `$${f.monto}`, sortValue: (f) => f.monto },
];

function filas(n: number): Fila[] {
  // Orden de inserción intencionalmente inverso al alfabético, para que
  // "sin ordenar" y "ordenado ascendente" sean estados visiblemente distintos.
  return Array.from({ length: n }, (_, i) => {
    const idx = n - 1 - i;
    return {
      id: `f${idx}`,
      nombre: `Fila ${String(idx).padStart(2, "0")}`,
      monto: (idx + 1) * 10,
    };
  });
}

describe("DataTable", () => {
  it("shows the empty message when there is no data", () => {
    render(
      <DataTable data={[]} columns={columns} getRowId={(f) => f.id} emptyMessage="Sin datos." />,
    );
    expect(screen.getByText("Sin datos.")).toBeInTheDocument();
  });

  it("sorts ascending then descending when clicking a sortable header", async () => {
    const user = userEvent.setup();
    render(
      <DataTable data={filas(3)} columns={columns} getRowId={(f) => f.id} emptyMessage="Sin datos." pageSize={10} />,
    );

    const filasVisiblesEnOrden = () =>
      screen.getAllByRole("row").slice(1).map((row) => within(row).getAllByRole("cell")[0].textContent);

    expect(filasVisiblesEnOrden()).toEqual(["Fila 02", "Fila 01", "Fila 00"]);

    await user.click(screen.getByRole("columnheader", { name: /Nombre/ }));
    expect(filasVisiblesEnOrden()).toEqual(["Fila 00", "Fila 01", "Fila 02"]);

    await user.click(screen.getByRole("columnheader", { name: /Nombre/ }));
    expect(filasVisiblesEnOrden()).toEqual(["Fila 02", "Fila 01", "Fila 00"]);
  });

  it("filters rows by the search input using searchable columns", async () => {
    const user = userEvent.setup();
    render(
      <DataTable
        data={filas(3)}
        columns={columns}
        getRowId={(f) => f.id}
        emptyMessage="Sin datos."
        searchPlaceholder="Buscar..."
      />,
    );

    await user.type(screen.getByPlaceholderText("Buscar..."), "Fila 01");
    expect(screen.getAllByRole("row")).toHaveLength(2); // header + 1 match
    expect(screen.getByText("Fila 01")).toBeInTheDocument();
  });

  it("paginates using pageSize", async () => {
    const user = userEvent.setup();
    render(
      <DataTable data={filas(9)} columns={columns} getRowId={(f) => f.id} emptyMessage="Sin datos." pageSize={4} />,
    );

    expect(screen.getAllByRole("row")).toHaveLength(5); // header + 4
    expect(screen.getByText(/1–4 de 9/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Siguiente/ }));
    expect(screen.getByText(/5–8 de 9/)).toBeInTheDocument();
  });

  it("tracks selected rows via checkboxes when selectable", async () => {
    const user = userEvent.setup();
    render(
      <DataTable data={filas(2)} columns={columns} getRowId={(f) => f.id} emptyMessage="Sin datos." selectable pageSize={10} />,
    );

    const rowCheckboxes = screen.getAllByRole("checkbox").slice(1); // [0] es "seleccionar todo"
    await user.click(rowCheckboxes[0]);
    expect(screen.getByText(/1 seleccionada/)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Correr el test y confirmar que falla**

Run: `npm run test -- components/shared/DataTable`
Expected: FAIL — `Cannot find module './DataTable'`.

- [ ] **Step 3: Implementar `DataTable`**

```tsx
"use client";

import { useMemo, useState } from "react";
import { ArrowDown, ArrowUp, ChevronLeft, ChevronRight, Search } from "lucide-react";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";

export type DataTableColumn<T> = {
  key: string;
  header: string;
  cell: (row: T) => React.ReactNode;
  sortValue?: (row: T) => string | number;
  searchable?: boolean;
  searchValue?: (row: T) => string;
  align?: "left" | "right";
};

export type DataTableProps<T> = {
  data: T[];
  columns: DataTableColumn<T>[];
  getRowId: (row: T) => string;
  selectable?: boolean;
  searchPlaceholder?: string;
  pageSize?: number;
  emptyMessage: string;
};

export function DataTable<T>({
  data,
  columns,
  getRowId,
  selectable = false,
  searchPlaceholder,
  pageSize = 8,
  emptyMessage,
}: DataTableProps<T>) {
  const [search, setSearch] = useState("");
  const [sort, setSort] = useState<{ key: string; dir: "asc" | "desc" } | null>(null);
  const [page, setPage] = useState(0);
  const [selected, setSelected] = useState<Set<string>>(new Set());

  const filtered = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return data;
    const searchables = columns.filter((c) => c.searchable);
    if (searchables.length === 0) return data;
    return data.filter((row) =>
      searchables.some((c) => {
        const text = c.searchValue ? c.searchValue(row) : String(c.sortValue?.(row) ?? "");
        return text.toLowerCase().includes(q);
      }),
    );
  }, [data, search, columns]);

  const sorted = useMemo(() => {
    if (!sort) return filtered;
    const column = columns.find((c) => c.key === sort.key);
    if (!column?.sortValue) return filtered;
    const copia = [...filtered];
    copia.sort((a, b) => {
      const va = column.sortValue!(a);
      const vb = column.sortValue!(b);
      const cmp = va < vb ? -1 : va > vb ? 1 : 0;
      return sort.dir === "asc" ? cmp : -cmp;
    });
    return copia;
  }, [filtered, sort, columns]);

  const totalPages = Math.max(1, Math.ceil(sorted.length / pageSize));
  const pageSafe = Math.min(page, totalPages - 1);
  const pageRows = sorted.slice(pageSafe * pageSize, pageSafe * pageSize + pageSize);

  function toggleSort(key: string) {
    setPage(0);
    setSort((prev) => {
      if (prev?.key !== key) return { key, dir: "asc" };
      if (prev.dir === "asc") return { key, dir: "desc" };
      return null;
    });
  }

  function toggleRow(id: string) {
    setSelected((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAllOnPage() {
    const idsEnPagina = pageRows.map(getRowId);
    const todasSeleccionadas = idsEnPagina.every((id) => selected.has(id));
    setSelected((prev) => {
      const next = new Set(prev);
      idsEnPagina.forEach((id) => (todasSeleccionadas ? next.delete(id) : next.add(id)));
      return next;
    });
  }

  if (data.length === 0) {
    return <p className="text-sm text-muted-foreground">{emptyMessage}</p>;
  }

  return (
    <div className="space-y-3">
      {searchPlaceholder && columns.some((c) => c.searchable) && (
        <div className="relative max-w-xs">
          <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder={searchPlaceholder}
            value={search}
            onChange={(e) => {
              setSearch(e.target.value);
              setPage(0);
            }}
            className="w-full rounded-lg border border-border bg-background py-1.5 pl-8 pr-3 text-sm outline-none focus:ring-1 focus:ring-ring"
          />
        </div>
      )}

      <div className="overflow-x-auto rounded-xl border border-border">
        <Table>
          <TableHeader>
            <TableRow>
              {selectable && (
                <TableHead className="w-9">
                  <input
                    type="checkbox"
                    aria-label="Seleccionar todo"
                    className="h-4 w-4 accent-primary"
                    checked={pageRows.length > 0 && pageRows.every((r) => selected.has(getRowId(r)))}
                    onChange={toggleAllOnPage}
                  />
                </TableHead>
              )}
              {columns.map((column) => (
                <TableHead
                  key={column.key}
                  onClick={column.sortValue ? () => toggleSort(column.key) : undefined}
                  className={`${column.sortValue ? "cursor-pointer select-none" : ""} ${
                    column.align === "right" ? "text-right" : ""
                  }`}
                >
                  <span className="inline-flex items-center gap-1">
                    {column.header}
                    {sort?.key === column.key &&
                      (sort.dir === "asc" ? (
                        <ArrowUp className="h-3 w-3" />
                      ) : (
                        <ArrowDown className="h-3 w-3" />
                      ))}
                  </span>
                </TableHead>
              ))}
            </TableRow>
          </TableHeader>
          <TableBody>
            {pageRows.map((row) => {
              const id = getRowId(row);
              return (
                <TableRow key={id}>
                  {selectable && (
                    <TableCell>
                      <input
                        type="checkbox"
                        aria-label={`Seleccionar fila ${id}`}
                        className="h-4 w-4 accent-primary"
                        checked={selected.has(id)}
                        onChange={() => toggleRow(id)}
                      />
                    </TableCell>
                  )}
                  {columns.map((column) => (
                    <TableCell
                      key={column.key}
                      className={column.align === "right" ? "text-right font-mono" : ""}
                    >
                      {column.cell(row)}
                    </TableCell>
                  ))}
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-muted-foreground">
        <span>
          {sorted.length === 0
            ? "0 resultados"
            : `${pageSafe * pageSize + 1}–${Math.min(sorted.length, pageSafe * pageSize + pageSize)} de ${sorted.length}`}
          {selectable && selected.size > 0 && ` · ${selected.size} seleccionada${selected.size === 1 ? "" : "s"}`}
        </span>
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setPage((p) => Math.max(0, p - 1))}
            disabled={pageSafe === 0}
            aria-label="Anterior"
            className="rounded-md border border-border p-1 disabled:opacity-40"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </button>
          <button
            type="button"
            onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
            disabled={pageSafe >= totalPages - 1}
            aria-label="Siguiente"
            className="rounded-md border border-border p-1 disabled:opacity-40"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </button>
        </div>
      </div>
    </div>
  );
}
```

- [ ] **Step 4: Correr el test y confirmar que pasa**

Run: `npm run test -- components/shared/DataTable`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add components/shared/DataTable.tsx components/shared/DataTable.test.tsx
git commit -m "feat: agregar DataTable genérico (orden, búsqueda, paginación, selección)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Fase 4 — Rediseño página por página

Ningún hook de datos cambia de firma en esta fase — solo el markup. Corre
`npm run test` (suite completa) al final de cada task, no solo el patrón
específico, porque estos cambios tocan componentes compartidos entre páginas.

### Task 14: Restyle de Login

**Files:**
- Modify: `frontend/app/login/page.tsx`

**Interfaces:** Ninguna nueva — mismo `useLogin()`, misma validación, mismos
`id` de campos (`email`, `password`) para no romper `app/login/page.test.tsx`.

- [ ] **Step 1: Reescribir el JSX de `app/login/page.tsx`**

Mantén exactamente la misma lógica de `handleSubmit`/estado (no la repitas si ya
la tienes en el archivo actual — solo reemplaza el `return`):

```tsx
  return (
    <main className="flex min-h-screen items-center justify-center bg-background p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-5 rounded-2xl border border-border bg-card p-8 shadow-sm"
      >
        <div className="space-y-1 text-center">
          <div className="mx-auto flex h-10 w-10 items-center justify-center rounded-xl bg-primary text-primary-foreground">
            F
          </div>
          <h1 className="font-display text-xl font-bold">FiscalCore</h1>
          <p className="text-sm text-muted-foreground">Inicia sesión para continuar</p>
        </div>

        <div className="space-y-2">
          <Label htmlFor="email">Correo</Label>
          <Input
            id="email"
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
          />
        </div>

        <div className="space-y-2">
          <Label htmlFor="password">Contraseña</Label>
          <Input
            id="password"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
          />
        </div>

        {formError && (
          <p role="alert" className="text-sm text-status-error">
            {formError}
          </p>
        )}

        <Button type="submit" className="w-full" disabled={login.isPending}>
          {login.isPending ? "Entrando..." : "Entrar"}
        </Button>
      </form>
    </main>
  );
```

- [ ] **Step 2: Verificar**

```bash
npm run test -- app/login
```

Expected: PASS, sin cambios necesarios en `app/login/page.test.tsx` (mismos
`id`, mismo `role="alert"`, mismo texto de botón).

- [ ] **Step 3: Commit**

```bash
git add app/login/page.tsx
git commit -m "style: restyle de Login con la nueva paleta

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 15: Rediseño de Dashboard

**Files:**
- Modify: `frontend/components/dashboard/RiesgosTable.tsx`
- Modify: `frontend/components/dashboard/RiesgosTable.test.tsx`
- Modify: `frontend/components/dashboard/ResumenRiesgos.tsx`
- Create: `frontend/components/dashboard/ResumenRiesgos.test.tsx` (no existía)
- Modify: `frontend/app/(app)/empresas/[empresaId]/dashboard/page.tsx`

**Interfaces:**
- Consumes: `DataTable`/`StatusBadge` (Task 13/11) en `RiesgosTable`; `StatCard`
  (Task 12) en `ResumenRiesgos` y en la página.
- `RiesgosTable({ riesgos }: { riesgos: RiesgoAbierto[] })` y
  `ResumenRiesgos({ resumen }: { resumen: ResumenRiesgosType })` conservan su
  firma pública — no cambian los imports en `page.tsx` salvo el nuevo bloque de
  `StatCard`.

- [ ] **Step 1: Migrar `RiesgosTable` a `DataTable`**

```tsx
import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { RiesgoAbierto } from "@/types/api";

const SEVERIDAD_RANK: Record<RiesgoAbierto["severidad"], number> = {
  critico: 0,
  alto: 1,
  medio: 2,
  bajo: 3,
};

function formatMoney(value: number | null): string {
  if (value == null) return "—";
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

const columns: DataTableColumn<RiesgoAbierto>[] = [
  {
    key: "severidad",
    header: "Severidad",
    cell: (r) => <StatusBadge status={r.severidad} />,
    sortValue: (r) => SEVERIDAD_RANK[r.severidad],
  },
  {
    key: "nombre",
    header: "Riesgo",
    cell: (r) => <span className="font-medium">{r.nombre}</span>,
    sortValue: (r) => r.nombre,
    searchable: true,
  },
  {
    key: "estado",
    header: "Estado",
    cell: (r) => <StatusBadge status={r.estado} />,
  },
  {
    key: "monto",
    header: "Monto afectado",
    cell: (r) => formatMoney(r.monto_afectado),
    sortValue: (r) => r.monto_afectado ?? 0,
    align: "right",
  },
  {
    key: "descripcion",
    header: "Descripción",
    cell: (r) => r.descripcion ?? "—",
    searchable: true,
    searchValue: (r) => r.descripcion ?? "",
  },
];

export function RiesgosTable({ riesgos }: { riesgos: RiesgoAbierto[] }) {
  return (
    <DataTable
      data={riesgos}
      columns={columns}
      getRowId={(r) => r.id}
      searchPlaceholder="Buscar riesgo..."
      emptyMessage="No hay riesgos abiertos en este periodo."
    />
  );
}
```

- [ ] **Step 2: Agregar el caso de la columna Estado a `RiesgosTable.test.tsx`**

Agrega al final del `describe`, después del test `"renders a row per risk"`:

```tsx
  it("renders a status badge for the risk's estado", () => {
    render(<RiesgosTable riesgos={[riesgo]} />);
    expect(screen.getByText("Pendiente")).toBeInTheDocument();
  });
```

(El fixture `riesgo` ya tiene `estado: "abierto"`, que `StatusBadge` mapea a la
etiqueta "Pendiente" — ver Task 11.)

- [ ] **Step 3: Migrar `ResumenRiesgos` a `StatCard`**

```tsx
import { AlertTriangle } from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
import type { ResumenRiesgos as ResumenRiesgosType } from "@/types/api";

export function ResumenRiesgos({ resumen }: { resumen: ResumenRiesgosType }) {
  const items: Array<{
    label: string;
    value: number;
    tone: "critico" | "alto" | "default" | "ok";
  }> = [
    { label: "Críticos", value: resumen.critico, tone: "critico" },
    { label: "Altos", value: resumen.alto, tone: "alto" },
    { label: "Medios", value: resumen.medio, tone: "default" },
    { label: "Bajos", value: resumen.bajo, tone: "default" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
      {items.map((item) => (
        <StatCard
          key={item.label}
          label={item.label}
          value={String(item.value)}
          icon={AlertTriangle}
          tone={item.tone}
        />
      ))}
    </div>
  );
}
```

- [ ] **Step 4: Escribir `ResumenRiesgos.test.tsx` (no existía)**

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResumenRiesgos } from "./ResumenRiesgos";
import type { ResumenRiesgos as ResumenRiesgosType } from "@/types/api";

const resumen: ResumenRiesgosType = {
  critico: 2,
  alto: 3,
  medio: 1,
  bajo: 6,
  monto_total_en_riesgo: 284320,
};

describe("ResumenRiesgos", () => {
  it("renders one stat card per severidad with its conteo", () => {
    render(<ResumenRiesgos resumen={resumen} />);
    expect(screen.getByText("Críticos")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Altos")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Medios")).toBeInTheDocument();
    expect(screen.getByText("Bajos")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
  });
});
```

- [ ] **Step 5: Agregar la fila de `StatCard` principales a la página de Dashboard**

En `app/(app)/empresas/[empresaId]/dashboard/page.tsx`, agrega los imports y
reemplaza el bloque `{dashboard.data && (...)}` (dejando el resto del archivo
—incluyendo el `<Input>` de periodo del Task 10— igual):

```tsx
import { AlertTriangle, DollarSign, GitBranch, TrendingUp } from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
// ...el resto de imports existentes del Task 10 se mantienen...
```

```tsx
      {dashboard.data && (
        <>
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard
              label="Score fiscal actual"
              value={`${dashboard.data.tendencia_score.at(-1)?.score ?? "—"}/100`}
              icon={TrendingUp}
              tone="ok"
              delta={
                dashboard.data.tendencia_score.length >= 2
                  ? (() => {
                      const [prev, curr] = dashboard.data.tendencia_score.slice(-2);
                      const diff = curr.score - prev.score;
                      return {
                        value: `${diff >= 0 ? "+" : ""}${diff} pts`,
                        direction: diff >= 0 ? ("up" as const) : ("down" as const),
                        label: `vs. ${prev.periodo}`,
                      };
                    })()
                  : undefined
              }
            />
            <StatCard
              label="Riesgos abiertos"
              value={String(dashboard.data.riesgos_abiertos.length)}
              icon={AlertTriangle}
              tone="alto"
            />
            <StatCard
              label="Monto en riesgo"
              value={dashboard.data.resumen_riesgos.monto_total_en_riesgo.toLocaleString(
                "es-MX",
                { style: "currency", currency: "MXN" },
              )}
              icon={DollarSign}
              tone="critico"
            />
            <StatCard
              label="Conciliación bancaria"
              value={`${dashboard.data.indicadores.pct_conciliacion ?? 0}%`}
              icon={GitBranch}
              tone="ok"
            />
          </div>
          <ResumenRiesgos resumen={dashboard.data.resumen_riesgos} />
          <RiesgosTable riesgos={dashboard.data.riesgos_abiertos} />
        </>
      )}
```

- [ ] **Step 6: Verificar**

```bash
npm run test
npm run build
```

Expected: suite completa en verde, build sin errores.

- [ ] **Step 7: Commit**

```bash
git add components/dashboard/ app/(app)/empresas/\[empresaId\]/dashboard/page.tsx
git commit -m "feat: rediseñar Dashboard con StatCard y DataTable

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 16: Rediseño de Empresas

**Files:**
- Modify: `frontend/components/empresas/EmpresaList.tsx`
- Modify: `frontend/components/empresas/EmpresaList.test.tsx`
- Modify: `frontend/components/empresas/EmpresaForm.tsx`
- Modify: `frontend/app/(app)/empresas/page.tsx`

**Interfaces:**
- Consumes: `DataTable` (Task 13), `Dialog`/`DialogContent`/`DialogHeader`/
  `DialogTitle`/`DialogTrigger` (Task 3), `DropdownMenu*` (Task 3).
- `EmpresaForm({ onCreated }: { onCreated?: () => void })` conserva su firma —
  `EmpresaForm.test.tsx` no requiere cambios (verificado: no depende del
  `<h2>` que se retira en el Step 3).

- [ ] **Step 1: Migrar `EmpresaList` a `DataTable`**

```tsx
"use client";

import Link from "next/link";
import { MoreHorizontal } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import type { Empresa } from "@/types/api";

const columns: DataTableColumn<Empresa>[] = [
  {
    key: "rfc",
    header: "RFC",
    cell: (e) => <span className="font-mono">{e.rfc}</span>,
    sortValue: (e) => e.rfc,
  },
  {
    key: "razon_social",
    header: "Razón social",
    cell: (e) => e.razon_social,
    sortValue: (e) => e.razon_social,
    searchable: true,
  },
  {
    key: "regimen_fiscal",
    header: "Régimen fiscal",
    cell: (e) => e.regimen_fiscal ?? "—",
  },
  {
    key: "acciones",
    header: "",
    cell: (empresa) => (
      <DropdownMenu>
        <DropdownMenuTrigger asChild>
          <button
            type="button"
            aria-label={`Acciones para ${empresa.razon_social}`}
            className="rounded-md p-1.5 text-muted-foreground hover:bg-accent hover:text-foreground"
          >
            <MoreHorizontal className="h-4 w-4" />
          </button>
        </DropdownMenuTrigger>
        <DropdownMenuContent align="end">
          <DropdownMenuItem asChild>
            <Link href={`/empresas/${empresa.id}/ingesta`}>Ingesta</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href={`/empresas/${empresa.id}/cedula-iva`}>Cédula de IVA</Link>
          </DropdownMenuItem>
          <DropdownMenuItem asChild>
            <Link href={`/empresas/${empresa.id}/conciliacion`}>Conciliación</Link>
          </DropdownMenuItem>
        </DropdownMenuContent>
      </DropdownMenu>
    ),
  },
];

export function EmpresaList({ empresas }: { empresas: Empresa[] }) {
  return (
    <DataTable
      data={empresas}
      columns={columns}
      getRowId={(e) => e.id}
      searchPlaceholder="Buscar por RFC o razón social..."
      emptyMessage="Aún no hay empresas registradas."
    />
  );
}
```

- [ ] **Step 2: Actualizar `EmpresaList.test.tsx`**

Reemplázalo completo — los links de acciones ahora viven detrás de un menú:

```tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmpresaList } from "./EmpresaList";
import type { Empresa } from "@/types/api";

const empresa: Empresa = {
  id: "e1",
  rfc: "AAA010101AAA",
  razon_social: "Acme SA de CV",
  regimen_fiscal: null,
  cp_fiscal: null,
  curp: null,
  obligaciones: null,
  representante_legal: null,
  rfc_representante: null,
  activo: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

async function abrirMenuAcciones() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /Acciones para/ }));
  return user;
}

describe("EmpresaList", () => {
  it("shows the empty state message when there are no empresas", () => {
    render(<EmpresaList empresas={[]} />);
    expect(
      screen.getByText("Aún no hay empresas registradas."),
    ).toBeInTheDocument();
  });

  it("renders an Ingesta link pointing to the empresa's ingesta page", async () => {
    render(<EmpresaList empresas={[empresa]} />);
    await abrirMenuAcciones();

    const link = screen.getByRole("link", { name: "Ingesta" });
    expect(link).toHaveAttribute("href", "/empresas/e1/ingesta");
  });

  it("still renders the Cédula de IVA and Conciliación links", async () => {
    render(<EmpresaList empresas={[empresa]} />);
    await abrirMenuAcciones();

    expect(screen.getByRole("link", { name: "Cédula de IVA" })).toHaveAttribute(
      "href",
      "/empresas/e1/cedula-iva",
    );
    expect(screen.getByRole("link", { name: "Conciliación" })).toHaveAttribute(
      "href",
      "/empresas/e1/conciliacion",
    );
  });
});
```

- [ ] **Step 3: Quitar el encabezado y el borde propio de `EmpresaForm`**

En `EmpresaForm.tsx`, cambia la etiqueta de apertura del `<form>` y elimina el
`<h2>` (el título ahora lo aporta el `Dialog` de la página):

```tsx
    <form onSubmit={handleSubmit} className="space-y-4">
```

(Se quita la línea `<h2 className="text-lg font-semibold">Agregar empresa</h2>`
completa; el resto del componente —incluyendo el botón "Guardar"— no cambia.)

- [ ] **Step 4: Envolver `EmpresaForm` en un `Dialog` en la página**

```tsx
"use client";

import { useState } from "react";
import { Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { EmpresaForm } from "@/components/empresas/EmpresaForm";
import { EmpresaList } from "@/components/empresas/EmpresaList";
import { ErrorState } from "@/components/shared/ErrorState";
import { useEmpresas } from "@/hooks/useEmpresas";

export default function EmpresasPage() {
  const { data: empresas, isLoading, isError, refetch } = useEmpresas();
  const [open, setOpen] = useState(false);

  return (
    <main className="mx-auto max-w-4xl space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Empresas</h1>
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogTrigger asChild>
            <Button>
              <Plus className="h-4 w-4" />
              Nueva empresa
            </Button>
          </DialogTrigger>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Agregar empresa</DialogTitle>
            </DialogHeader>
            <EmpresaForm onCreated={() => setOpen(false)} />
          </DialogContent>
        </Dialog>
      </div>

      {isLoading && <p>Cargando empresas...</p>}
      {isError && (
        <ErrorState
          message="No se pudieron cargar las empresas."
          onRetry={() => refetch()}
        />
      )}
      {empresas && <EmpresaList empresas={empresas} />}
    </main>
  );
}
```

- [ ] **Step 5: Verificar**

```bash
npm run test
npm run build
```

Expected: suite completa en verde (incluyendo `EmpresaForm.test.tsx` sin
modificar), build sin errores.

- [ ] **Step 6: Commit**

```bash
git add components/empresas/ app/\(app\)/empresas/page.tsx
git commit -m "feat: rediseñar Empresas con DataTable y alta en Dialog

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 17: Rediseño de Ingesta

**Files:**
- Modify: `frontend/components/ingesta/CfdiUploadForm.tsx`
- Modify: `frontend/components/ingesta/BancoUploadForm.tsx`
- Modify: `frontend/components/ingesta/IngestaResultado.tsx`

**Interfaces:** Sin cambios de props en ninguno de los 3 componentes
(`CfdiUploadForm({ empresaId })`, `BancoUploadForm({ empresaId })`,
`IngestaResultado({ resultado })`) — `IngestaResultado.test.tsx` no requiere
cambios (verificado: no depende de clases CSS, solo de texto y de
`getByRole("list")`).

- [ ] **Step 1: Envolver `CfdiUploadForm` en `Card`**

Reemplaza el `return` (la lógica de `handleSubmit`/estado no cambia):

```tsx
  return (
    <Card>
      <CardHeader>
        <CardTitle>Subir CFDI</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="cfdi-periodo">Periodo (YYYY-MM)</Label>
            <Input
              id="cfdi-periodo"
              placeholder="2026-07"
              value={periodo}
              onChange={(e) => setPeriodo(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="cfdi-archivos">Archivos XML</Label>
            <Input
              id="cfdi-archivos"
              type="file"
              multiple
              accept=".xml"
              onChange={(e) => setArchivos(e.target.files)}
            />
          </div>

          {formError && (
            <p role="alert" className="text-sm text-status-error">
              {formError}
            </p>
          )}

          <Button type="submit" disabled={subirCfdi.isPending}>
            {subirCfdi.isPending ? "Subiendo..." : "Subir CFDI"}
          </Button>

          {resultado && <IngestaResultado resultado={resultado} />}
        </form>
      </CardContent>
    </Card>
  );
```

Agrega el import de `Card`/`CardContent`/`CardHeader`/`CardTitle` al inicio del
archivo (junto a los imports existentes de `Button`/`Input`/`Label`):

```tsx
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
```

- [ ] **Step 2: Envolver `BancoUploadForm` en `Card`**

Mismo patrón — reemplaza el `return` (mantén el `select` nativo de banco tal
cual, incluyendo `esOtro`/`bancoLibre`):

```tsx
  return (
    <Card>
      <CardHeader>
        <CardTitle>Subir estado de cuenta</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="banco-periodo">Periodo (YYYY-MM)</Label>
            <Input
              id="banco-periodo"
              placeholder="2026-07"
              value={periodo}
              onChange={(e) => setPeriodo(e.target.value)}
            />
          </div>

          <div className="space-y-2">
            <Label htmlFor="banco-select">Banco</Label>
            <select
              id="banco-select"
              className="w-full rounded-md border border-input bg-background p-2 text-sm"
              value={bancoSeleccionado}
              onChange={(e) => setBancoSeleccionado(e.target.value)}
            >
              <option value="">Selecciona un banco</option>
              {BANCOS_COMUNES.map((banco) => (
                <option key={banco.value} value={banco.value}>
                  {banco.label}
                </option>
              ))}
            </select>
          </div>

          {esOtro && (
            <div className="space-y-2">
              <Label htmlFor="banco-libre">Nombre del banco</Label>
              <Input
                id="banco-libre"
                value={bancoLibre}
                onChange={(e) => setBancoLibre(e.target.value)}
              />
            </div>
          )}

          <div className="space-y-2">
            <Label htmlFor="banco-archivo">Estado de cuenta (.xlsx o .csv)</Label>
            <Input
              id="banco-archivo"
              type="file"
              accept=".xlsx,.csv"
              onChange={(e) => setArchivo(e.target.files?.[0] ?? null)}
            />
          </div>

          {formError && (
            <p role="alert" className="text-sm text-status-error">
              {formError}
            </p>
          )}

          <Button type="submit" disabled={subirBanco.isPending}>
            {subirBanco.isPending ? "Subiendo..." : "Subir estado de cuenta"}
          </Button>

          {resultado && <IngestaResultado resultado={resultado} />}
        </form>
      </CardContent>
    </Card>
  );
```

Agrega el mismo import de `Card`/`CardContent`/`CardHeader`/`CardTitle`.

- [ ] **Step 3: Rediseñar `IngestaResultado`**

```tsx
import { AlertTriangle, CheckCircle2 } from "lucide-react";
import type { IngestaResponse } from "@/types/api";

export function IngestaResultado({ resultado }: { resultado: IngestaResponse }) {
  const plural = resultado.registros_procesados === 1 ? "" : "s";
  const sinErrores = resultado.errores.length === 0;

  return (
    <div
      className={`space-y-2 rounded-lg border p-4 text-sm ${
        sinErrores
          ? "border-status-ok-soft bg-status-ok-soft"
          : "border-status-pendiente-soft bg-status-pendiente-soft"
      }`}
    >
      <p className="flex items-center gap-2 font-medium">
        {sinErrores ? (
          <CheckCircle2 className="h-4 w-4 flex-none text-status-ok" />
        ) : (
          <AlertTriangle className="h-4 w-4 flex-none text-status-pendiente" />
        )}
        {resultado.mensaje}
      </p>
      <p>
        {resultado.registros_procesados} registro{plural} procesado{plural}.
      </p>
      {resultado.errores.length > 0 && (
        <ul className="list-disc space-y-1 pl-9">
          {resultado.errores.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Verificar**

```bash
npm run test -- ingesta
npm run build
```

Expected: PASS, `IngestaResultado.test.tsx` sigue en verde sin modificaciones.

- [ ] **Step 5: Commit**

```bash
git add components/ingesta/
git commit -m "feat: rediseñar Ingesta con Card y estados con ícono

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 18: Rediseño de Conciliación

**Files:**
- Modify: `frontend/components/conciliacion/ResumenConciliacion.tsx`
- Modify: `frontend/components/conciliacion/ParesTable.tsx`
- Modify: `frontend/app/(app)/empresas/[empresaId]/conciliacion/page.tsx`

**Interfaces:** Sin cambios de props (`ResumenConciliacion({ resumen })`,
`ParesTable({ pares })`). Ambos archivos de test (`ResumenConciliacion.test.tsx`,
`ParesTable.test.tsx`, traídos por el merge de la Fase 0) **no requieren
modificación** — se preservan a propósito los mismos textos exactos que ya
verifican (`"Conciliado (20 movimientos)"`, `"Sin CFDI"`, etc.).

- [ ] **Step 1: Migrar `ResumenConciliacion` a `StatCard`**

```tsx
import { CheckCircle2 } from "lucide-react";
import { StatCard } from "@/components/shared/StatCard";
import type { ConciliacionResumen } from "@/types/api";

export function ResumenConciliacion({ resumen }: { resumen: ConciliacionResumen }) {
  const items: Array<{ label: string; value: number; tone: "ok" | "default" | "alto" | "critico" }> = [
    { label: "Exactos", value: resumen.exacto, tone: "ok" },
    { label: "Parciales", value: resumen.parcial, tone: "default" },
    { label: "Sin CFDI", value: resumen.sin_cfdi, tone: "alto" },
    { label: "Sin movimiento", value: resumen.sin_movimiento, tone: "critico" },
  ];

  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
      {items.map((item) => (
        <StatCard
          key={item.label}
          label={item.label}
          value={String(item.value)}
          icon={CheckCircle2}
          tone={item.tone}
        />
      ))}
      <StatCard
        label={`Conciliado (${resumen.total} movimientos)`}
        value={`${resumen.pct_conciliado}%`}
        icon={CheckCircle2}
        tone="ok"
      />
    </div>
  );
}
```

Nota: el `label` del último `StatCard` reproduce textualmente
`"Conciliado (20 movimientos)"` (con el `total` real interpolado) — es a
propósito, para que `ResumenConciliacion.test.tsx` siga pasando sin tocarlo.

- [ ] **Step 2: Migrar `ParesTable` a `DataTable`**

```tsx
import { DataTable, type DataTableColumn } from "@/components/shared/DataTable";
import { StatusBadge } from "@/components/shared/StatusBadge";
import type { ParConciliacion } from "@/types/api";

function formatMoney(value: number | null): string {
  if (value == null) return "—";
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

const columns: DataTableColumn<ParConciliacion>[] = [
  { key: "tipo_match", header: "Tipo", cell: (p) => <StatusBadge status={p.tipo_match} /> },
  {
    key: "mov_fecha",
    header: "Fecha",
    cell: (p) => p.mov_fecha ?? "—",
    sortValue: (p) => p.mov_fecha ?? "",
  },
  {
    key: "concepto",
    header: "Concepto",
    cell: (p) => p.concepto ?? "—",
    searchable: true,
    searchValue: (p) => p.concepto ?? "",
  },
  {
    key: "rfc_detectado",
    header: "RFC detectado",
    cell: (p) => <span className="font-mono">{p.rfc_detectado ?? "—"}</span>,
  },
  {
    key: "monto_movimiento",
    header: "Monto movimiento",
    cell: (p) => formatMoney(p.monto_movimiento),
    sortValue: (p) => p.monto_movimiento ?? 0,
    align: "right",
  },
  {
    key: "monto_cfdi",
    header: "Monto CFDI",
    cell: (p) => formatMoney(p.monto_cfdi),
    sortValue: (p) => p.monto_cfdi ?? 0,
    align: "right",
  },
  {
    key: "diferencia",
    header: "Diferencia",
    cell: (p) => (
      <span
        className={
          p.diferencia != null && p.diferencia < 0 ? "text-status-error" : "text-status-ok"
        }
      >
        {formatMoney(p.diferencia)}
      </span>
    ),
    sortValue: (p) => p.diferencia ?? 0,
    align: "right",
  },
];

export function ParesTable({ pares }: { pares: ParConciliacion[] }) {
  return (
    <DataTable
      data={pares}
      columns={columns}
      getRowId={(p) => p.id}
      selectable
      searchPlaceholder="Buscar concepto..."
      emptyMessage="No hay movimientos pendientes de conciliar en este periodo."
    />
  );
}
```

- [ ] **Step 3: Ajustar el contenedor de la página**

En `app/(app)/empresas/[empresaId]/conciliacion/page.tsx`, cambia solo la
clase del `<main>` (el resto del archivo —incluyendo el `<Input>` de periodo y
los hooks— no cambia):

```tsx
    <main className="mx-auto max-w-5xl space-y-6">
```

- [ ] **Step 4: Verificar**

```bash
npm run test -- conciliacion
npm run build
```

Expected: PASS, ambos archivos de test de conciliación siguen en verde sin
modificarlos.

- [ ] **Step 5: Commit**

```bash
git add components/conciliacion/ app/\(app\)/empresas/\[empresaId\]/conciliacion/page.tsx
git commit -m "feat: rediseñar Conciliación con StatCard y DataTable

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

### Task 19: Rediseño de Cédula de IVA

**Files:**
- Modify: `frontend/components/cedula-iva/CedulaIvaTable.tsx`
- Modify: `frontend/app/(app)/empresas/[empresaId]/cedula-iva/page.tsx`

**Interfaces:** Sin cambios de props (`CedulaIvaTable({ cedula })`).
`CedulaIvaTable.test.tsx` **no requiere modificación** (verificado: solo
compara texto de labels/montos, no depende del markup `<table>` nativo).

No se usa `DataTable` aquí — son 10 filas fijas clave-valor sin necesidad real
de orden/filtro/paginación (ver spec).

- [ ] **Step 1: Migrar `CedulaIvaTable` a los primitivos `Table` de shadcn**

```tsx
import {
  Table,
  TableBody,
  TableCell,
  TableRow,
} from "@/components/ui/table";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { CedulaIva } from "@/types/api";

function formatMoney(value: number): string {
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

export function CedulaIvaTable({ cedula }: { cedula: CedulaIva }) {
  const filas: Array<[string, number]> = [
    ["IVA trasladado (total)", cedula.trasladado.total],
    ["IVA acreditable bruto", cedula.acreditable.bruto],
    ["Factor de prorrateo", cedula.acreditable.factor_prorrateo],
    ["IVA acreditable ajustado", cedula.acreditable.ajustado],
    ["IVA retenido", cedula.iva_retenido],
    ["IVA por pagar", cedula.resultado.iva_por_pagar],
    ["Saldo a cargo", cedula.resultado.saldo_a_cargo],
    ["Saldo a favor", cedula.resultado.saldo_a_favor],
    ["IVA pagado según DIOT", cedula.comparativo_sat.diot_iva_pagado],
    ["Diferencia vs. DIOT", cedula.comparativo_sat.diferencia],
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Cédula de IVA</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableBody>
            {filas.map(([label, value]) => (
              <TableRow key={label}>
                <TableCell className="font-medium">{label}</TableCell>
                <TableCell className="text-right font-mono">
                  {label === "Factor de prorrateo" ? value : formatMoney(value)}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
```

- [ ] **Step 2: Ajustar el contenedor de la página**

En `app/(app)/empresas/[empresaId]/cedula-iva/page.tsx`, quita el `<h1>Cédula
de IVA</h1>` duplicado (el `CardTitle` ya lo muestra) y ajusta el `<main>`:

```tsx
    <main className="mx-auto max-w-3xl space-y-6">
```

Elimina la línea `<h1 className="text-2xl font-semibold">Cédula de IVA</h1>`
— el resto del archivo (input de periodo, estados de carga/error) no cambia.

- [ ] **Step 3: Verificar**

```bash
npm run test -- cedula-iva
npm run build
```

Expected: PASS, `CedulaIvaTable.test.tsx` sigue en verde sin modificarlo.

- [ ] **Step 4: Commit**

```bash
git add components/cedula-iva/ app/\(app\)/empresas/\[empresaId\]/cedula-iva/page.tsx
git commit -m "feat: rediseñar Cédula de IVA con Table y Card

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

---

## Cierre

### Task 20: Verificación end-to-end

**Files:** Ninguno (solo verificación manual y automatizada).

- [ ] **Step 1: Suite completa + build**

```bash
cd /c/Users/carlo/Project_Development/FiscalCore/.worktrees/feat-frontend-rediseno/frontend
npm run test
npm run build
```

Expected: toda la suite en verde, build sin errores ni warnings de rutas.

- [ ] **Step 2: Levantar backend y frontend locales**

```bash
# Terminal 1, desde la raíz del repo:
cd /c/Users/carlo/Project_Development/FiscalCore
./dev.sh   # o: python -m uvicorn backend.main_api:app --reload --port 8000

# Terminal 2:
cd /c/Users/carlo/Project_Development/FiscalCore/.worktrees/feat-frontend-rediseno/frontend
npm run dev
```

- [ ] **Step 3: Recorrido manual completo**

En el navegador (`http://localhost:3000`), en **light mode** primero:

1. Login con un usuario de prueba.
2. En `/empresas`: crear una empresa nueva vía el botón "Nueva empresa" (Dialog)
   y confirmar que aparece en la `DataTable` sin recargar la página.
3. Abrir el menú de acciones (`⋯`) de esa empresa y navegar a Ingesta.
4. Subir un XML de CFDI y un estado de cuenta de ejemplo; confirmar que
   `IngestaResultado` muestra el ícono correcto (verde sin errores / ámbar con
   errores).
5. Ir a Dashboard (vía sidebar): confirmar las 4 `StatCard` principales, la fila
   de severidad, y que la tabla de riesgos ordena/filtra/pagina correctamente.
6. Ir a Conciliación: confirmar las `StatCard` de resumen y que `ParesTable`
   permite seleccionar filas con checkbox.
7. Ir a Cédula de IVA: confirmar que la tabla clave-valor se ve dentro de una
   `Card`.
8. Usar el buscador del header para saltar a otra empresa; confirmar que
   `EmpresaSwitcher` en el sidebar también refleja el cambio.
9. Clic en `ThemeToggle`: confirmar que toda la app cambia a **dark mode** sin
   texto ilegible en ninguna pantalla visitada, y que persiste al recargar
   (`F5`).
10. Reducir el viewport a <1024px (herramientas de desarrollador): confirmar
    que el sidebar se oculta y el botón hamburguesa del header lo abre como
    `Sheet`.
11. Cerrar sesión desde el sidebar; confirmar redirección a `/login`.

Expected: ningún error de consola, ninguna pantalla rota, navegación
consistente entre Sidebar/Header/EmpresaSwitcher en todo el recorrido.

- [ ] **Step 4: Confirmar que no queda código muerto**

```bash
grep -rn "AppHeader" --include="*.tsx" --include="*.ts" .
```

Expected: sin resultados (el componente fue eliminado en la Task 9 y nada debe
importarlo ya).

Este task no genera un commit propio — es la verificación de cierre de todo el
plan. Si algo falla en el Step 3, vuelve a la task correspondiente, corrige, y
repite este task completo antes de considerar el rediseño terminado.
