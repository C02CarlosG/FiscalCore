import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useGuardarAjusteIsr, useGuardarPorcentajeNomina, useIsrFlujoDetalle, useIsrFlujoResumen, useQuitarAjusteIsr } from "./useIsrFlujo";

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

describe("hooks del ISR por flujo", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("no consulta sin empresa o sin periodo válido", () => {
    renderHook(() => useIsrFlujoResumen("", "2026-09"), { wrapper: crear().wrapper });
    renderHook(() => useIsrFlujoResumen("e1", ""), { wrapper: crear().wrapper });
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("pide el resumen y el detalle", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useIsrFlujoResumen("e1", "2026-09"), { wrapper: crear().wrapper });
    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/isr-flujo/2026-09");

    renderHook(() => useIsrFlujoDetalle("e1", "2026-09", "deduccion", "nomina", true, 2), { wrapper: crear().wrapper });
    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(2));
    expect(ultima()[0]).toBe(
      "/api/v1/empresas/e1/isr-flujo/2026-09/detalle?lado=deduccion&bloque=nomina&acumulado=true&pagina=2&por_pagina=50",
    );
  });

  it("guardar y quitar ajustes y guardar el porcentaje refrescan el ISR", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    const { queryClient, wrapper } = crear();
    const invalidar = vi.spyOn(queryClient, "invalidateQueries");

    const g = renderHook(() => useGuardarAjusteIsr("e1"), { wrapper });
    await act(async () => { await g.result.current.mutateAsync({ uuid: "U1", lado: "ingreso", motivo: "x" }); });
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/isr-flujo/ajustes");
    expect(ultima()[1]).toMatchObject({ method: "PUT" });

    const q = renderHook(() => useQuitarAjusteIsr("e1"), { wrapper });
    await act(async () => { await q.result.current.mutateAsync({ uuid: "U-1", lado: "deduccion" }); });
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/isr-flujo/ajustes/deduccion/U-1");
    expect(ultima()[1]).toMatchObject({ method: "DELETE" });

    const p = renderHook(() => useGuardarPorcentajeNomina("e1", 2026), { wrapper });
    await act(async () => { await p.result.current.mutateAsync(0.53); });
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/isr-flujo/config/2026");
    expect(JSON.parse((ultima()[1] as RequestInit).body as string)).toEqual({ pct_nomina_exenta: 0.53 });
    const claves = invalidar.mock.calls.map((c) => (c[0] as { queryKey: unknown[] }).queryKey[0]);
    expect(claves).toEqual(expect.arrayContaining(["isr-flujo-resumen", "isr-flujo-detalle"]));
  });
});
