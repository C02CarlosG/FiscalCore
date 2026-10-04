import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { HistorialDocumentos } from "./HistorialDocumentos";
import type { DocumentoFiscal } from "./tipos";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn(), apiDescargar: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

const BASE = "/api/v1/informacion-fiscal/empresas/e1";

const docs: DocumentoFiscal[] = [
  {
    id: "d2", tipo: "opinion", nombre_archivo: "32D octubre.pdf", tamano_bytes: 1, rfc: "ACM010101AA1",
    fecha_emision: "2026-10-03", created_at: "2026-10-04T10:00:00+00:00", datos: {},
    antiguedad_dias: 1, vigente_hasta: "2026-11-01", vigente: true, motivo: null,
  },
  {
    id: "d1", tipo: "constancia", nombre_archivo: "CSF.pdf", tamano_bytes: 1, rfc: "ACM010101AA1",
    fecha_emision: "2026-09-01", created_at: "2026-09-02T10:00:00+00:00", datos: {},
    antiguedad_dias: 33, vigente_hasta: null, vigente: null, motivo: null,
  },
];

function renderHistorial() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <HistorialDocumentos empresaId="e1" />
    </QueryClientProvider>,
  );
}

describe("HistorialDocumentos", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockImplementation(async (ruta: string, opciones?: RequestInit) => {
      if (opciones?.method === "DELETE") return undefined;
      if (ruta === `${BASE}/documentos`) return docs;
      throw new Error(`llamada inesperada: ${ruta}`);
    });
  });

  it("lista las cargas con su tipo y fecha de emisión", async () => {
    renderHistorial();
    expect(await screen.findByText("32D octubre.pdf")).toBeInTheDocument();
    expect(screen.getByText("CSF.pdf")).toBeInTheDocument();
    expect(screen.getByText("Opinión de cumplimiento")).toBeInTheDocument();
    expect(screen.getByText("01/09/2026")).toBeInTheDocument();
  });

  it("pide confirmación antes de eliminar", async () => {
    const user = userEvent.setup();
    renderHistorial();
    await screen.findByText("CSF.pdf");

    await user.click(screen.getByRole("button", { name: "Eliminar CSF.pdf" }));
    expect(apiFetch).not.toHaveBeenCalledWith(expect.anything(), expect.objectContaining({ method: "DELETE" }));

    await user.click(screen.getByRole("button", { name: "Confirmar eliminación de CSF.pdf" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(`${BASE}/documentos/d1`, { method: "DELETE" }),
    );
  });

  it("sin cargas lo dice", async () => {
    vi.mocked(apiFetch).mockResolvedValue([]);
    renderHistorial();
    expect(await screen.findByText("Todavía no hay documentos cargados.")).toBeInTheDocument();
  });
});
