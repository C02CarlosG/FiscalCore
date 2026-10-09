import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useComparativoDeclarado, useEliminarDeclaracion, useGuardarDeclaracion } from "./useDeclaraciones";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});
import { apiFetch } from "@/lib/api-client";

function crear() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: React.ReactNode }) => <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  return { queryClient, wrapper };
}
const ultima = () => vi.mocked(apiFetch).mock.calls.at(-1)!;

describe("hooks de declaraciones", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("no consulta sin empresa o sin periodo válido y pide el comparativo del periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    renderHook(() => useComparativoDeclarado("", "2026-09"), { wrapper: crear().wrapper });
    renderHook(() => useComparativoDeclarado("e1", ""), { wrapper: crear().wrapper });
    expect(apiFetch).not.toHaveBeenCalled();

    renderHook(() => useComparativoDeclarado("e1", "2026-09"), { wrapper: crear().wrapper });
    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/declaraciones/2026-09");
  });

  it("guardar manda PUT con el cuerpo y eliminar manda DELETE; ambos refrescan", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    const { queryClient, wrapper } = crear();
    const invalidar = vi.spyOn(queryClient, "invalidateQueries");

    const g = renderHook(() => useGuardarDeclaracion("e1", "2026-09"), { wrapper });
    await act(async () => {
      await g.result.current.mutateAsync({ impuesto: "isr", datos: { tipo: "normal", fecha_presentacion: null, numero_operacion: null, notas: "", ingresos: "1000" } });
    });
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/declaraciones/2026-09/isr");
    expect(ultima()[1]).toMatchObject({ method: "PUT" });
    expect(JSON.parse((ultima()[1] as RequestInit).body as string)).toMatchObject({ tipo: "normal", ingresos: "1000" });

    const e = renderHook(() => useEliminarDeclaracion("e1", "2026-09"), { wrapper });
    await act(async () => { await e.result.current.mutateAsync("iva"); });
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/declaraciones/2026-09/iva");
    expect(ultima()[1]).toMatchObject({ method: "DELETE" });
    expect(invalidar).toHaveBeenCalledTimes(2);
  });
});
