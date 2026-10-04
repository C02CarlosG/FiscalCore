import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { InformacionFiscalPanel } from "./InformacionFiscalPanel";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

const BASE = "/api/v1/informacion-fiscal/empresas/e1";

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <InformacionFiscalPanel empresaId="e1" />
    </QueryClientProvider>,
  );
}

describe("InformacionFiscalPanel", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("muestra una tarjeta por documento y el historial", async () => {
    vi.mocked(apiFetch).mockImplementation(async (ruta: string) => {
      if (ruta === BASE) return { constancia: null, opinion: null };
      if (ruta === `${BASE}/documentos`) return [];
      throw new Error(`llamada inesperada: ${ruta}`);
    });
    renderPanel();

    expect(await screen.findByText("Opinión de cumplimiento")).toBeInTheDocument();
    expect(screen.getByText("Constancia de situación fiscal")).toBeInTheDocument();
    expect(screen.getByText("Historial")).toBeInTheDocument();
  });

  it("si la consulta falla ofrece reintentar", async () => {
    vi.mocked(apiFetch).mockRejectedValue(new Error("boom"));
    renderPanel();
    expect(await screen.findByText("No se pudo consultar la información fiscal de la empresa.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });
});
