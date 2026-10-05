import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MisInvitaciones } from "./MisInvitaciones";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

const invitacion = {
  id: "i1", rol: "contador", estado: "pendiente", creada: "2026-10-04T00:00:00+00:00", rfc: "ACM010101AA1",
  razon_social: "ACME SA DE CV", invitada_por: "Carlos",
};

function renderInvitaciones(lista: unknown[]) {
  vi.mocked(apiFetch).mockImplementation(async (ruta: string, opciones?: RequestInit) => {
    if (ruta === "/api/v1/cuenta/invitaciones") return lista;
    if (opciones?.method === "POST") return {};
    throw new Error(`llamada inesperada: ${ruta}`);
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MisInvitaciones />
    </QueryClientProvider>,
  );
}

describe("MisInvitaciones", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("no muestra nada si no hay invitaciones", async () => {
    renderInvitaciones([]);
    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    expect(screen.queryByText("Invitaciones")).not.toBeInTheDocument();
  });

  it("acepta una invitación", async () => {
    const user = userEvent.setup();
    renderInvitaciones([invitacion]);
    expect(await screen.findByText("ACME SA DE CV")).toBeInTheDocument();
    expect(screen.getByText(/invita Carlos/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Aceptar invitación de ACME SA DE CV" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/v1/cuenta/invitaciones/i1/aceptar", { method: "POST" }),
    );
  });

  it("rechaza una invitación", async () => {
    const user = userEvent.setup();
    renderInvitaciones([invitacion]);
    await user.click(await screen.findByRole("button", { name: "Rechazar invitación de ACME SA DE CV" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/v1/cuenta/invitaciones/i1/rechazar", { method: "POST" }),
    );
  });

  it("una aceptada muestra que espera aprobación, sin botones", async () => {
    renderInvitaciones([{ ...invitacion, estado: "aceptada_pendiente" }]);
    expect(await screen.findByText("Esperando aprobación")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Aceptar invitación/ })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Rechazar invitación/ })).not.toBeInTheDocument();
  });
});
