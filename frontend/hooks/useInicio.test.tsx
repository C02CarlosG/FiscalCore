import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useInicioIvaAnual, useInicioResumen } from "./useInicio";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

function crearWrapper() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: React.ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const ultimaUrl = () => vi.mocked(apiFetch).mock.calls.at(-1)![0] as string;

describe("useInicioResumen", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("no consulta sin empresa o sin periodo", () => {
    renderHook(() => useInicioResumen("", "2026-09"), { wrapper: crearWrapper() });
    renderHook(() => useInicioResumen("e1", ""), { wrapper: crearWrapper() });

    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("pide el resumen del periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ meses: [] });
    renderHook(() => useInicioResumen("e1", "2026-09"), { wrapper: crearWrapper() });

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(ultimaUrl()).toBe("/api/v1/empresas/e1/inicio/resumen?periodo=2026-09");
  });

  it("cambiar de periodo pide otro y conserva el anterior mientras llega", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ periodo: "2026-09" });
    const { result, rerender } = renderHook(({ p }: { p: string }) => useInicioResumen("e1", p), {
      wrapper: crearWrapper(),
      initialProps: { p: "2026-09" },
    });
    await waitFor(() => expect(result.current.data).toBeDefined());

    let llega: (valor: unknown) => void = () => {};
    vi.mocked(apiFetch).mockReturnValue(new Promise((resolver) => (llega = resolver)));
    rerender({ p: "2026-08" });

    expect(ultimaUrl()).toBe("/api/v1/empresas/e1/inicio/resumen?periodo=2026-08");
    expect(result.current.data).toEqual({ periodo: "2026-09" });

    llega({ periodo: "2026-08" });
    await waitFor(() => expect(result.current.data).toEqual({ periodo: "2026-08" }));
  });
});

describe("useInicioIvaAnual", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("no consulta sin empresa o sin periodo válido", () => {
    renderHook(() => useInicioIvaAnual("", "2026-09"), { wrapper: crearWrapper() });
    renderHook(() => useInicioIvaAnual("e1", ""), { wrapper: crearWrapper() });

    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("pide el ejercicio completo del periodo (los meses posteriores se atenúan en pantalla)", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ meses: [] });
    renderHook(() => useInicioIvaAnual("e1", "2026-09"), { wrapper: crearWrapper() });

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(ultimaUrl()).toBe("/api/v1/empresas/e1/inicio/iva-anual?ejercicio=2026");
  });

  it("cambiar de mes dentro del mismo ejercicio reutiliza la consulta del ejercicio", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ meses: [] });
    const { rerender } = renderHook(({ p }: { p: string }) => useInicioIvaAnual("e1", p), {
      wrapper: crearWrapper(),
      initialProps: { p: "2026-09" },
    });
    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));

    rerender({ p: "2026-03" });

    expect(apiFetch).toHaveBeenCalledTimes(1);
  });
});
