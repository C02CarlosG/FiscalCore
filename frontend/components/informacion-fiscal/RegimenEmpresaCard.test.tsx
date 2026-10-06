import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RegimenEmpresaCard } from "./RegimenEmpresaCard";
import type { RegimenEmpresa } from "./tipos";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

const RUTA = "/api/v1/informacion-fiscal/empresas/e1/regimen";

function renderCard(datos: RegimenEmpresa) {
  vi.mocked(apiFetch).mockImplementation(async (ruta: string, opciones?: RequestInit) => {
    if (ruta === RUTA && !opciones?.method) return datos;
    if (opciones?.method === "PUT") return { actual: { codigo: "626", texto: "626 - Régimen Simplificado de Confianza" } };
    throw new Error(`llamada inesperada: ${ruta}`);
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <RegimenEmpresaCard empresaId="e1" />
    </QueryClientProvider>,
  );
}

describe("RegimenEmpresaCard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("sin constancia pide subirla", async () => {
    renderCard({ actual: null, constancia_id: null, detectados: [], sugerido: null });
    expect(await screen.findByText("Sin capturar")).toBeInTheDocument();
    expect(screen.getByText(/Sube la constancia/)).toBeInTheDocument();
  });

  it("sugiere el régimen de la constancia cuando difiere y lo guarda", async () => {
    const user = userEvent.setup();
    renderCard({
      actual: { codigo: "612", texto: "612 - Personas Físicas con Actividades Empresariales y Profesionales" },
      constancia_id: "c1",
      detectados: [
        { codigo: "626", descripcion: "Régimen Simplificado de Confianza", nombre: "Régimen Simplificado de Confianza" },
        { codigo: "612", descripcion: "Personas Físicas con Actividades Empresariales y Profesionales", nombre: "x" },
      ],
      sugerido: "626",
    });
    expect(await screen.findByText(/indica el régimen 626, distinto al de la empresa/)).toBeInTheDocument();
    expect(screen.getByText("En uso")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Usar el régimen 626" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(RUTA, { method: "PUT", body: JSON.stringify({ codigo: "626" }) }),
    );
    expect(await screen.findByText("Régimen 626 guardado en la empresa.")).toBeInTheDocument();
  });
});
