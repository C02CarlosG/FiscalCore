# Ingesta de CFDI y estado de cuenta (Fase 2a) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir, en la rama `feat/frontend-ingesta`, una página `/empresas/[empresaId]/ingesta` que permita subir CFDI (XML) y un estado de cuenta bancario (`.xlsx`/`.csv`) contra los endpoints de ingesta ya existentes en `backend/routers/ingesta.py`.

**Architecture:** Dos formularios independientes (`CfdiUploadForm`, `BancoUploadForm`) en una sola página cliente, cada uno con su propia mutación de TanStack Query que envía `FormData` vía `apiFetch`. Un componente compartido (`IngestaResultado`) renderiza la respuesta de ambos endpoints (mismo shape `IngestaResponse`).

**Tech Stack:** Next.js (App Router) + TypeScript, Tailwind, TanStack Query, Vitest + React Testing Library — mismo stack que Fase 1, sin dependencias nuevas.

Ver spec completa en `docs/superpowers/specs/2026-07-23-frontend-ingesta-design.md`.

## Global Constraints

- Todo el código nuevo vive bajo `frontend/` (convención heredada de Fase 1).
- Trabajar sobre la rama `feat/frontend-ingesta` (creada desde `feat/frontend-nextjs`, spec commiteada en `e68409a`).
- Alcance de esta fase: solo la página de ingesta. No tocar conciliación (`/conciliaciones`, `/cierre`), movimientos ni categorías — son sub-proyectos posteriores.
- El selector de banco usa un elemento `<select>` nativo (no el componente `Select` de shadcn/ui basado en Radix), siguiendo el mismo patrón que ya usa el selector de empresa en `frontend/app/(app)/dashboard/page.tsx`. Esto evita introducir el primer uso real de Radix Select en este proyecto — que requeriría agregar polyfills de Pointer Events a `vitest.setup.ts` — sin cambiar la UX descrita en la spec (dropdown con bancos comunes + "Otro").
- Cada commit sigue Conventional Commits (`feat:`, `test:`, `chore:`), imperativo y acotado.
- TDD: cada task escribe el test antes que la implementación.
- Sin E2E en esta fase (misma decisión que Fase 1).

---

### Task 1: Soporte de `FormData` en `apiFetch`

**Files:**
- Modify: `frontend/lib/api-client.ts:39` (dentro de `apiFetch`)
- Modify: `frontend/lib/api-client.test.ts`

**Interfaces:**
- Consumes: ninguno nuevo.
- Produces: `apiFetch<T>(path, options)` ahora omite el header `Content-Type: application/json` cuando `options.body instanceof FormData` — el resto de la firma no cambia.

- [ ] **Step 1: Escribir el test que debe fallar**

Agregar al final de `describe("apiFetch", ...)` en `frontend/lib/api-client.test.ts` (antes del cierre `});` final):

```ts
  it("does not add a Content-Type header when the body is FormData", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    const formData = new FormData();
    formData.append("periodo", "2026-07");
    await apiFetch("/api/v1/empresas/e1/cfdi/upload", {
      method: "POST",
      body: formData,
    });

    const [, options] = fetchMock.mock.calls[0];
    expect(
      (options.headers as Record<string, string>)["Content-Type"],
    ).toBeUndefined();
  });

  it("adds a Content-Type header of application/json for a plain object body", async () => {
    const fetchMock = vi.fn().mockResolvedValue(mockResponse(200, { ok: true }));
    vi.stubGlobal("fetch", fetchMock);

    await apiFetch("/api/v1/mis-empresas", {
      method: "POST",
      body: JSON.stringify({ rfc: "AAA010101AAA" }),
    });

    const [, options] = fetchMock.mock.calls[0];
    expect((options.headers as Record<string, string>)["Content-Type"]).toBe(
      "application/json",
    );
  });
```

Run: `cd frontend && npx vitest run lib/api-client.test.ts`
Expected: FAIL — el primer test nuevo falla porque `apiFetch` hoy siempre agrega `Content-Type: application/json`.

- [ ] **Step 2: Implementar el cambio en `apiFetch`**

En `frontend/lib/api-client.ts`, reemplazar el bloque de construcción de `headers` dentro de `apiFetch`:

```ts
export async function apiFetch<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const isFormData = options.body instanceof FormData;
  const headers: Record<string, string> = {
    ...(isFormData ? {} : { "Content-Type": "application/json" }),
    ...((options.headers as Record<string, string>) ?? {}),
  };
  if (token) {
    headers["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(`${apiBaseUrl()}${path}`, {
    ...options,
    headers,
  });
```

(El resto de la función no cambia.)

Run: `cd frontend && npx vitest run lib/api-client.test.ts`
Expected: PASS (7 tests: 5 existentes + 2 nuevos)

- [ ] **Step 3: Commit**

```bash
git add frontend/lib/api-client.ts frontend/lib/api-client.test.ts
git commit -m "fix: apiFetch no fuerza Content-Type json cuando el body es FormData"
```

---

### Task 2: Tipo `IngestaResponse` y hooks de mutación

**Files:**
- Modify: `frontend/types/api.ts` (agregar al final del archivo)
- Create: `frontend/hooks/useIngesta.ts`

**Interfaces:**
- Consumes: `apiFetch` de `lib/api-client.ts` (Task 1).
- Produces: `IngestaResponse` en `types/api.ts`; `useSubirCfdi(empresaId: string)` → mutación con `mutationFn(input: { archivos: File[]; periodo: string }): Promise<IngestaResponse>`; `useSubirBanco(empresaId: string)` → mutación con `mutationFn(input: { archivo: File; banco: string; periodo: string }): Promise<IngestaResponse>`. Ambos hooks son consumidos por las Tasks 4 y 5.

No hay test dedicado para este hook (mismo patrón que `useEmpresas.ts`/`useLogin.ts` en Fase 1: las mutaciones se cubren a través de los tests de los componentes que las usan, en las Tasks 4 y 5).

- [ ] **Step 1: Agregar `IngestaResponse` a `types/api.ts`**

Agregar al final de `frontend/types/api.ts`:

```ts
export interface IngestaResponse {
  mensaje: string;
  registros_procesados: number;
  errores: string[];
  periodo: string;
}
```

- [ ] **Step 2: Implementar `hooks/useIngesta.ts`**

```ts
// frontend/hooks/useIngesta.ts
"use client";

import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { IngestaResponse } from "@/types/api";

interface SubirCfdiInput {
  archivos: File[];
  periodo: string;
}

export function useSubirCfdi(empresaId: string) {
  return useMutation({
    mutationFn: (input: SubirCfdiInput) => {
      const formData = new FormData();
      for (const archivo of input.archivos) {
        formData.append("archivos", archivo);
      }
      formData.append("periodo", input.periodo);
      return apiFetch<IngestaResponse>(
        `/api/v1/empresas/${empresaId}/cfdi/upload`,
        { method: "POST", body: formData },
      );
    },
  });
}

interface SubirBancoInput {
  archivo: File;
  banco: string;
  periodo: string;
}

export function useSubirBanco(empresaId: string) {
  return useMutation({
    mutationFn: (input: SubirBancoInput) => {
      const formData = new FormData();
      formData.append("archivo", input.archivo);
      formData.append("banco", input.banco);
      formData.append("periodo", input.periodo);
      return apiFetch<IngestaResponse>(
        `/api/v1/empresas/${empresaId}/banco/upload`,
        { method: "POST", body: formData },
      );
    },
  });
}
```

- [ ] **Step 3: Verificar que el proyecto compila**

Run: `cd frontend && npx tsc --noEmit`
Expected: sin errores de tipos.

- [ ] **Step 4: Commit**

```bash
git add frontend/types/api.ts frontend/hooks/useIngesta.ts
git commit -m "feat: tipo IngestaResponse y hooks useSubirCfdi/useSubirBanco"
```

---

### Task 3: Componente compartido `IngestaResultado`

**Files:**
- Create: `frontend/components/ingesta/IngestaResultado.tsx`
- Create: `frontend/components/ingesta/IngestaResultado.test.tsx`

**Interfaces:**
- Consumes: `IngestaResponse` de `types/api.ts` (Task 2).
- Produces: `IngestaResultado({ resultado: IngestaResponse })` — usado por las Tasks 4 y 5.

- [ ] **Step 1: Escribir el test (debe fallar)**

```tsx
// frontend/components/ingesta/IngestaResultado.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IngestaResultado } from "./IngestaResultado";

describe("IngestaResultado", () => {
  it("shows the message and the processed count", () => {
    render(
      <IngestaResultado
        resultado={{
          mensaje: "3 CFDI procesados correctamente",
          registros_procesados: 3,
          errores: [],
          periodo: "2026-07",
        }}
      />,
    );

    expect(
      screen.getByText("3 CFDI procesados correctamente"),
    ).toBeInTheDocument();
    expect(screen.getByText("3 registros procesados.")).toBeInTheDocument();
  });

  it("does not render an error list when there are no errors", () => {
    render(
      <IngestaResultado
        resultado={{
          mensaje: "ok",
          registros_procesados: 1,
          errores: [],
          periodo: "2026-07",
        }}
      />,
    );

    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("renders each partial error as a list item", () => {
    render(
      <IngestaResultado
        resultado={{
          mensaje: "1 CFDI procesado correctamente",
          registros_procesados: 1,
          errores: ["otro.xml: UUID duplicado", "malo.xml: XML inválido"],
          periodo: "2026-07",
        }}
      />,
    );

    expect(
      screen.getByText("otro.xml: UUID duplicado"),
    ).toBeInTheDocument();
    expect(screen.getByText("malo.xml: XML inválido")).toBeInTheDocument();
  });
});
```

Run: `cd frontend && npx vitest run components/ingesta/IngestaResultado.test.tsx`
Expected: FAIL — `Cannot find module './IngestaResultado'`

- [ ] **Step 2: Implementar `IngestaResultado.tsx`**

```tsx
// frontend/components/ingesta/IngestaResultado.tsx
import type { IngestaResponse } from "@/types/api";

export function IngestaResultado({ resultado }: { resultado: IngestaResponse }) {
  const plural = resultado.registros_procesados === 1 ? "" : "s";

  return (
    <div className="space-y-2 rounded-md border p-4 text-sm">
      <p>{resultado.mensaje}</p>
      <p>
        {resultado.registros_procesados} registro{plural} procesado{plural}.
      </p>
      {resultado.errores.length > 0 && (
        <ul className="list-disc space-y-1 pl-5 text-amber-700">
          {resultado.errores.map((error) => (
            <li key={error}>{error}</li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

Run: `cd frontend && npx vitest run components/ingesta/IngestaResultado.test.tsx`
Expected: PASS (3 tests)

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ingesta/IngestaResultado.tsx frontend/components/ingesta/IngestaResultado.test.tsx
git commit -m "feat: componente IngestaResultado compartido"
```

---

### Task 4: `CfdiUploadForm`

**Files:**
- Create: `frontend/components/ingesta/CfdiUploadForm.tsx`
- Create: `frontend/components/ingesta/CfdiUploadForm.test.tsx`

**Interfaces:**
- Consumes: `useSubirCfdi` de `hooks/useIngesta.ts` (Task 2); `IngestaResultado` (Task 3); `apiFetch`, `ApiError` de `lib/api-client.ts`; `Button`, `Input`, `Label` de `@/components/ui/*`.
- Produces: `CfdiUploadForm({ empresaId: string })` — usado por la Task 6.

- [ ] **Step 1: Escribir el test (debe fallar)**

```tsx
// frontend/components/ingesta/CfdiUploadForm.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CfdiUploadForm } from "./CfdiUploadForm";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

function renderForm() {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <CfdiUploadForm empresaId="e1" />
    </QueryClientProvider>,
  );
}

describe("CfdiUploadForm", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("shows a validation error when there is no periodo", async () => {
    const user = userEvent.setup();
    renderForm();

    const file = new File(["<xml></xml>"], "cfdi.xml", { type: "text/xml" });
    await user.upload(screen.getByLabelText("Archivos XML"), file);
    await user.click(screen.getByRole("button", { name: /subir cfdi/i }));

    expect(screen.getByText("El periodo es obligatorio")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("shows a validation error when there are no files", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    await user.click(screen.getByRole("button", { name: /subir cfdi/i }));

    expect(
      screen.getByText("Selecciona al menos un archivo XML"),
    ).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("submits FormData with the files and periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      mensaje: "1 CFDI procesado correctamente",
      registros_procesados: 1,
      errores: [],
      periodo: "2026-07",
    });
    const user = userEvent.setup();
    renderForm();

    const file = new File(["<xml></xml>"], "cfdi.xml", { type: "text/xml" });
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    await user.upload(screen.getByLabelText("Archivos XML"), file);
    await user.click(screen.getByRole("button", { name: /subir cfdi/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    const [path, options] = vi.mocked(apiFetch).mock.calls[0];
    expect(path).toBe("/api/v1/empresas/e1/cfdi/upload");
    const body = options?.body as FormData;
    expect(body.get("periodo")).toBe("2026-07");
    expect((body.get("archivos") as File).name).toBe("cfdi.xml");
  });

  it("shows the result summary including partial errors", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      mensaje: "1 CFDI procesado correctamente",
      registros_procesados: 1,
      errores: ["otro.xml: UUID duplicado"],
      periodo: "2026-07",
    });
    const user = userEvent.setup();
    renderForm();

    const file = new File(["<xml></xml>"], "cfdi.xml", { type: "text/xml" });
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    await user.upload(screen.getByLabelText("Archivos XML"), file);
    await user.click(screen.getByRole("button", { name: /subir cfdi/i }));

    await waitFor(() =>
      expect(screen.getByText("otro.xml: UUID duplicado")).toBeInTheDocument(),
    );
  });

  it("shows the backend error message on failure", async () => {
    vi.mocked(apiFetch).mockRejectedValue(
      new ApiError(400, "Archivo con extensión inválida"),
    );
    const user = userEvent.setup();
    renderForm();

    const file = new File(["not xml"], "cfdi.txt", { type: "text/plain" });
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    await user.upload(screen.getByLabelText("Archivos XML"), file);
    await user.click(screen.getByRole("button", { name: /subir cfdi/i }));

    await waitFor(() =>
      expect(
        screen.getByText("Archivo con extensión inválida"),
      ).toBeInTheDocument(),
    );
  });
});
```

Run: `cd frontend && npx vitest run components/ingesta/CfdiUploadForm.test.tsx`
Expected: FAIL — `Cannot find module './CfdiUploadForm'`

- [ ] **Step 2: Implementar `CfdiUploadForm.tsx`**

```tsx
// frontend/components/ingesta/CfdiUploadForm.tsx
"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSubirCfdi } from "@/hooks/useIngesta";
import { ApiError } from "@/lib/api-client";
import { IngestaResultado } from "@/components/ingesta/IngestaResultado";
import type { IngestaResponse } from "@/types/api";

export function CfdiUploadForm({ empresaId }: { empresaId: string }) {
  const subirCfdi = useSubirCfdi(empresaId);
  const [periodo, setPeriodo] = useState("");
  const [archivos, setArchivos] = useState<FileList | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<IngestaResponse | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setResultado(null);

    if (!periodo.trim()) {
      setFormError("El periodo es obligatorio");
      return;
    }
    if (!archivos || archivos.length === 0) {
      setFormError("Selecciona al menos un archivo XML");
      return;
    }

    try {
      const response = await subirCfdi.mutateAsync({
        archivos: Array.from(archivos),
        periodo: periodo.trim(),
      });
      setResultado(response);
      setArchivos(null);
      event.currentTarget.reset();
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("No se pudo subir el CFDI, intenta de nuevo");
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border p-4">
      <h2 className="text-lg font-semibold">Subir CFDI</h2>

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
          accept=".xml"
          multiple
          onChange={(e) => setArchivos(e.target.files)}
        />
      </div>

      {formError && (
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}

      <Button type="submit" disabled={subirCfdi.isPending}>
        {subirCfdi.isPending ? "Subiendo..." : "Subir CFDI"}
      </Button>

      {resultado && <IngestaResultado resultado={resultado} />}
    </form>
  );
}
```

Run: `cd frontend && npx vitest run components/ingesta/CfdiUploadForm.test.tsx`
Expected: PASS (5 tests)

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ingesta/CfdiUploadForm.tsx frontend/components/ingesta/CfdiUploadForm.test.tsx
git commit -m "feat: formulario de subida de CFDI"
```

---

### Task 5: `BancoUploadForm`

**Files:**
- Create: `frontend/components/ingesta/BancoUploadForm.tsx`
- Create: `frontend/components/ingesta/BancoUploadForm.test.tsx`

**Interfaces:**
- Consumes: `useSubirBanco` de `hooks/useIngesta.ts` (Task 2); `IngestaResultado` (Task 3); `apiFetch`, `ApiError` de `lib/api-client.ts`; `Button`, `Input`, `Label` de `@/components/ui/*`.
- Produces: `BancoUploadForm({ empresaId: string })` — usado por la Task 6.

- [ ] **Step 1: Escribir el test (debe fallar)**

```tsx
// frontend/components/ingesta/BancoUploadForm.test.tsx
import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BancoUploadForm } from "./BancoUploadForm";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

function renderForm() {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <BancoUploadForm empresaId="e1" />
    </QueryClientProvider>,
  );
}

describe("BancoUploadForm", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("shows a validation error when there is no periodo", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.selectOptions(screen.getByLabelText("Banco"), "bbva");
    const file = new File(["a,b"], "estado.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Estado de cuenta (.xlsx o .csv)"), file);
    await user.click(
      screen.getByRole("button", { name: /subir estado de cuenta/i }),
    );

    expect(screen.getByText("El periodo es obligatorio")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("shows a validation error when there is no banco", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    const file = new File(["a,b"], "estado.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Estado de cuenta (.xlsx o .csv)"), file);
    await user.click(
      screen.getByRole("button", { name: /subir estado de cuenta/i }),
    );

    expect(screen.getByText("El banco es obligatorio")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("reveals a free-text input when 'Otro' is selected and uses it as the banco value", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      mensaje: "5 movimientos procesados",
      registros_procesados: 5,
      errores: [],
      periodo: "2026-07",
    });
    const user = userEvent.setup();
    renderForm();

    await user.selectOptions(screen.getByLabelText("Banco"), "otro");
    await user.type(screen.getByLabelText("Nombre del banco"), "Banco Azteca");
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    const file = new File(["a,b"], "estado.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Estado de cuenta (.xlsx o .csv)"), file);
    await user.click(
      screen.getByRole("button", { name: /subir estado de cuenta/i }),
    );

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    const [, options] = vi.mocked(apiFetch).mock.calls[0];
    const body = options?.body as FormData;
    expect(body.get("banco")).toBe("Banco Azteca");
  });

  it("submits FormData with the file, banco and periodo for a listed bank", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      mensaje: "5 movimientos procesados",
      registros_procesados: 5,
      errores: [],
      periodo: "2026-07",
    });
    const user = userEvent.setup();
    renderForm();

    await user.selectOptions(screen.getByLabelText("Banco"), "bbva");
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    const file = new File(["a,b"], "estado.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Estado de cuenta (.xlsx o .csv)"), file);
    await user.click(
      screen.getByRole("button", { name: /subir estado de cuenta/i }),
    );

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    const [path, options] = vi.mocked(apiFetch).mock.calls[0];
    expect(path).toBe("/api/v1/empresas/e1/banco/upload");
    const body = options?.body as FormData;
    expect(body.get("banco")).toBe("bbva");
    expect(body.get("periodo")).toBe("2026-07");
    expect((body.get("archivo") as File).name).toBe("estado.csv");
  });

  it("shows the backend error message on failure", async () => {
    vi.mocked(apiFetch).mockRejectedValue(
      new ApiError(400, "No se pudo interpretar el archivo"),
    );
    const user = userEvent.setup();
    renderForm();

    await user.selectOptions(screen.getByLabelText("Banco"), "bbva");
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    const file = new File(["a,b"], "estado.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Estado de cuenta (.xlsx o .csv)"), file);
    await user.click(
      screen.getByRole("button", { name: /subir estado de cuenta/i }),
    );

    await waitFor(() =>
      expect(
        screen.getByText("No se pudo interpretar el archivo"),
      ).toBeInTheDocument(),
    );
  });
});
```

Run: `cd frontend && npx vitest run components/ingesta/BancoUploadForm.test.tsx`
Expected: FAIL — `Cannot find module './BancoUploadForm'`

- [ ] **Step 2: Implementar `BancoUploadForm.tsx`**

```tsx
// frontend/components/ingesta/BancoUploadForm.tsx
"use client";

import { FormEvent, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useSubirBanco } from "@/hooks/useIngesta";
import { ApiError } from "@/lib/api-client";
import { IngestaResultado } from "@/components/ingesta/IngestaResultado";
import type { IngestaResponse } from "@/types/api";

const BANCOS_COMUNES = [
  { value: "bbva", label: "BBVA" },
  { value: "santander", label: "Santander" },
  { value: "banamex", label: "Banamex" },
  { value: "banorte", label: "Banorte" },
  { value: "hsbc", label: "HSBC" },
  { value: "scotiabank", label: "Scotiabank" },
  { value: "otro", label: "Otro" },
];

export function BancoUploadForm({ empresaId }: { empresaId: string }) {
  const subirBanco = useSubirBanco(empresaId);
  const [periodo, setPeriodo] = useState("");
  const [bancoSeleccionado, setBancoSeleccionado] = useState("");
  const [bancoLibre, setBancoLibre] = useState("");
  const [archivo, setArchivo] = useState<File | null>(null);
  const [formError, setFormError] = useState<string | null>(null);
  const [resultado, setResultado] = useState<IngestaResponse | null>(null);

  const esOtro = bancoSeleccionado === "otro";
  const bancoFinal = esOtro ? bancoLibre.trim() : bancoSeleccionado;

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFormError(null);
    setResultado(null);

    if (!periodo.trim()) {
      setFormError("El periodo es obligatorio");
      return;
    }
    if (!bancoFinal) {
      setFormError("El banco es obligatorio");
      return;
    }
    if (!archivo) {
      setFormError("Selecciona un archivo .xlsx o .csv");
      return;
    }

    try {
      const response = await subirBanco.mutateAsync({
        archivo,
        banco: bancoFinal,
        periodo: periodo.trim(),
      });
      setResultado(response);
      setArchivo(null);
      setBancoSeleccionado("");
      setBancoLibre("");
      event.currentTarget.reset();
    } catch (err) {
      if (err instanceof ApiError) {
        setFormError(err.message);
      } else {
        setFormError("No se pudo subir el estado de cuenta, intenta de nuevo");
      }
    }
  }

  return (
    <form onSubmit={handleSubmit} className="space-y-4 rounded-lg border p-4">
      <h2 className="text-lg font-semibold">Subir estado de cuenta</h2>

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
          className="w-full rounded-md border p-2"
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
        <p role="alert" className="text-sm text-red-600">
          {formError}
        </p>
      )}

      <Button type="submit" disabled={subirBanco.isPending}>
        {subirBanco.isPending ? "Subiendo..." : "Subir estado de cuenta"}
      </Button>

      {resultado && <IngestaResultado resultado={resultado} />}
    </form>
  );
}
```

Run: `cd frontend && npx vitest run components/ingesta/BancoUploadForm.test.tsx`
Expected: PASS (5 tests)

- [ ] **Step 3: Commit**

```bash
git add frontend/components/ingesta/BancoUploadForm.tsx frontend/components/ingesta/BancoUploadForm.test.tsx
git commit -m "feat: formulario de subida de estado de cuenta bancario"
```

---

### Task 6: Página de Ingesta y link de navegación desde Empresas

**Files:**
- Create: `frontend/app/(app)/empresas/[empresaId]/ingesta/page.tsx`
- Modify: `frontend/components/empresas/EmpresaList.tsx`
- Create: `frontend/components/empresas/EmpresaList.test.tsx`

**Interfaces:**
- Consumes: `CfdiUploadForm` (Task 4), `BancoUploadForm` (Task 5); `Empresa` de `types/api.ts`.
- Produces: ruta `/empresas/[empresaId]/ingesta`; `EmpresaList` ahora renderiza un link "Ingesta" por fila además del de "Cédula de IVA" ya existente.

- [ ] **Step 1: Escribir el test de `EmpresaList` (debe fallar)**

```tsx
// frontend/components/empresas/EmpresaList.test.tsx
import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
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

describe("EmpresaList", () => {
  it("renders an Ingesta link pointing to the empresa's ingesta page", () => {
    render(<EmpresaList empresas={[empresa]} />);

    const link = screen.getByRole("link", { name: "Ingesta" });
    expect(link).toHaveAttribute("href", "/empresas/e1/ingesta");
  });

  it("still renders the Cédula de IVA link", () => {
    render(<EmpresaList empresas={[empresa]} />);

    const link = screen.getByRole("link", { name: "Cédula de IVA" });
    expect(link).toHaveAttribute("href", "/empresas/e1/cedula-iva");
  });
});
```

Run: `cd frontend && npx vitest run components/empresas/EmpresaList.test.tsx`
Expected: FAIL — no existe un link con nombre accesible "Ingesta"

- [ ] **Step 2: Agregar el link "Ingesta" en `EmpresaList.tsx`**

En `frontend/components/empresas/EmpresaList.tsx`, reemplazar la celda final:

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
            </td>
```

Run: `cd frontend && npx vitest run components/empresas/EmpresaList.test.tsx`
Expected: PASS (2 tests)

- [ ] **Step 3: Implementar la página de Ingesta**

```tsx
// frontend/app/(app)/empresas/[empresaId]/ingesta/page.tsx
"use client";

import { useParams } from "next/navigation";
import { CfdiUploadForm } from "@/components/ingesta/CfdiUploadForm";
import { BancoUploadForm } from "@/components/ingesta/BancoUploadForm";

export default function IngestaPage() {
  const params = useParams<{ empresaId: string }>();

  return (
    <main className="mx-auto max-w-3xl space-y-6 p-6">
      <h1 className="text-2xl font-semibold">Ingesta</h1>
      <CfdiUploadForm empresaId={params.empresaId} />
      <BancoUploadForm empresaId={params.empresaId} />
    </main>
  );
}
```

- [ ] **Step 4: Correr toda la suite y verificar el build**

Run: `cd frontend && npm test`
Expected: PASS (todos los tests, incluidos los de las Tasks 1-6)

Run: `cd frontend && npm run build`
Expected: build exitoso, sin errores de TypeScript

- [ ] **Step 5: Commit**

```bash
git add "frontend/app/(app)/empresas/[empresaId]/ingesta/page.tsx" frontend/components/empresas/EmpresaList.tsx frontend/components/empresas/EmpresaList.test.tsx
git commit -m "feat: página de ingesta de CFDI y estado de cuenta, link desde Empresas"
```

---

## Verificación final

Tras completar la Task 6, correr manualmente:

```bash
cd frontend
npm test
npm run build
```

Ambos deben terminar exitosamente antes de considerar la fase 2a completa.
