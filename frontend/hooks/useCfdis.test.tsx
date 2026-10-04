import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCfdiColumnas, useCfdiDetalle, useCfdiListado, useCfdiResumen } from "./useCfdis";
import { leerEstado } from "@/lib/cfdi-url";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

// Un cliente por prueba, creado una sola vez: si cambiara en cada render se perdería la caché.
function crearWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const estado = (texto = "") => leerEstado(new URLSearchParams(texto), "2026-09");
const ultimaUrl = () => vi.mocked(apiFetch).mock.calls.at(-1)![0] as string;

describe("useCfdiColumnas", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("no consulta sin empresa", () => {
    renderHook(() => useCfdiColumnas("", "emitidos", "I"), { wrapper: crearWrapper() });

    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("pide el catálogo de la dirección y el tipo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ encabezado: [], concepto: [] });
    renderHook(() => useCfdiColumnas("e1", "recibidos", "E"), { wrapper: crearWrapper() });

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(ultimaUrl()).toBe("/api/v1/empresas/e1/cfdis/columnas?direccion=recibidos&tipo=E");
  });
});

describe("useCfdiListado", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("no consulta sin empresa", () => {
    renderHook(() => useCfdiListado("", "emitidos", estado()), { wrapper: crearWrapper() });

    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("manda todos los parámetros del estado", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ items: [], total: 0, pagina: 2, por_pagina: 50 });
    renderHook(
      () => useCfdiListado("e1", "emitidos", estado("tipo=E&metodo=PPD&pago=pendientes&q=abc&orden=total&dir=desc&pagina=2&por_pagina=50")),
      { wrapper: crearWrapper() },
    );

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    const url = new URL(ultimaUrl(), "http://x");
    expect(url.pathname).toBe("/api/v1/empresas/e1/cfdis");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      direccion: "emitidos", periodo: "2026-09", tipo: "E", estado: "vigente", metodo: "PPD",
      pago: "pendientes", q: "abc", orden: "total", dir: "desc", pagina: "2", por_pagina: "50",
    });
  });

  it("al cambiar de página conserva las filas anteriores mientras llegan las nuevas", async () => {
    let resolverSegunda: (v: unknown) => void = () => {};
    vi.mocked(apiFetch)
      .mockResolvedValueOnce({ items: [{ uuid: "A" }], total: 60, pagina: 1, por_pagina: 30 })
      .mockImplementationOnce(() => new Promise((r) => { resolverSegunda = r; }));

    const { result, rerender } = renderHook(
      ({ pagina }: { pagina: number }) => useCfdiListado("e1", "emitidos", estado(`pagina=${pagina}`)),
      { wrapper: crearWrapper(), initialProps: { pagina: 1 } },
    );
    await waitFor(() => expect(result.current.data?.items[0].uuid).toBe("A"));

    rerender({ pagina: 2 });

    expect(result.current.isPlaceholderData).toBe(true);
    expect(result.current.data?.items[0].uuid).toBe("A");

    await act(async () => resolverSegunda({ items: [{ uuid: "B" }], total: 60, pagina: 2, por_pagina: 30 }));
    await waitFor(() => expect(result.current.data?.items[0].uuid).toBe("B"));
  });
});

describe("useCfdiResumen", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("no consulta sin empresa", () => {
    renderHook(() => useCfdiResumen("", "emitidos", estado()), { wrapper: crearWrapper() });

    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("no manda orden ni paginación, que el resumen no usa", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useCfdiResumen("e1", "recibidos", estado("tipo=P&orden=total&dir=desc&pagina=4&por_pagina=100")), {
      wrapper: crearWrapper(),
    });

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    const url = new URL(ultimaUrl(), "http://x");
    expect(url.pathname).toBe("/api/v1/empresas/e1/cfdis/resumen");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      direccion: "recibidos", periodo: "2026-09", tipo: "P", estado: "vigente", metodo: "todos", pago: "todos",
    });
  });

  it("paginar no vuelve a pedir el resumen", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    const { rerender } = renderHook(
      ({ pagina }: { pagina: number }) => useCfdiResumen("e1", "emitidos", estado(`pagina=${pagina}`)),
      { wrapper: crearWrapper(), initialProps: { pagina: 1 } },
    );
    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));

    rerender({ pagina: 2 });

    expect(apiFetch).toHaveBeenCalledTimes(1);
  });
});

describe("useCfdiDetalle", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("no consulta mientras no haya uuid (fila cerrada)", () => {
    renderHook(() => useCfdiDetalle("e1", null), { wrapper: crearWrapper() });

    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("pide el detalle del uuid y lo reutiliza al reabrir", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ conceptos: [], total_conceptos: 0 });
    const wrapper = crearWrapper();
    const { result, rerender } = renderHook(({ uuid }: { uuid: string | null }) => useCfdiDetalle("e1", uuid), {
      wrapper,
      initialProps: { uuid: "U-1" as string | null },
    });

    await waitFor(() => expect(result.current.data).toBeDefined());
    expect(ultimaUrl()).toBe("/api/v1/empresas/e1/cfdis/U-1");

    rerender({ uuid: null });
    rerender({ uuid: "U-1" });
    expect(result.current.data).toBeDefined();
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });
});
