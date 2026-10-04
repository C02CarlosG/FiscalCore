import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { PerfilForm } from "./PerfilForm";
import { CambiarContrasenaForm } from "./CambiarContrasenaForm";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

const perfil = {
  id: "u1", email: "carlos@despacho.mx", nombre: "Carlos", telefono: null, rfc: null,
  nombre_despacho: "Despacho Oaxaca", cedula_profesional: null,
};

function renderCon(ui: React.ReactElement) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("PerfilForm", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockImplementation(async (ruta: string, opciones?: RequestInit) => {
      if (ruta === "/api/v1/auth/me") return perfil;
      if (ruta === "/api/v1/usuarios/perfil") return { ...perfil, ...JSON.parse(String(opciones?.body)) };
      throw new Error(`llamada inesperada: ${ruta}`);
    });
  });

  it("carga el perfil y guarda solo lo que cambió", async () => {
    const user = userEvent.setup();
    renderCon(<PerfilForm />);
    expect(await screen.findByDisplayValue("Carlos")).toBeInTheDocument();
    expect(screen.getByText("carlos@despacho.mx")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Teléfono"), "9511234567");
    await user.type(screen.getByLabelText("RFC"), "gahc800101ab3");
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/v1/usuarios/perfil", {
        method: "PATCH",
        body: JSON.stringify({ telefono: "9511234567", rfc: "GAHC800101AB3" }),
      }),
    );
    expect(await screen.findByText("Perfil guardado")).toBeInTheDocument();
  });

  it("sin cambios no llama a la API", async () => {
    const user = userEvent.setup();
    renderCon(<PerfilForm />);
    await screen.findByDisplayValue("Carlos");
    await user.click(screen.getByRole("button", { name: "Guardar perfil" }));
    expect(await screen.findByText("No hay cambios que guardar")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledTimes(1);
  });
});

describe("CambiarContrasenaForm", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  async function llenar(actual: string, nueva: string, confirmar: string) {
    const user = userEvent.setup();
    await user.type(screen.getByLabelText("Contraseña actual"), actual);
    await user.type(screen.getByLabelText("Contraseña nueva"), nueva);
    await user.type(screen.getByLabelText("Confirma la contraseña nueva"), confirmar);
    await user.click(screen.getByRole("button", { name: "Cambiar contraseña" }));
  }

  it("valida longitud y confirmación antes de llamar a la API", async () => {
    renderCon(<CambiarContrasenaForm />);
    await llenar("Actual-123", "corta", "corta");
    expect(await screen.findByText("La contraseña nueva debe tener al menos 8 caracteres")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("avisa si la confirmación no coincide", async () => {
    renderCon(<CambiarContrasenaForm />);
    await llenar("Actual-123", "Nueva-Clave-1", "Nueva-Clave-2");
    expect(await screen.findByText("La confirmación no coincide")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("cambia la contraseña y limpia el formulario", async () => {
    vi.mocked(apiFetch).mockResolvedValue(undefined);
    renderCon(<CambiarContrasenaForm />);
    await llenar("Actual-123", "Nueva-Clave-1", "Nueva-Clave-1");
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/v1/cuenta/contrasena", {
        method: "POST",
        body: JSON.stringify({ actual: "Actual-123", nueva: "Nueva-Clave-1" }),
      }),
    );
    expect(await screen.findByText("Contraseña actualizada")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña actual")).toHaveValue("");
  });

  it("muestra el error del backend", async () => {
    vi.mocked(apiFetch).mockRejectedValue(new ApiError(400, "La contraseña actual no es correcta"));
    renderCon(<CambiarContrasenaForm />);
    await llenar("Mala-123", "Nueva-Clave-1", "Nueva-Clave-1");
    expect(await screen.findByText("La contraseña actual no es correcta")).toBeInTheDocument();
  });
});
