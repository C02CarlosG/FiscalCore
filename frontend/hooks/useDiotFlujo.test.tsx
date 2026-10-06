import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useClasificarTerceroDiot, useDiotFlujo, useQuitarClasificacionDiot } from "./useDiotFlujo";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

function crear() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: React.ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { queryClient, wrapper };
}

const ultima = () => vi.mocked(apiFetch).mock.calls.at(-1)!;

describe("useDiotFlujo", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("no consulta sin empresa o sin periodo válido", () => {
    renderHook(() => useDiotFlujo("", "2026-09"), { wrapper: crear().wrapper });
    renderHook(() => useDiotFlujo("e1", "2026-13"), { wrapper: crear().wrapper });

    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("pide la DIOT del periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useDiotFlujo("e1", "2026-09"), { wrapper: crear().wrapper });

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/diot-flujo/2026-09");
  });
});

describe("clasificación del tercero", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("PUT con la clasificación y refresca la DIOT", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    const { queryClient, wrapper } = crear();
    const invalidar = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useClasificarTerceroDiot("e1", "2026-09"), { wrapper });

    await act(() => result.current.mutateAsync({ proveedorId: "p1", datos: { tipo_operacion: "06" } }));

    expect(ultima()[0]).toBe("/api/v1/empresas/e1/diot-flujo/2026-09/terceros/p1");
    expect(ultima()[1]).toMatchObject({ method: "PUT", body: JSON.stringify({ tipo_operacion: "06" }) });
    expect(invalidar).toHaveBeenCalledWith({ queryKey: ["diot-flujo", "e1"] });
  });

  it("DELETE retira la clasificación del periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    const { result } = renderHook(() => useQuitarClasificacionDiot("e1", "2026-09"), { wrapper: crear().wrapper });

    await act(() => result.current.mutateAsync("p1"));

    expect(ultima()[0]).toBe("/api/v1/empresas/e1/diot-flujo/2026-09/terceros/p1");
    expect(ultima()[1]).toMatchObject({ method: "DELETE" });
  });
});
