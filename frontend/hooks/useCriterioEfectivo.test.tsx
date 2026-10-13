import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCambiarCriterioEfectivo, useCriterioEfectivo } from "./useCriterioEfectivo";

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

describe("hooks del criterio de efectivo", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("lee el criterio de la empresa", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ criterio_efectivo: "estricto", umbral_efectivo: 0 });
    const { result } = renderHook(() => useCriterioEfectivo("e1"), { wrapper: crear().wrapper });
    await waitFor(() => expect(result.current.data?.criterio_efectivo).toBe("estricto"));
    expect(vi.mocked(apiFetch).mock.calls[0][0]).toBe("/api/v1/empresas/e1/criterio-efectivo");
  });

  it("no consulta sin empresa", () => {
    renderHook(() => useCriterioEfectivo(""), { wrapper: crear().wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("al cambiarlo envía el PUT e invalida IVA, ISR, DIOT, inicio y declaraciones de esa empresa", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ criterio_efectivo: "estricto", umbral_efectivo: 0 });
    const { queryClient, wrapper } = crear();
    const claves = [
      ["iva-flujo-resumen", "e1", "2026-09"], ["iva-flujo-detalle", "e1", "2026-09"],
      ["isr-flujo-resumen", "e1", "2026-09"], ["isr-flujo-detalle", "e1", "2026-09"],
      ["diot-flujo", "e1", "2026-09"], ["inicio-resumen", "e1", "2026-09"], ["inicio-iva-anual", "e1", 2026],
      ["declaraciones", "e1", "2026-09"],
    ];
    for (const k of claves) queryClient.setQueryData(k, { ok: true });
    queryClient.setQueryData(["iva-flujo-resumen", "otra", "2026-09"], { ok: true });

    const { result } = renderHook(() => useCambiarCriterioEfectivo("e1"), { wrapper });
    await act(async () => {
      await result.current.mutateAsync("estricto");
    });

    const [url, init] = vi.mocked(apiFetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/empresas/e1/criterio-efectivo");
    expect(init.method).toBe("PUT");
    expect(JSON.parse(String(init.body))).toEqual({ criterio: "estricto" });
    for (const k of claves) expect(queryClient.getQueryState(k)?.isInvalidated, k.join("/")).toBe(true);
    expect(queryClient.getQueryState(["iva-flujo-resumen", "otra", "2026-09"])?.isInvalidated).toBe(false);
  });
});
