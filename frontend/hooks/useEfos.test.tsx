import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useEfosEstado, useImportarEfos, useSubirEfos } from "./useEfos";

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

describe("hooks de EFOS", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("lee el estado de la lista", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ hay_lista: true });
    const { result } = renderHook(() => useEfosEstado(), { wrapper: crear().wrapper });
    await waitFor(() => expect(result.current.data?.hay_lista).toBe(true));
    expect(vi.mocked(apiFetch).mock.calls[0][0]).toBe("/api/v1/efos/estado");
  });

  it("importar hace POST y refresca el estado, el listado de CFDI y los proveedores", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ estado: "correcta" });
    const { queryClient, wrapper } = crear();
    for (const k of ["efos-estado", "cfdi-listado", "cfdi-resumen", "proveedores"]) queryClient.setQueryData([k, "x"], { ok: true });
    const { result } = renderHook(() => useImportarEfos(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync();
    });
    const [url, init] = vi.mocked(apiFetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/admin/efos/importar");
    expect(init.method).toBe("POST");
    for (const k of ["efos-estado", "cfdi-listado", "cfdi-resumen", "proveedores"]) {
      expect(queryClient.getQueryState([k, "x"])?.isInvalidated, k).toBe(true);
    }
  });

  it("subir envía el archivo como multipart a la ruta de administración", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ estado: "correcta" });
    const { result } = renderHook(() => useSubirEfos(), { wrapper: crear().wrapper });
    const archivo = new File(["a,b"], "lista.csv", { type: "text/csv" });
    await act(async () => {
      await result.current.mutateAsync(archivo);
    });
    const [url, init] = vi.mocked(apiFetch).mock.calls[0] as [string, RequestInit];
    expect(url).toBe("/api/v1/admin/efos/subir");
    expect(init.method).toBe("POST");
    expect((init.body as FormData).get("archivo")).toBe(archivo);
  });
});
