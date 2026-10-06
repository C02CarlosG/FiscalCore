import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useCrearProveedor, useEditarProveedor, useProveedores } from "./useProveedores";

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

describe("hooks de proveedores", () => {
  beforeEach(() => vi.mocked(apiFetch).mockReset());

  it("lista con y sin búsqueda, y no consulta sin empresa", async () => {
    vi.mocked(apiFetch).mockResolvedValue({ items: [] });
    renderHook(() => useProveedores("", ""), { wrapper: crear().wrapper });
    expect(apiFetch).not.toHaveBeenCalled();

    renderHook(() => useProveedores("e1", "ac me"), { wrapper: crear().wrapper });
    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/proveedores?q=ac%20me");
  });

  it("crear y editar mandan POST y PATCH y refrescan catálogo y DIOT", async () => {
    vi.mocked(apiFetch).mockResolvedValue({});
    const { queryClient, wrapper } = crear();
    const invalidar = vi.spyOn(queryClient, "invalidateQueries");

    const c = renderHook(() => useCrearProveedor("e1"), { wrapper });
    await act(async () => { await c.result.current.mutateAsync({ rfc: "AAA010101AAA" }); });
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/proveedores");
    expect(ultima()[1]).toMatchObject({ method: "POST" });

    const e = renderHook(() => useEditarProveedor("e1"), { wrapper });
    await act(async () => { await e.result.current.mutateAsync({ id: "p1", cambios: { tipo_operacion: "06" } }); });
    expect(ultima()[0]).toBe("/api/v1/empresas/e1/proveedores/p1");
    expect(ultima()[1]).toMatchObject({ method: "PATCH" });
    const claves = invalidar.mock.calls.map((x) => (x[0] as { queryKey: unknown[] }).queryKey[0]);
    expect(claves).toEqual(expect.arrayContaining(["proveedores", "diot-flujo"]));
  });
});
