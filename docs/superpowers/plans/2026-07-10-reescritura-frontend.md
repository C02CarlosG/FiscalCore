# Reescritura de Frontend (Fase 1 — núcleo mínimo) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir, en la rama `feat/frontend-nextjs`, un frontend Next.js mínimo funcional que cubra login, alta/listado de empresas, dashboard y cédula de IVA, consumiendo la API de FastAPI ya existente en `backend/`.

**Architecture:** SPA con Next.js App Router usado solo como router/bundler (sin SSR de datos de negocio, porque la sesión vive en `localStorage`). Todas las páginas de negocio son Client Components envueltas en un `AuthGuard`. TanStack Query maneja fetch/cache/invalidación contra la API; un wrapper de `fetch` (`lib/api-client.ts`) centraliza headers y normalización de errores.

**Tech Stack:** Next.js (App Router) + TypeScript, Tailwind CSS, shadcn/ui, TanStack Query, Vitest + React Testing Library.

Ver spec completa en `docs/superpowers/specs/2026-07-10-reescritura-frontend-design.md`.

## Global Constraints

- Todo el código nuevo vive bajo `frontend/` en la raíz del repo (no tocar `backend/` ni `database/` en este plan).
- Trabajar sobre la rama `feat/frontend-nextjs` (ya creada y con la spec commiteada en `31869d7`).
- Sesión: token JWT en `localStorage` bajo la clave `fiscalcore.session` (no cookies httpOnly).
- Variable de entorno para la URL de la API: `NEXT_PUBLIC_API_URL` (ver `.env.local.example`).
- Alcance de páginas de esta fase: `/login`, `/empresas`, `/dashboard`, `/empresas/[empresaId]/cedula-iva`. Ninguna otra página.
- No agregar parseo de constancia de situación fiscal, ni las 8 páginas restantes del frontend anterior — están fuera de alcance (ver spec).
- Cada commit sigue Conventional Commits (`feat:`, `test:`, `chore:`), imperativo y acotado, por convención del repo (`CLAUDE.md`).

---

### Task 1: Scaffold del proyecto Next.js (TS + Tailwind + shadcn/ui + TanStack Query + Vitest)

**Files:**
- Create: `frontend/` (generado por `create-next-app`)
- Modify: `frontend/tailwind.config.ts`
- Modify: `frontend/app/globals.css`
- Create: `frontend/components.json`
- Create: `frontend/lib/utils.ts`
- Create: `frontend/components/ui/button.tsx`, `frontend/components/ui/card.tsx`, `frontend/components/ui/input.tsx`, `frontend/components/ui/label.tsx`, `frontend/components/ui/table.tsx`, `frontend/components/ui/select.tsx` (generados por `shadcn` CLI)
- Create: `frontend/vitest.config.ts`
- Create: `frontend/vitest.setup.ts`
- Create: `frontend/.env.local.example`
- Create: `frontend/.env.local`
- Modify: `frontend/package.json` (scripts `test`, `test:watch`)

**Interfaces:**
- Produces: alias de import `@/*` apuntando a `frontend/` (usado por todas las tasks siguientes); comando `npm test` corriendo Vitest; componentes shadcn/ui importables desde `@/components/ui/*`.

- [ ] **Step 1: Generar el proyecto base con create-next-app**

Desde la raíz del repo:

```bash
npx --yes create-next-app@latest frontend \
  --typescript --eslint --tailwind --app --no-src-dir \
  --import-alias "@/*" --use-npm
```

Responde "Yes" a cualquier prompt residual sobre Turbopack o convenciones adicionales si el CLI lo pregunta (no debería, con los flags de arriba).

Run: `test -d frontend/app && echo OK`
Expected: `OK`

- [ ] **Step 2: Instalar dependencias de shadcn/ui, TanStack Query y testing**

```bash
cd frontend
npm install @tanstack/react-query clsx tailwind-merge class-variance-authority lucide-react tailwindcss-animate
npm install -D vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom @testing-library/user-event vite-tsconfig-paths
```

Run: `cat package.json | grep -c "@tanstack/react-query"`
Expected: `1`

- [ ] **Step 3: Escribir `components.json` (config de shadcn/ui)**

```json
{
  "$schema": "https://ui.shadcn.com/schema.json",
  "style": "new-york",
  "rsc": true,
  "tsx": true,
  "tailwind": {
    "config": "tailwind.config.ts",
    "css": "app/globals.css",
    "baseColor": "neutral",
    "cssVariables": true,
    "prefix": ""
  },
  "aliases": {
    "components": "@/components",
    "utils": "@/lib/utils",
    "ui": "@/components/ui",
    "lib": "@/lib",
    "hooks": "@/hooks"
  }
}
```

Guardar en `frontend/components.json`.

- [ ] **Step 4: Escribir `lib/utils.ts` (helper `cn` que usan los componentes shadcn/ui)**

```ts
import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}
```

Guardar en `frontend/lib/utils.ts`.

- [ ] **Step 5: Reemplazar `tailwind.config.ts` con la config de shadcn/ui**

```ts
import type { Config } from "tailwindcss";

const config: Config = {
  darkMode: ["class"],
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: { "2xl": "1400px" },
    },
    extend: {
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
};

export default config;
```

Guardar en `frontend/tailwind.config.ts` (sobreescribe el generado por create-next-app).

- [ ] **Step 6: Reemplazar `app/globals.css` con las variables CSS de shadcn/ui**

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    --background: 0 0% 100%;
    --foreground: 0 0% 3.9%;
    --card: 0 0% 100%;
    --card-foreground: 0 0% 3.9%;
    --popover: 0 0% 100%;
    --popover-foreground: 0 0% 3.9%;
    --primary: 0 0% 9%;
    --primary-foreground: 0 0% 98%;
    --secondary: 0 0% 96.1%;
    --secondary-foreground: 0 0% 9%;
    --muted: 0 0% 96.1%;
    --muted-foreground: 0 0% 45.1%;
    --accent: 0 0% 96.1%;
    --accent-foreground: 0 0% 9%;
    --destructive: 0 84.2% 60.2%;
    --destructive-foreground: 0 0% 98%;
    --border: 0 0% 89.8%;
    --input: 0 0% 89.8%;
    --ring: 0 0% 3.9%;
    --radius: 0.5rem;
  }

  .dark {
    --background: 0 0% 3.9%;
    --foreground: 0 0% 98%;
    --card: 0 0% 3.9%;
    --card-foreground: 0 0% 98%;
    --popover: 0 0% 3.9%;
    --popover-foreground: 0 0% 98%;
    --primary: 0 0% 98%;
    --primary-foreground: 0 0% 9%;
    --secondary: 0 0% 14.9%;
    --secondary-foreground: 0 0% 98%;
    --muted: 0 0% 14.9%;
    --muted-foreground: 0 0% 63.9%;
    --accent: 0 0% 14.9%;
    --accent-foreground: 0 0% 98%;
    --destructive: 0 62.8% 30.6%;
    --destructive-foreground: 0 0% 98%;
    --border: 0 0% 14.9%;
    --input: 0 0% 14.9%;
    --ring: 0 0% 83.1%;
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

Guardar en `frontend/app/globals.css`.

- [ ] **Step 7: Generar los componentes de shadcn/ui con el CLI**

```bash
npx --yes shadcn@latest add button card input label table select --yes
```

Run: `ls frontend/components/ui/`
Expected: incluye `button.tsx card.tsx input.tsx label.tsx table.tsx select.tsx`

- [ ] **Step 8: Configurar Vitest**

`frontend/vitest.config.ts`:

```ts
import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import tsconfigPaths from "vite-tsconfig-paths";

export default defineConfig({
  plugins: [tsconfigPaths(), react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    passWithNoTests: true,
  },
});
```

`frontend/vitest.setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
```

En `frontend/package.json`, dentro de `"scripts"`, agregar:

```json
"test": "vitest run",
"test:watch": "vitest"
```

Run: `cd frontend && npm test`
Expected: termina en `0` sin fallos (aún no hay archivos de test — `passWithNoTests` evita que eso sea un error).

- [ ] **Step 9: Variables de entorno**

Crear `frontend/.env.local.example`:

```
NEXT_PUBLIC_API_URL=http://localhost:8000
```

Crear `frontend/.env.local` con el mismo contenido (Next.js no lee `.env.local.example`; `.env.local` ya está en el `.gitignore` que genera create-next-app).

- [ ] **Step 10: Verificar build y dev server**

```bash
cd frontend
npm run build
```

Expected: build exitoso, sin errores de TypeScript ni de Tailwind.

```bash
cd frontend
npm run dev & sleep 3 && curl -sf http://localhost:3000 > /dev/null && echo OK; kill %1
```

Expected: `OK`

- [ ] **Step 11: Commit**

```bash
git add frontend/ 
git commit -m "chore: scaffold de frontend Next.js + TS + Tailwind + shadcn/ui + TanStack Query + Vitest"
```

---

### Task 2: Cliente de API — tipos, sesión y wrapper de fetch

**Files:**
- Create: `frontend/types/api.ts`
- Create: `frontend/lib/auth.ts`
- Create: `frontend/lib/auth.test.ts`
- Create: `frontend/lib/api-client.ts`
- Create: `frontend/lib/api-client.test.ts`

**Interfaces:**
- Consumes: ninguno (primera pieza de lógica del proyecto).
- Produces: `types/api.ts` exporta `LoginResponse`, `EmpresaResumen`, `Empresa`, `AgregarEmpresaRequest`, `AgregarEmpresaResponse`, `RiesgoAbierto`, `ResumenRiesgos`, `Indicadores`, `TendenciaScore`, `DashboardData`, `CedulaIva`. `lib/auth.ts` exporta `saveSession(login: LoginResponse): Session`, `loadSession(): Session | null`, `clearSession(): void`, `getToken(): string | null`. `lib/api-client.ts` exporta `apiFetch<T>(path: string, options?: RequestInit): Promise<T>` y la clase `ApiError` (`status: number`, `message: string`, `fieldErrors?: Record<string, string>`).

- [ ] **Step 1: Escribir los tipos de la API**

```ts
// frontend/types/api.ts
export interface EmpresaResumen {
  empresa_id: string;
  rfc: string;
  razon_social: string;
  regimen_fiscal: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  nombre: string | null;
  empresas: EmpresaResumen[];
}

export interface Empresa {
  id: string;
  rfc: string;
  razon_social: string;
  regimen_fiscal: string | null;
  cp_fiscal: string | null;
  curp: string | null;
  obligaciones: string[] | null;
  representante_legal: string | null;
  rfc_representante: string | null;
  activo: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgregarEmpresaRequest {
  rfc: string;
  razon_social: string;
  regimen_fiscal?: string;
  cp_fiscal?: string;
  curp?: string;
  obligaciones?: string[];
  representante_legal?: string;
  rfc_representante?: string;
}

export interface AgregarEmpresaResponse {
  mensaje: string;
  empresa_id: string;
  rfc: string;
  razon_social: string;
}

export interface RiesgoAbierto {
  id: string;
  codigo: string;
  nombre: string;
  severidad: "critico" | "alto" | "medio" | "bajo";
  monto_afectado: number | null;
  descripcion: string | null;
  cfdi_id: string | null;
  movimiento_id: string | null;
  estado: string;
  periodo: string;
  created_at: string;
}

export interface ResumenRiesgos {
  critico: number;
  alto: number;
  medio: number;
  bajo: number;
  monto_total_en_riesgo: number;
}

export interface Indicadores {
  ingresos_cfdi?: number;
  egresos_cfdi?: number;
  depositos_banco?: number;
  cargos_banco?: number;
  brecha_ingresos?: number;
  brecha_egresos?: number;
  pct_conciliacion?: number;
}

export interface TendenciaScore {
  periodo: string;
  score: number;
}

export interface DashboardData {
  empresa: Empresa;
  score_actual: Record<string, unknown> | null;
  riesgos_abiertos: RiesgoAbierto[];
  resumen_riesgos: ResumenRiesgos;
  tendencia_score: TendenciaScore[];
  indicadores: Indicadores;
}

export interface IvaDesglose {
  base: number;
  iva: number;
}

export interface TrasladadoIva {
  pue: IvaDesglose;
  ppd: { cobrado: number; iva: number };
  notas_credito: IvaDesglose;
  total: number;
}

export interface AcreditableIva {
  pue: IvaDesglose;
  ppd: { pagado: number; iva: number };
  notas_credito: IvaDesglose;
  excluido_efectivo: { iva: number };
  bruto: number;
  factor_prorrateo: number;
  ajustado: number;
}

export interface ResultadoIva {
  iva_por_pagar: number;
  saldo_a_cargo: number;
  saldo_a_favor: number;
}

export interface ComparativoSat {
  diot_iva_pagado: number;
  diferencia: number;
}

export interface CedulaIva {
  empresa_id: string;
  periodo: string;
  trasladado: TrasladadoIva;
  acreditable: AcreditableIva;
  iva_retenido: number;
  resultado: ResultadoIva;
  comparativo_sat: ComparativoSat;
}
```

- [ ] **Step 2: Escribir la prueba de `lib/auth.ts` (debe fallar — el módulo no existe)**

```ts
// frontend/lib/auth.test.ts
import { describe, it, expect, beforeEach } from "vitest";
import { saveSession, loadSession, clearSession, getToken } from "./auth";
import type { LoginResponse } from "@/types/api";

const loginResponse: LoginResponse = {
  access_token: "abc123",
  token_type: "bearer",
  user_id: "u1",
  email: "test@example.com",
  nombre: "Test",
  empresas: [],
};

describe("auth session storage", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("saves and loads a session", () => {
    saveSession(loginResponse);
    const session = loadSession();
    expect(session?.accessToken).toBe("abc123");
    expect(session?.email).toBe("test@example.com");
  });

  it("returns null when there is no session", () => {
    expect(loadSession()).toBeNull();
  });

  it("clears the session", () => {
    saveSession(loginResponse);
    clearSession();
    expect(loadSession()).toBeNull();
  });

  it("getToken returns the stored token", () => {
    saveSession(loginResponse);
    expect(getToken()).toBe("abc123");
  });

  it("getToken returns null without a session", () => {
    expect(getToken()).toBeNull();
  });
});
```

Run: `cd frontend && npx vitest run lib/auth.test.ts`
Expected: FAIL — `Cannot find module './auth'`

- [ ] **Step 3: Implementar `lib/auth.ts`**

```ts
// frontend/lib/auth.ts
import type { LoginResponse } from "@/types/api";

const STORAGE_KEY = "fiscalcore.session";

export interface Session {
  accessToken: string;
  userId: string;
  email: string;
  nombre: string | null;
  empresas: LoginResponse["empresas"];
}

export function saveSession(login: LoginResponse): Session {
  const session: Session = {
    accessToken: login.access_token,
    userId: login.user_id,
    email: login.email,
    nombre: login.nombre,
    empresas: login.empresas,
  };
  window.localStorage.setItem(STORAGE_KEY, JSON.stringify(session));
  return session;
}

export function loadSession(): Session | null {
  const raw = window.localStorage.getItem(STORAGE_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as Session;
  } catch {
    return null;
  }
}

export function clearSession(): void {
  window.localStorage.removeItem(STORAGE_KEY);
}

export function getToken(): string | null {
  return loadSession()?.accessToken ?? null;
}
```

Run: `cd frontend && npx vitest run lib/auth.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 4: Escribir la prueba de `lib/api-client.ts` (debe fallar)**

```ts
// frontend/lib/api-client.test.ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { apiFetch, ApiError } from "./api-client";
import { saveSession, getToken } from "./auth";
import type { LoginResponse } from "@/types/api";

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "test@example.com",
  nombre: "Test",
  empresas: [],
};

function mockResponse(status: number, body: unknown) {
  return {
    ok: status >= 200 && status < 300,
    status,
    statusText: "error",
    json: async () => body,
  };
}

describe("apiFetch", () => {
  beforeEach(() => {
    process.env.NEXT_PUBLIC_API_URL = "http://localhost:8000";
    window.localStorage.clear();
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("adds the Authorization header when there is a session", async () => {
    saveSession(loginResponse);
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/v1/empresas");

    const [, options] = fetchMock.mock.calls[0];
    expect((options.headers as Record<string, string>)["Authorization"]).toBe(
      "Bearer token-123",
    );
  });

  it("does not add an Authorization header without a session", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/v1/empresas");

    const [, options] = fetchMock.mock.calls[0];
    expect(
      (options.headers as Record<string, string>)["Authorization"],
    ).toBeUndefined();
  });

  it("throws ApiError with the backend detail on a non-2xx response", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockResponse(401, { detail: "Credenciales incorrectas" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/auth/login")).rejects.toMatchObject({
      status: 401,
      message: "Credenciales incorrectas",
    });
  });

  it("clears the session when the response is 401", async () => {
    saveSession(loginResponse);
    const fetchMock = vi
      .fn()
      .mockResolvedValue(mockResponse(401, { detail: "no autorizado" }));
    vi.stubGlobal("fetch", fetchMock);

    await expect(apiFetch("/api/v1/auth/me")).rejects.toBeInstanceOf(ApiError);
    expect(getToken()).toBeNull();
  });

  it("maps 422 validation errors to field errors", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      mockResponse(422, {
        detail: [{ loc: ["body", "rfc"], msg: "campo requerido" }],
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    try {
      await apiFetch("/api/v1/mis-empresas", { method: "POST" });
      throw new Error("no debería llegar aquí");
    } catch (err) {
      expect(err).toBeInstanceOf(ApiError);
      expect((err as ApiError).fieldErrors).toEqual({ rfc: "campo requerido" });
    }
  });
});
```

Run: `cd frontend && npx vitest run lib/api-client.test.ts`
Expected: FAIL — `Cannot find module './api-client'`

- [ ] **Step 5: Implementar `lib/api-client.ts`**

```ts
// frontend/lib/api-client.ts
import { getToken, clearSession } from "./auth";

export class ApiError extends Error {
  status: number;
  fieldErrors?: Record<string, string>;

  constructor(status: number, message: string, fieldErrors?: Record<string, string>) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.fieldErrors = fieldErrors;
  }
}

function apiBaseUrl(): string {
  const url = process.env.NEXT_PUBLIC_API_URL;
  if (!url) {
    throw new Error("NEXT_PUBLIC_API_URL no está configurada");
  }
  return url;
}

function parseFieldErrors(detail: unknown): Record<string, string> | undefined {
  if (!Array.isArray(detail)) return undefined;
  const fieldErrors: Record<string, string> = {};
  for (const item of detail) {
    if (item && typeof item === "object" && "loc" in item && "msg" in item) {
      const loc = (item as { loc: unknown[] }).loc;
      const field = String(loc[loc.length - 1]);
      fieldErrors[field] = String((item as { msg: unknown }).msg);
    }
  }
  return Object.keys(fieldErrors).length > 0 ? fieldErrors : undefined;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...options,
    headers,
  });

  if (response.status === 401) {
    clearSession();
  }

  if (!response.ok) {
    let detail: unknown = response.statusText;
    try {
      const body = await response.json();
      detail = body.detail ?? detail;
    } catch {
      // respuesta sin cuerpo JSON, se usa statusText
    }
    const fieldErrors = parseFieldErrors(detail);
    const message = typeof detail === "string" ? detail : "Solicitud inválida";
    throw new ApiError(response.status, message, fieldErrors);
  }

  if (response.status === 204) {
    return undefined as T;
  }

  return (await response.json()) as T;
}
```

Run: `cd frontend && npx vitest run lib/api-client.test.ts`
Expected: PASS (5 tests)

- [ ] **Step 6: Correr toda la suite y commitear**

Run: `cd frontend && npm test`
Expected: PASS (10 tests: 5 de `auth.test.ts` + 5 de `api-client.test.ts`)

```bash
git add frontend/types/api.ts frontend/lib/auth.ts frontend/lib/auth.test.ts frontend/lib/api-client.ts frontend/lib/api-client.test.ts
git commit -m "feat: cliente de API — tipos, sesión en localStorage y wrapper de fetch"
```

---

### Task 3: Proveedor de TanStack Query con logout global en 401

**Files:**
- Create: `frontend/lib/query-client.ts`
- Create: `frontend/lib/query-client.test.tsx`
- Create: `frontend/components/providers/QueryProvider.tsx`
- Modify: `frontend/app/layout.tsx`

**Interfaces:**
- Consumes: `ApiError` de `lib/api-client.ts` (Task 2); `clearSession` de `lib/auth.ts` (Task 2).
- Produces: `createQueryClient(onUnauthorized: () => void): QueryClient` en `lib/query-client.ts`; componente `QueryProvider({ children })` que envuelve la app y redirige a `/login` en cualquier error 401.

- [ ] **Step 1: Escribir la prueba de `createQueryClient` (debe fallar)**

```tsx
// frontend/lib/query-client.test.tsx
import { describe, expect, it, vi } from "vitest";
import { createQueryClient } from "./query-client";
import { ApiError } from "./api-client";
import { saveSession, getToken } from "./auth";
import type { LoginResponse } from "@/types/api";

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "test@example.com",
  nombre: "Test",
  empresas: [],
};

describe("createQueryClient", () => {
  it("clears the session and calls onUnauthorized on a 401 ApiError", async () => {
    saveSession(loginResponse);
    const onUnauthorized = vi.fn();
    const queryClient = createQueryClient(onUnauthorized);

    await queryClient
      .fetchQuery({
        queryKey: ["boom"],
        queryFn: () => {
          throw new ApiError(401, "no autorizado");
        },
      })
      .catch(() => undefined);

    expect(onUnauthorized).toHaveBeenCalledTimes(1);
    expect(getToken()).toBeNull();
  });

  it("does not call onUnauthorized for non-401 errors", async () => {
    const onUnauthorized = vi.fn();
    const queryClient = createQueryClient(onUnauthorized);

    await queryClient
      .fetchQuery({
        queryKey: ["boom-500"],
        queryFn: () => {
          throw new ApiError(500, "error de servidor");
        },
      })
      .catch(() => undefined);

    expect(onUnauthorized).not.toHaveBeenCalled();
  });
});
```

Run: `cd frontend && npx vitest run lib/query-client.test.tsx`
Expected: FAIL — `Cannot find module './query-client'`

- [ ] **Step 2: Implementar `lib/query-client.ts`**

```ts
// frontend/lib/query-client.ts
import { QueryCache, QueryClient } from "@tanstack/react-query";
import { ApiError } from "./api-client";
import { clearSession } from "./auth";

export function createQueryClient(onUnauthorized: () => void): QueryClient {
  return new QueryClient({
    queryCache: new QueryCache({
      onError: (error) => {
        if (error instanceof ApiError && error.status === 401) {
          clearSession();
          onUnauthorized();
        }
      },
    }),
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
      },
    },
  });
}
```

Run: `cd frontend && npx vitest run lib/query-client.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 3: Implementar `components/providers/QueryProvider.tsx`**

```tsx
// frontend/components/providers/QueryProvider.tsx
"use client";

import { useRouter } from "next/navigation";
import { QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";
import { createQueryClient } from "@/lib/query-client";

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const router = useRouter();
  const [queryClient] = useState(() =>
    createQueryClient(() => router.replace("/login")),
  );

  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}
```

- [ ] **Step 4: Envolver la app en `app/layout.tsx`**

Editar `frontend/app/layout.tsx` para que el `<body>` envuelva `{children}` con `<QueryProvider>`:

```tsx
import type { Metadata } from "next";
import "./globals.css";
import { QueryProvider } from "@/components/providers/QueryProvider";

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
    <html lang="es">
      <body>
        <QueryProvider>{children}</QueryProvider>
      </body>
    </html>
  );
}
```

- [ ] **Step 5: Verificar build y commitear**

Run: `cd frontend && npm run build`
Expected: build exitoso

```bash
git add frontend/lib/query-client.ts frontend/lib/query-client.test.tsx frontend/components/providers/QueryProvider.tsx frontend/app/layout.tsx
git commit -m "feat: proveedor de TanStack Query con logout global en 401"
```

---

### Task 4: AuthGuard y layout protegido

**Files:**
- Create: `frontend/components/auth/AuthGuard.tsx`
- Create: `frontend/components/auth/AuthGuard.test.tsx`
- Create: `frontend/app/(app)/layout.tsx`

**Interfaces:**
- Consumes: `getToken`, `clearSession` de `lib/auth.ts`; `apiFetch`, `ApiError` de `lib/api-client.ts` (Task 2).
- Produces: componente `AuthGuard({ children })` — sin token, redirige a `/login`; con token inválido (401 en `GET /api/v1/auth/me`), limpia sesión y redirige a `/login`; con token válido, renderiza `children`. Cualquier página bajo `app/(app)/` queda protegida automáticamente por el layout.

- [ ] **Step 1: Escribir la prueba de `AuthGuard` (debe fallar)**

```tsx
// frontend/components/auth/AuthGuard.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import { AuthGuard } from "./AuthGuard";
import { saveSession, getToken } from "@/lib/auth";
import type { LoginResponse } from "@/types/api";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "test@example.com",
  nombre: "Test",
  empresas: [],
};

describe("AuthGuard", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    vi.mocked(apiFetch).mockReset();
    window.localStorage.clear();
  });

  it("redirects to /login when there is no session", async () => {
    render(
      <AuthGuard>
        <div>contenido protegido</div>
      </AuthGuard>,
    );

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    expect(screen.queryByText("contenido protegido")).not.toBeInTheDocument();
  });

  it("renders children when the session is valid", async () => {
    saveSession(loginResponse);
    vi.mocked(apiFetch).mockResolvedValue({ user_id: "u1" });

    render(
      <AuthGuard>
        <div>contenido protegido</div>
      </AuthGuard>,
    );

    await waitFor(() =>
      expect(screen.getByText("contenido protegido")).toBeInTheDocument(),
    );
  });

  it("clears the session and redirects when /auth/me responds 401", async () => {
    saveSession(loginResponse);
    vi.mocked(apiFetch).mockRejectedValue(new ApiError(401, "no autorizado"));

    render(
      <AuthGuard>
        <div>contenido protegido</div>
      </AuthGuard>,
    );

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
    expect(getToken()).toBeNull();
  });
});
```

Run: `cd frontend && npx vitest run components/auth/AuthGuard.test.tsx`
Expected: FAIL — `Cannot find module './AuthGuard'`

- [ ] **Step 2: Implementar `AuthGuard.tsx`**

```tsx
// frontend/components/auth/AuthGuard.tsx
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

Run: `cd frontend && npx vitest run components/auth/AuthGuard.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 3: Crear el layout protegido**

```tsx
// frontend/app/(app)/layout.tsx
import { AuthGuard } from "@/components/auth/AuthGuard";

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <AuthGuard>{children}</AuthGuard>;
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/components/auth/AuthGuard.tsx frontend/components/auth/AuthGuard.test.tsx "frontend/app/(app)/layout.tsx"
git commit -m "feat: AuthGuard y layout protegido para las páginas autenticadas"
```

---

### Task 5: Página de login

**Files:**
- Create: `frontend/hooks/useLogin.ts`
- Create: `frontend/app/login/page.tsx`
- Create: `frontend/app/login/page.test.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `ApiError` de `lib/api-client.ts`; `saveSession` de `lib/auth.ts`; `LoginResponse` de `types/api.ts`; componentes `Button`, `Input`, `Label` de `@/components/ui/*` (Task 1).
- Produces: hook `useLogin()` (mutación de TanStack Query); página `/login` que autentica y redirige a `/empresas`.

- [ ] **Step 1: Implementar `hooks/useLogin.ts`**

```ts
// frontend/hooks/useLogin.ts
"use client";

import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { saveSession } from "@/lib/auth";
import type { LoginResponse } from "@/types/api";

interface LoginInput {
  email: string;
  password: string;
}

export function useLogin() {
  return useMutation({
    mutationFn: async (input: LoginInput) => {
      const response = await apiFetch<LoginResponse>("/api/v1/auth/login", {
        method: "POST",
        body: JSON.stringify(input),
      });
      saveSession(response);
      return response;
    },
  });
}
```

- [ ] **Step 2: Escribir la prueba de la página de login (debe fallar)**

```tsx
// frontend/app/login/page.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LoginPage from "./page";
import { getToken } from "@/lib/auth";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

function renderLoginPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LoginPage />
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    vi.mocked(apiFetch).mockReset();
    window.localStorage.clear();
  });

  it("shows a validation error when fields are empty", async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await user.click(screen.getByRole("button", { name: /entrar/i }));

    expect(
      screen.getByText("Correo y contraseña son obligatorios"),
    ).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("logs in and redirects to /empresas on success", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      access_token: "token-123",
      token_type: "bearer",
      user_id: "u1",
      email: "test@example.com",
      nombre: "Test",
      empresas: [],
    });
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Correo"), "test@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "secreto123");
    await user.click(screen.getByRole("button", { name: /entrar/i }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/empresas"));
    expect(getToken()).toBe("token-123");
  });

  it("shows the backend error message on invalid credentials", async () => {
    const { ApiError } = await import("@/lib/api-client");
    vi.mocked(apiFetch).mockRejectedValue(
      new ApiError(401, "Credenciales incorrectas"),
    );
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Correo"), "test@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "mala-clave");
    await user.click(screen.getByRole("button", { name: /entrar/i }));

    await waitFor(() =>
      expect(screen.getByText("Credenciales incorrectas")).toBeInTheDocument(),
    );
  });
});
```

Run: `cd frontend && npx vitest run app/login/page.test.tsx`
Expected: FAIL — `Cannot find module './page'`

- [ ] **Step 3: Implementar `app/login/page.tsx`**

```tsx
// frontend/app/login/page.tsx
"use client";

import { FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useLogin } from "@/hooks/useLogin";
import { ApiError } from "@/lib/api-client";

export default function LoginPage() {
  const router = useRouter();
  const login = useLogin();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);

    if (!email || !password) {
      setFormError("Correo y contraseña son obligatorios");
      return;
    }

    try {
      await login.mutateAsync({ email, password });
      router.replace("/empresas");
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("No se pudo iniciar sesión, intenta de nuevo");
      }
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <form
        onSubmit={handleSubmit}
        className="w-full max-w-sm space-y-4 rounded-lg border p-6"
      >
        <h1 className="text-xl font-semibold">Iniciar sesión</h1>

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
          <p role="alert" className="text-sm text-red-600">
            {formError}
          </p>
        )}

        <Button type="submit" className="w-full" disabled={login.isPending}>
          {login.isPending ? "Entrando..." : "Entrar"}
        </Button>
      </form>
    </main>
  );
}
```

Run: `cd frontend && npx vitest run app/login/page.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 4: Commit**

```bash
git add frontend/hooks/useLogin.ts frontend/app/login/page.tsx frontend/app/login/page.test.tsx
git commit -m "feat: página de login"
```

---

### Task 6: Empresas — alta, listado y ErrorState compartido

**Files:**
- Create: `frontend/components/shared/ErrorState.tsx`
- Create: `frontend/hooks/useEmpresas.ts`
- Create: `frontend/components/empresas/EmpresaForm.tsx`
- Create: `frontend/components/empresas/EmpresaForm.test.tsx`
- Create: `frontend/components/empresas/EmpresaList.tsx`
- Create: `frontend/app/(app)/empresas/page.tsx`

**Interfaces:**
- Consumes: `apiFetch`, `ApiError` de `lib/api-client.ts`; `AgregarEmpresaRequest`, `AgregarEmpresaResponse`, `Empresa` de `types/api.ts`; componentes `Button`, `Input`, `Label` de `@/components/ui/*`.
- Produces: `useEmpresas()` (query `['empresas']` → `Empresa[]`), `useCrearEmpresa()` (mutación que invalida `['empresas']`); componente `ErrorState({ message, onRetry? })` reutilizado por las tasks 7 y 8; página `/empresas`.

- [ ] **Step 1: Implementar `ErrorState.tsx`**

```tsx
// frontend/components/shared/ErrorState.tsx
export function ErrorState({
  message,
  onRetry,
}: {
  message: string;
  onRetry?: () => void;
}) {
  return (
    <div
      role="alert"
      className="rounded-md border border-red-300 bg-red-50 p-4 text-sm text-red-700"
    >
      <p>{message}</p>
      {onRetry && (
        <button type="button" onClick={onRetry} className="mt-2 font-medium underline">
          Reintentar
        </button>
      )}
    </div>
  );
}
```

- [ ] **Step 2: Implementar `hooks/useEmpresas.ts`**

```ts
// frontend/hooks/useEmpresas.ts
"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type {
  AgregarEmpresaRequest,
  AgregarEmpresaResponse,
  Empresa,
} from "@/types/api";

export function useEmpresas() {
  return useQuery({
    queryKey: ["empresas"],
    queryFn: () => apiFetch<Empresa[]>("/api/v1/empresas"),
  });
}

export function useCrearEmpresa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AgregarEmpresaRequest) =>
      apiFetch<AgregarEmpresaResponse>("/api/v1/mis-empresas", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["empresas"] });
    },
  });
}
```

- [ ] **Step 3: Escribir la prueba de `EmpresaForm` (debe fallar)**

```tsx
// frontend/components/empresas/EmpresaForm.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EmpresaForm } from "./EmpresaForm";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

function renderForm(onCreated = vi.fn()) {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <EmpresaForm onCreated={onCreated} />
    </QueryClientProvider>,
  );
  return { onCreated };
}

describe("EmpresaForm", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("shows required-field errors and does not call the API", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(screen.getByText("El RFC es obligatorio")).toBeInTheDocument();
    expect(screen.getByText("La razón social es obligatoria")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("rejects an RFC with an invalid length", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("RFC"), "ABC123");
    await user.type(screen.getByLabelText("Razón social"), "Acme SA de CV");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(
      screen.getByText("El RFC debe tener 12 o 13 caracteres"),
    ).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("submits and calls onCreated on success", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      mensaje: "Empresa vinculada correctamente",
      empresa_id: "e1",
      rfc: "AAA010101AAA",
      razon_social: "Acme SA de CV",
    });
    const user = userEvent.setup();
    const { onCreated } = renderForm();

    await user.type(screen.getByLabelText("RFC"), "aaa010101aaa");
    await user.type(screen.getByLabelText("Razón social"), "Acme SA de CV");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1));
    const [, options] = vi.mocked(apiFetch).mock.calls[0];
    expect(JSON.parse((options as RequestInit).body as string)).toEqual({
      rfc: "AAA010101AAA",
      razon_social: "Acme SA de CV",
    });
  });

  it("shows field errors returned by the backend", async () => {
    vi.mocked(apiFetch).mockRejectedValue(
      new ApiError(422, "Solicitud inválida", { rfc: "RFC ya registrado" }),
    );
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("RFC"), "aaa010101aaa");
    await user.type(screen.getByLabelText("Razón social"), "Acme SA de CV");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    await waitFor(() =>
      expect(screen.getByText("RFC ya registrado")).toBeInTheDocument(),
    );
  });
});
```

Run: `cd frontend && npx vitest run components/empresas/EmpresaForm.test.tsx`
Expected: FAIL — `Cannot find module './EmpresaForm'`

- [ ] **Step 4: Implementar `EmpresaForm.tsx`**

```tsx
// frontend/components/empresas/EmpresaForm.tsx
"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useCrearEmpresa } from "@/hooks/useEmpresas";
import { ApiError } from "@/lib/api-client";

interface FieldErrors {
  rfc?: string;
  razon_social?: string;
}

export function EmpresaForm({ onCreated }: { onCreated?: () => void }) {
  const crearEmpresa = useCrearEmpresa();
  const [rfc, setRfc] = useState("");
  const [razonSocial, setRazonSocial] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);

  function validar(): boolean {
    const errors: FieldErrors = {};
    const rfcNormalizado = rfc.trim().toUpperCase();
    if (!rfcNormalizado) {
      errors.rfc = "El RFC es obligatorio";
    } else if (rfcNormalizado.length < 12 || rfcNormalizado.length > 13) {
      errors.rfc = "El RFC debe tener 12 o 13 caracteres";
    }
    if (!razonSocial.trim()) {
      errors.razon_social = "La razón social es obligatoria";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    if (!validar()) return;

    try {
      await crearEmpresa.mutateAsync({
        rfc: rfc.trim().toUpperCase(),
        razon_social: razonSocial.trim(),
      });
      setRfc("");
      setRazonSocial("");
      setFieldErrors({});
      onCreated?.();
    } catch (err) {
      if (err instanceof ApiError) {
        setFieldErrors((err.fieldErrors as FieldErrors) ?? {});
        setFormError(err.fieldErrors ? null : err.message);
      } else {
        setFormError("No se pudo dar de alta la empresa, intenta de nuevo");
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border p-4">
      <h2 className="text-lg font-semibold">Agregar empresa</h2>

      <div className="space-y-2">
        <Label htmlFor="rfc">RFC</Label>
        <Input id="rfc" value={rfc} onChange={(e) => setRfc(e.target.value)} />
        {fieldErrors.rfc && (
          <p role="alert" className="text-sm text-red-600">
            {fieldErrors.rfc}
          </p>
        )}
      </div>

      <div className="space-y-2">
        <Label htmlFor="razon_social">Razón social</Label>
        <Input
          id="razon_social"
          value={razonSocial}
          onChange={(e) => setRazonSocial(e.target.value)}
        />
        {fieldErrors.razon_social && (
          <p role="alert" className="text-sm text-red-600">
            {fieldErrors.razon_social}
          </p>
        )}
      </div>

      {formError && (
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}

      <Button type="submit" disabled={crearEmpresa.isPending}>
        {crearEmpresa.isPending ? "Guardando..." : "Guardar"}
      </Button>
    </form>
  );
}
```

Run: `cd frontend && npx vitest run components/empresas/EmpresaForm.test.tsx`
Expected: PASS (4 tests)

- [ ] **Step 5: Implementar `EmpresaList.tsx`**

```tsx
// frontend/components/empresas/EmpresaList.tsx
import Link from "next/link";
import type { Empresa } from "@/types/api";

export function EmpresaList({ empresas }: { empresas: Empresa[] }) {
  if (empresas.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        Aún no hay empresas registradas.
      </p>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left">
          <th className="py-2">RFC</th>
          <th className="py-2">Razón social</th>
          <th className="py-2">Régimen fiscal</th>
          <th className="py-2"></th>
        </tr>
      </thead>
      <tbody>
        {empresas.map((empresa) => (
          <tr key={empresa.id} className="border-b">
            <td className="py-2">{empresa.rfc}</td>
            <td className="py-2">{empresa.razon_social}</td>
            <td className="py-2">{empresa.regimen_fiscal ?? "—"}</td>
            <td className="py-2">
              <Link
                className="text-blue-600 hover:underline"
                href={`/empresas/${empresa.id}/cedula-iva`}
              >
                Cédula de IVA
              </Link>
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

- [ ] **Step 6: Implementar la página `/empresas`**

```tsx
// frontend/app/(app)/empresas/page.tsx
"use client";

import { EmpresaForm } from "@/components/empresas/EmpresaForm";
import { EmpresaList } from "@/components/empresas/EmpresaList";
import { ErrorState } from "@/components/shared/ErrorState";
import { useEmpresas } from "@/hooks/useEmpresas";

export default function EmpresasPage() {
  const { data: empresas, isLoading, isError, refetch } = useEmpresas();

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Empresas</h1>

      <EmpresaForm />

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

- [ ] **Step 7: Correr toda la suite y commitear**

Run: `cd frontend && npm test`
Expected: PASS (todas las pruebas anteriores + las 4 nuevas de `EmpresaForm`)

```bash
git add frontend/components/shared/ErrorState.tsx frontend/hooks/useEmpresas.ts frontend/components/empresas/ "frontend/app/(app)/empresas/page.tsx"
git commit -m "feat: alta y listado de empresas"
```

---

### Task 7: Dashboard

**Files:**
- Create: `frontend/hooks/useDashboard.ts`
- Create: `frontend/hooks/useDashboard.test.tsx`
- Create: `frontend/components/dashboard/ResumenRiesgos.tsx`
- Create: `frontend/components/dashboard/RiesgosTable.tsx`
- Create: `frontend/components/dashboard/RiesgosTable.test.tsx`
- Create: `frontend/app/(app)/dashboard/page.tsx`

**Interfaces:**
- Consumes: `apiFetch` de `lib/api-client.ts`; `DashboardData`, `ResumenRiesgos` (tipo), `RiesgoAbierto` de `types/api.ts`; `useEmpresas()` de `hooks/useEmpresas.ts` (Task 6); `ErrorState` de `components/shared/ErrorState.tsx` (Task 6); `Input`, `Label` de `@/components/ui/*`.
- Produces: `useDashboard(empresaId: string | undefined, periodo: string)`; página `/dashboard`.

- [ ] **Step 1: Escribir la prueba de `useDashboard` (debe fallar)**

```tsx
// frontend/hooks/useDashboard.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useDashboard } from "./useDashboard";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient();
  return (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
}

describe("useDashboard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("does not fetch when there is no empresaId", () => {
    renderHook(() => useDashboard(undefined, ""), { wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("fetches without a periodo query param when periodo is empty", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useDashboard("empresa-1", ""), { wrapper });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/v1/dashboard/empresa-1"),
    );
  });

  it("fetches with a periodo query param when periodo is set", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useDashboard("empresa-1", "2026-07"), { wrapper });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        "/api/v1/dashboard/empresa-1?periodo=2026-07",
      ),
    );
  });
});
```

Run: `cd frontend && npx vitest run hooks/useDashboard.test.tsx`
Expected: FAIL — `Cannot find module './useDashboard'`

- [ ] **Step 2: Implementar `hooks/useDashboard.ts`**

```ts
// frontend/hooks/useDashboard.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { DashboardData } from "@/types/api";

export function useDashboard(empresaId: string | undefined, periodo: string) {
  return useQuery({
    queryKey: ["dashboard", empresaId, periodo],
    queryFn: () =>
      apiFetch<DashboardData>(
        `/api/v1/dashboard/${empresaId}${periodo ? `?periodo=${periodo}` : ""}`,
      ),
    enabled: Boolean(empresaId),
  });
}
```

Run: `cd frontend && npx vitest run hooks/useDashboard.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 3: Escribir la prueba de `RiesgosTable` (debe fallar)**

```tsx
// frontend/components/dashboard/RiesgosTable.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiesgosTable } from "./RiesgosTable";
import type { RiesgoAbierto } from "@/types/api";

const riesgo: RiesgoAbierto = {
  id: "r1",
  codigo: "R001",
  nombre: "Brecha de ingresos",
  severidad: "alto",
  monto_afectado: 12345.67,
  descripcion: "Depósitos bancarios sin CFDI",
  cfdi_id: null,
  movimiento_id: "m1",
  estado: "abierto",
  periodo: "2026-07",
  created_at: "2026-07-01T00:00:00Z",
};

describe("RiesgosTable", () => {
  it("shows an empty state message when there are no risks", () => {
    render(<RiesgosTable riesgos={[]} />);
    expect(
      screen.getByText("No hay riesgos abiertos en este periodo."),
    ).toBeInTheDocument();
  });

  it("renders a row per risk", () => {
    render(<RiesgosTable riesgos={[riesgo]} />);
    expect(screen.getByText("Brecha de ingresos")).toBeInTheDocument();
    expect(screen.getByText("Depósitos bancarios sin CFDI")).toBeInTheDocument();
  });
});
```

Run: `cd frontend && npx vitest run components/dashboard/RiesgosTable.test.tsx`
Expected: FAIL — `Cannot find module './RiesgosTable'`

- [ ] **Step 4: Implementar `RiesgosTable.tsx` y `ResumenRiesgos.tsx`**

```tsx
// frontend/components/dashboard/RiesgosTable.tsx
import type { RiesgoAbierto } from "@/types/api";

export function RiesgosTable({ riesgos }: { riesgos: RiesgoAbierto[] }) {
  if (riesgos.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No hay riesgos abiertos en este periodo.
      </p>
    );
  }

  return (
    <table className="w-full text-sm">
      <thead>
        <tr className="border-b text-left">
          <th className="py-2">Severidad</th>
          <th className="py-2">Riesgo</th>
          <th className="py-2">Monto afectado</th>
          <th className="py-2">Descripción</th>
        </tr>
      </thead>
      <tbody>
        {riesgos.map((riesgo) => (
          <tr key={riesgo.id} className="border-b">
            <td className="py-2 capitalize">{riesgo.severidad}</td>
            <td className="py-2">{riesgo.nombre}</td>
            <td className="py-2">
              {riesgo.monto_afectado != null
                ? `$${riesgo.monto_afectado.toLocaleString("es-MX")}`
                : "—"}
            </td>
            <td className="py-2">{riesgo.descripcion ?? "—"}</td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

```tsx
// frontend/components/dashboard/ResumenRiesgos.tsx
import type { ResumenRiesgos as ResumenRiesgosType } from "@/types/api";

export function ResumenRiesgos({ resumen }: { resumen: ResumenRiesgosType }) {
  const items = [
    { label: "Críticos", value: resumen.critico },
    { label: "Altos", value: resumen.alto },
    { label: "Medios", value: resumen.medio },
    { label: "Bajos", value: resumen.bajo },
  ];

  return (
    <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
      {items.map((item) => (
        <div key={item.label} className="rounded-lg border p-4 text-center">
          <p className="text-2xl font-semibold">{item.value}</p>
          <p className="text-sm text-muted-foreground">{item.label}</p>
        </div>
      ))}
      <div className="col-span-2 rounded-lg border p-4 text-center sm:col-span-4">
        <p className="text-2xl font-semibold">
          ${resumen.monto_total_en_riesgo.toLocaleString("es-MX")}
        </p>
        <p className="text-sm text-muted-foreground">Monto total en riesgo</p>
      </div>
    </div>
  );
}
```

Run: `cd frontend && npx vitest run components/dashboard/RiesgosTable.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 5: Implementar la página `/dashboard`**

```tsx
// frontend/app/(app)/dashboard/page.tsx
"use client";

import { useState } from "react";
import { useEmpresas } from "@/hooks/useEmpresas";
import { useDashboard } from "@/hooks/useDashboard";
import { ResumenRiesgos } from "@/components/dashboard/ResumenRiesgos";
import { RiesgosTable } from "@/components/dashboard/RiesgosTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function DashboardPage() {
  const { data: empresas } = useEmpresas();
  const [empresaId, setEmpresaId] = useState<string>("");
  const [periodo, setPeriodo] = useState<string>("");

  const dashboard = useDashboard(empresaId || undefined, periodo);

  return (
    <main className="mx-auto max-w-4xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Dashboard</h1>

      <div className="flex flex-wrap gap-4">
        <div className="space-y-2">
          <Label htmlFor="empresa">Empresa</Label>
          <select
            id="empresa"
            className="rounded-md border p-2"
            value={empresaId}
            onChange={(e) => setEmpresaId(e.target.value)}
          >
            <option value="">Selecciona una empresa</option>
            {empresas?.map((empresa) => (
              <option key={empresa.id} value={empresa.id}>
                {empresa.razon_social}
              </option>
            ))}
          </select>
        </div>

        <div className="space-y-2">
          <Label htmlFor="periodo">Periodo (YYYY-MM)</Label>
          <Input
            id="periodo"
            placeholder="2026-07"
            value={periodo}
            onChange={(e) => setPeriodo(e.target.value)}
          />
        </div>
      </div>

      {!empresaId && <p>Selecciona una empresa para ver su dashboard.</p>}
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

- [ ] **Step 6: Correr toda la suite y commitear**

Run: `cd frontend && npm test`
Expected: PASS (todas las pruebas anteriores + las 5 nuevas de esta task)

```bash
git add frontend/hooks/useDashboard.ts frontend/hooks/useDashboard.test.tsx frontend/components/dashboard/ "frontend/app/(app)/dashboard/page.tsx"
git commit -m "feat: página de dashboard"
```

---

### Task 8: Cédula de IVA y redirección de la ruta raíz

**Files:**
- Create: `frontend/hooks/useCedulaIva.ts`
- Create: `frontend/components/cedula-iva/CedulaIvaTable.tsx`
- Create: `frontend/components/cedula-iva/CedulaIvaTable.test.tsx`
- Create: `frontend/app/(app)/empresas/[empresaId]/cedula-iva/page.tsx`
- Modify: `frontend/app/page.tsx`
- Create: `frontend/app/page.test.tsx`

**Interfaces:**
- Consumes: `apiFetch` de `lib/api-client.ts`; `CedulaIva` de `types/api.ts`; `getToken` de `lib/auth.ts`; `ErrorState` de `components/shared/ErrorState.tsx`; `Input`, `Label` de `@/components/ui/*`.
- Produces: `useCedulaIva(empresaId: string, periodo: string)`; página `/empresas/[empresaId]/cedula-iva`; página raíz `/` que redirige a `/empresas` o `/login` según haya sesión.

- [ ] **Step 1: Escribir la prueba de `CedulaIvaTable` (debe fallar)**

```tsx
// frontend/components/cedula-iva/CedulaIvaTable.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CedulaIvaTable } from "./CedulaIvaTable";
import type { CedulaIva } from "@/types/api";

const cedula: CedulaIva = {
  empresa_id: "e1",
  periodo: "2026-07",
  trasladado: {
    pue: { base: 1000, iva: 160 },
    ppd: { cobrado: 0, iva: 0 },
    notas_credito: { base: 0, iva: 0 },
    total: 160,
  },
  acreditable: {
    pue: { base: 500, iva: 80 },
    ppd: { pagado: 0, iva: 0 },
    notas_credito: { base: 0, iva: 0 },
    excluido_efectivo: { iva: 0 },
    bruto: 80,
    factor_prorrateo: 1,
    ajustado: 80,
  },
  iva_retenido: 0,
  resultado: {
    iva_por_pagar: 80,
    saldo_a_cargo: 80,
    saldo_a_favor: 0,
  },
  comparativo_sat: {
    diot_iva_pagado: 80,
    diferencia: 0,
  },
};

describe("CedulaIvaTable", () => {
  it("renders the key IVA amounts", () => {
    render(<CedulaIvaTable cedula={cedula} />);
    expect(screen.getByText("IVA trasladado (total)")).toBeInTheDocument();
    expect(screen.getByText("IVA por pagar")).toBeInTheDocument();
    expect(screen.getAllByText(/\$80\.00/).length).toBeGreaterThan(0);
  });
});
```

Run: `cd frontend && npx vitest run components/cedula-iva/CedulaIvaTable.test.tsx`
Expected: FAIL — `Cannot find module './CedulaIvaTable'`

- [ ] **Step 2: Implementar `useCedulaIva.ts` y `CedulaIvaTable.tsx`**

```ts
// frontend/hooks/useCedulaIva.ts
"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { CedulaIva } from "@/types/api";

export function useCedulaIva(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["cedula-iva", empresaId, periodo],
    queryFn: () =>
      apiFetch<CedulaIva>(`/api/v1/empresas/${empresaId}/cedula-iva/${periodo}`),
    enabled: Boolean(empresaId) && Boolean(periodo),
  });
}
```

```tsx
// frontend/components/cedula-iva/CedulaIvaTable.tsx
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
    <table className="w-full text-sm">
      <tbody>
        {filas.map(([label, value]) => (
          <tr key={label} className="border-b">
            <td className="py-2 font-medium">{label}</td>
            <td className="py-2 text-right">
              {label === "Factor de prorrateo" ? value : formatMoney(value)}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  );
}
```

Run: `cd frontend && npx vitest run components/cedula-iva/CedulaIvaTable.test.tsx`
Expected: PASS (1 test)

- [ ] **Step 3: Implementar la página `/empresas/[empresaId]/cedula-iva`**

```tsx
// frontend/app/(app)/empresas/[empresaId]/cedula-iva/page.tsx
"use client";

import { useParams } from "next/navigation";
import { useState } from "react";
import { useCedulaIva } from "@/hooks/useCedulaIva";
import { CedulaIvaTable } from "@/components/cedula-iva/CedulaIvaTable";
import { ErrorState } from "@/components/shared/ErrorState";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";

export default function CedulaIvaPage() {
  const params = useParams<{ empresaId: string }>();
  const [periodo, setPeriodo] = useState("");
  const cedula = useCedulaIva(params.empresaId, periodo);

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Cédula de IVA</h1>

      <div className="space-y-2">
        <Label htmlFor="periodo">Periodo (YYYY-MM)</Label>
        <Input
          id="periodo"
          placeholder="2026-07"
          value={periodo}
          onChange={(e) => setPeriodo(e.target.value)}
        />
      </div>

      {!periodo && <p>Ingresa un periodo para calcular la cédula.</p>}
      {cedula.isLoading && <p>Calculando cédula...</p>}
      {cedula.isError && (
        <ErrorState
          message="No se pudo calcular la cédula de IVA."
          onRetry={() => cedula.refetch()}
        />
      )}
      {cedula.data && <CedulaIvaTable cedula={cedula.data} />}
    </main>
  );
}
```

- [ ] **Step 4: Escribir la prueba de la redirección en la ruta raíz (debe fallar)**

```tsx
// frontend/app/page.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, waitFor } from "@testing-library/react";
import HomePage from "./page";
import { saveSession } from "@/lib/auth";
import type { LoginResponse } from "@/types/api";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "test@example.com",
  nombre: "Test",
  empresas: [],
};

describe("HomePage", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    window.localStorage.clear();
  });

  it("redirects to /login when there is no session", async () => {
    render(<HomePage />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/login"));
  });

  it("redirects to /empresas when there is a session", async () => {
    saveSession(loginResponse);
    render(<HomePage />);
    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/empresas"));
  });
});
```

Run: `cd frontend && npx vitest run app/page.test.tsx`
Expected: FAIL (el `page.tsx` generado por create-next-app no redirige)

- [ ] **Step 5: Reemplazar `app/page.tsx`**

```tsx
// frontend/app/page.tsx
"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import { getToken } from "@/lib/auth";

export default function HomePage() {
  const router = useRouter();

  useEffect(() => {
    router.replace(getToken() ? "/empresas" : "/login");
  }, [router]);

  return null;
}
```

Run: `cd frontend && npx vitest run app/page.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 6: Correr toda la suite completa, build y commitear**

Run: `cd frontend && npm test`
Expected: PASS (todas las pruebas de las 8 tasks)

Run: `cd frontend && npm run build`
Expected: build exitoso

```bash
git add frontend/hooks/useCedulaIva.ts frontend/components/cedula-iva/ "frontend/app/(app)/empresas/[empresaId]/cedula-iva/page.tsx" frontend/app/page.tsx frontend/app/page.test.tsx
git commit -m "feat: página de cédula de IVA y redirección de la ruta raíz"
```
