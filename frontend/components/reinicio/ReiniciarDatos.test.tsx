import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ReiniciarDatos } from "./ReiniciarDatos";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

const BASE = "/api/v1/reinicio/empresas/e1";
const VISTA = {
  conteos: { cfdi: 120, pagos_cfdi: 4, sat_solicitudes: 2 },
  total_cfdi: 120,
  frase: "REINICIAR ACM010101AA1",
  token: "tok",
  expira_en: "2026-10-06T19:00:00+00:00",
};

function renderReinicio(puede = true) {
  vi.mocked(apiFetch).mockImplementation(async (ruta: string) => {
    if (ruta === "/api/v1/cuenta/empresas/e1/usuarios") {
      return { mi_rol: puede ? "administrador" : "contador", puede_administrar: puede, usuarios: [], invitaciones: [], por_aprobar: [] };
    }
    if (ruta === `${BASE}/previsualizar`) return VISTA;
    if (ruta === `${BASE}/confirmar`) return { borrados: { cfdi: 120 }, sincronizacion_pausada: true };
    throw new Error(`llamada inesperada: ${ruta}`);
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ReiniciarDatos empresaId="e1" />
    </QueryClientProvider>,
  );
}

describe("ReiniciarDatos", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("un contador no ve el botón", async () => {
    renderReinicio(false);
    expect(await screen.findByText(/Solo un administrador/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ver qué se borraría" })).not.toBeInTheDocument();
  });

  it("muestra los conteos y solo habilita reiniciar con la frase exacta y la contraseña", async () => {
    const user = userEvent.setup();
    renderReinicio();
    await user.click(await screen.findByRole("button", { name: "Ver qué se borraría" }));
    const form = await screen.findByRole("form", { name: "Confirmar reinicio" });
    const tabla = within(form).getByRole("table", { name: "Registros que se borrarán" });
    expect(within(tabla).getByText("120")).toBeInTheDocument();
    const boton = within(form).getByRole("button", { name: "Reiniciar datos" });
    await user.type(within(form).getByLabelText("Frase de confirmación"), "REINICIAR");
    await user.type(within(form).getByLabelText("Tu contraseña"), "secreta");
    expect(boton).toBeDisabled();
    await user.type(within(form).getByLabelText("Frase de confirmación"), " ACM010101AA1");
    expect(boton).toBeEnabled();
    await user.click(boton);
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(`${BASE}/confirmar`, {
        method: "POST",
        body: JSON.stringify({ token: "tok", frase: "REINICIAR ACM010101AA1", contrasena: "secreta" }),
      }),
    );
    expect(await screen.findByText("Datos reiniciados.")).toBeInTheDocument();
    expect(screen.getByText(/quedó pausada/)).toBeInTheDocument();
  });
});
