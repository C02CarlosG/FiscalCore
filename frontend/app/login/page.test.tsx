import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import LoginPage from "./page";
import { getToken } from "@/lib/auth";

const replaceMock = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
}));

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

function renderLoginPage() {
  const queryClient = new QueryClient();
  return render(
    <QueryClientProvider client={queryClient}>
      <LoginPage />
    </QueryClientProvider>,
  );
}

describe("LoginPage", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    vi.mocked(apiFetch).mockReset();
    window.localStorage.clear();
  });

  it("shows a validation error when fields are empty", async () => {
    const user = userEvent.setup();
    renderLoginPage();

    await user.click(screen.getByRole("button", { name: /entrar/i }));

    expect(
      screen.getByText("Correo y contraseña son obligatorios"),
    ).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("logs in and redirects to /empresas on success", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      access_token: "token-123",
      token_type: "bearer",
      user_id: "u1",
      email: "test@example.com",
      nombre: "Test",
      empresas: [],
    });
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Correo"), "test@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "secreto123");
    await user.click(screen.getByRole("button", { name: /entrar/i }));

    await waitFor(() => expect(replaceMock).toHaveBeenCalledWith("/empresas"));
    expect(getToken()).toBe("token-123");
  });

  it("shows the backend error message on invalid credentials", async () => {
    const { ApiError } = await import("@/lib/api-client");
    vi.mocked(apiFetch).mockRejectedValue(
      new ApiError(401, "Credenciales incorrectas"),
    );
    const user = userEvent.setup();
    renderLoginPage();

    await user.type(screen.getByLabelText("Correo"), "test@example.com");
    await user.type(screen.getByLabelText("Contraseña"), "mala-clave");
    await user.click(screen.getByRole("button", { name: /entrar/i }));

    await waitFor(() =>
      expect(screen.getByText("Credenciales incorrectas")).toBeInTheDocument(),
    );
  });
});
