import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useGuardarAjusteIva, useIvaFlujoDetalle, useIvaFlujoResumen, useQuitarAjusteIva } from "./useIvaFlujo";

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

describe("useIvaFlujoResumen", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("no consulta sin empresa o sin periodo válido", () => {
    renderHook(() => useIvaFlujoResumen("", "2026-09"), { wrapper: crear().wrapper });
    renderHook(() => useIvaFlujoResumen("e1", ""), { wrapper: crear().wrapper });

    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("pide el resumen del periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useIvaFlujoResumen("e1", "2026-09"), { wrapper: crear().wrapper });

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/iva-flujo/2026-09");
  });
});

describe("useIvaFlujoDetalle", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("pide la página del origen y la dirección", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ items: [], total: 0, pagina: 2, por_pagina: 50 });
    renderHook(() => useIvaFlujoDetalle("e1", "2026-09", "acreditable", "credito", 2), { wrapper: crear().wrapper });

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(ultima()[0]).toBe(
      "/api/v1/empresas/e1/iva-flujo/2026-09/detalle?direccion=acreditable&origen=credito&pagina=2&por_pagina=50",
    );
  });

  it("no consulta cuando la vista no tiene detalle (dirección nula)", () => {
    renderHook(() => useIvaFlujoDetalle("e1", "2026-09", null, "contado", 1), { wrapper: crear().wrapper });

    expect(apiFetch).not.toHaveBeenCalled();
  });
});

describe("ajustes", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("guardar manda el ajuste por PUT y refresca resumen, detalle e Inicio", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    const { queryClient, wrapper } = crear();
    const invalidar = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useGuardarAjusteIva("e1"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({ uuid: "U1", direccion: "trasladado", accion: "excluir", motivo: "duplicado" });
    });

    const [ruta, opciones] = ultima();
    expect(ruta).toBe("/api/v1/empresas/e1/iva-flujo/ajustes");
    expect(opciones).toMatchObject({ method: "PUT" });
    expect(JSON.parse((opciones as RequestInit).body as string)).toEqual({
      uuid: "U1", direccion: "trasladado", accion: "excluir", motivo: "duplicado",
    });
    const claves = invalidar.mock.calls.map((c) => (c[0] as { queryKey: unknown[] }).queryKey[0]);
    expect(claves).toEqual(expect.arrayContaining(["iva-flujo-resumen", "iva-flujo-detalle", "inicio-iva-anual"]));
  });

  it("quitar manda DELETE a la dirección y UUID y refresca", async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    const { queryClient, wrapper } = crear();
    const invalidar = vi.spyOn(queryClient, "invalidateQueries");
    const { result } = renderHook(() => useQuitarAjusteIva("e1"), { wrapper });

    await act(async () => {
      await result.current.mutateAsync({ uuid: "U-1", direccion: "acreditable" });
    });

    const [ruta, opciones] = ultima();
    expect(ruta).toBe("/api/v1/empresas/e1/iva-flujo/ajustes/acreditable/U-1");
    expect(opciones).toMatchObject({ method: "DELETE" });
    expect(invalidar).toHaveBeenCalled();
  });
});
