import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EmpresaForm } from "./EmpresaForm";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

function renderForm(onCreated = vi.fn()) {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <EmpresaForm onCreated={onCreated} />
    </QueryClientProvider>,
  );
  return { onCreated };
}

describe("EmpresaForm", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("shows required-field errors and does not call the API", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(screen.getByText("El RFC es obligatorio")).toBeInTheDocument();
    expect(screen.getByText("La razón social es obligatoria")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("rejects an RFC with an invalid length", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("RFC"), "ABC123");
    await user.type(screen.getByLabelText("Razón social"), "Acme SA de CV");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    expect(
      screen.getByText("El RFC debe tener 12 o 13 caracteres"),
    ).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("submits and calls onCreated on success", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      mensaje: "Empresa vinculada correctamente",
      empresa_id: "e1",
      rfc: "AAA010101AAA",
      razon_social: "Acme SA de CV",
    });
    const user = userEvent.setup();
    const { onCreated } = renderForm();

    await user.type(screen.getByLabelText("RFC"), "aaa010101aaa");
    await user.type(screen.getByLabelText("Razón social"), "Acme SA de CV");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledTimes(1));
    const [, options] = vi.mocked(apiFetch).mock.calls[0];
    expect(JSON.parse((options as RequestInit).body as string)).toEqual({
      rfc: "AAA010101AAA",
      razon_social: "Acme SA de CV",
    });
  });

  it("shows field errors returned by the backend", async () => {
    vi.mocked(apiFetch).mockRejectedValue(
      new ApiError(422, "Solicitud inválida", { rfc: "RFC ya registrado" }),
    );
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("RFC"), "aaa010101aaa");
    await user.type(screen.getByLabelText("Razón social"), "Acme SA de CV");
    await user.click(screen.getByRole("button", { name: /guardar/i }));

    await waitFor(() =>
      expect(screen.getByText("RFC ya registrado")).toBeInTheDocument(),
    );
  });
});
