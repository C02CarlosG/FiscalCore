import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { UsuariosEmpresa } from "./UsuariosEmpresa";
import type { UsuariosDeEmpresa } from "./tipos";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

const BASE = "/api/v1/cuenta/empresas/e1/usuarios";

const datos = (puede: boolean): UsuariosDeEmpresa => ({
  mi_rol: puede ? "administrador" : "contador",
  puede_administrar: puede,
  usuarios: [
    { usuario_id: "u1", email: "carlos@despacho.mx", nombre: "Carlos", rol: "administrador", desde: "2026-01-01T00:00:00+00:00", soy_yo: puede },
    { usuario_id: "u2", email: "ana@despacho.mx", nombre: "Ana", rol: "contador", desde: "2026-02-01T00:00:00+00:00", soy_yo: !puede },
  ],
});

function renderUsuarios(puede = true) {
  vi.mocked(apiFetch).mockImplementation(async (ruta: string, opciones?: RequestInit) => {
    if (ruta === BASE && !opciones?.method) return datos(puede);
    if (opciones?.method) return {};
    throw new Error(`llamada inesperada: ${ruta}`);
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <UsuariosEmpresa empresaId="e1" />
    </QueryClientProvider>,
  );
}

describe("UsuariosEmpresa", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("lista a los usuarios con su rol", async () => {
    renderUsuarios();
    expect(await screen.findByText("ana@despacho.mx")).toBeInTheDocument();
    expect(screen.getByText("(tú)")).toBeInTheDocument();
  });

  it("un contador ve la lista sin poder cambiarla", async () => {
    renderUsuarios(false);
    await screen.findByText("ana@despacho.mx");
    expect(screen.getByText(/Solo un administrador de la empresa/)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Dar acceso" })).not.toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: /Rol de/ })).not.toBeInTheDocument();
  });

  it("da de alta con contraseña temporal", async () => {
    const user = userEvent.setup();
    renderUsuarios();
    await screen.findByText("ana@despacho.mx");
    const form = screen.getByRole("form", { name: "Dar acceso a la empresa" });
    await user.type(within(form).getByLabelText("Correo"), "luis@despacho.mx");
    await user.type(within(form).getByLabelText("Nombre (si no tiene cuenta)"), "Luis");
    await user.type(within(form).getByLabelText("Contraseña temporal (si no tiene cuenta)"), "Temporal-123");
    await user.click(within(form).getByRole("button", { name: "Dar acceso" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(BASE, {
        method: "POST",
        body: JSON.stringify({ email: "luis@despacho.mx", rol: "contador", nombre: "Luis", password_temporal: "Temporal-123" }),
      }),
    );
  });

  it("muestra el error del backend al dar de alta", async () => {
    const user = userEvent.setup();
    renderUsuarios();
    await screen.findByText("ana@despacho.mx");
    vi.mocked(apiFetch).mockRejectedValueOnce(new ApiError(409, "Esa persona ya tiene acceso a la empresa"));
    const form = screen.getByRole("form", { name: "Dar acceso a la empresa" });
    await user.type(within(form).getByLabelText("Correo"), "ana@despacho.mx");
    await user.click(within(form).getByRole("button", { name: "Dar acceso" }));
    expect(await screen.findByText("Esa persona ya tiene acceso a la empresa")).toBeInTheDocument();
  });

  it("cambia el rol de una fila", async () => {
    const user = userEvent.setup();
    renderUsuarios();
    await screen.findByText("ana@despacho.mx");
    await user.selectOptions(screen.getByRole("combobox", { name: "Rol de ana@despacho.mx" }), "administrador");
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(`${BASE}/u2`, { method: "PATCH", body: JSON.stringify({ rol: "administrador" }) }),
    );
  });

  it("quita el acceso solo después de confirmar", async () => {
    const user = userEvent.setup();
    renderUsuarios();
    await screen.findByText("ana@despacho.mx");
    await user.click(screen.getByRole("button", { name: "Quitar acceso a ana@despacho.mx" }));
    expect(apiFetch).not.toHaveBeenCalledWith(`${BASE}/u2`, { method: "DELETE" });
    await user.click(screen.getByRole("button", { name: "Confirmar: quitar acceso a ana@despacho.mx" }));
    await waitFor(() => expect(apiFetch).toHaveBeenCalledWith(`${BASE}/u2`, { method: "DELETE" }));
  });
});
