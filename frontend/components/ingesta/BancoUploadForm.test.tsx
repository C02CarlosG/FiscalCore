import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BancoUploadForm } from "./BancoUploadForm";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

function renderForm() {
  const queryClient = new QueryClient();
  render(
    <QueryClientProvider client={queryClient}>
      <BancoUploadForm empresaId="e1" />
    </QueryClientProvider>,
  );
}

describe("BancoUploadForm", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("shows a validation error when there is no periodo", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.selectOptions(screen.getByLabelText("Banco"), "bbva");
    const file = new File(["a,b"], "estado.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Estado de cuenta (.xlsx o .csv)"), file);
    await user.click(
      screen.getByRole("button", { name: /subir estado de cuenta/i }),
    );

    expect(screen.getByText("El periodo es obligatorio")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("shows a validation error when there is no banco", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    const file = new File(["a,b"], "estado.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Estado de cuenta (.xlsx o .csv)"), file);
    await user.click(
      screen.getByRole("button", { name: /subir estado de cuenta/i }),
    );

    expect(screen.getByText("El banco es obligatorio")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("reveals a free-text input when 'Otro' is selected and uses it as the banco value", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      mensaje: "5 movimientos procesados",
      registros_procesados: 5,
      errores: [],
      periodo: "2026-07",
    });
    const user = userEvent.setup();
    renderForm();

    await user.selectOptions(screen.getByLabelText("Banco"), "otro");
    await user.type(screen.getByLabelText("Nombre del banco"), "Banco Azteca");
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    const file = new File(["a,b"], "estado.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Estado de cuenta (.xlsx o .csv)"), file);
    await user.click(
      screen.getByRole("button", { name: /subir estado de cuenta/i }),
    );

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    const [, options] = vi.mocked(apiFetch).mock.calls[0];
    const body = options?.body as FormData;
    expect(body.get("banco")).toBe("Banco Azteca");
  });

  it("submits FormData with the file, banco and periodo for a listed bank", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      mensaje: "5 movimientos procesados",
      registros_procesados: 5,
      errores: [],
      periodo: "2026-07",
    });
    const user = userEvent.setup();
    renderForm();

    await user.selectOptions(screen.getByLabelText("Banco"), "bbva");
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    const file = new File(["a,b"], "estado.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Estado de cuenta (.xlsx o .csv)"), file);
    await user.click(
      screen.getByRole("button", { name: /subir estado de cuenta/i }),
    );

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    const [path, options] = vi.mocked(apiFetch).mock.calls[0];
    expect(path).toBe("/api/v1/empresas/e1/banco/upload");
    const body = options?.body as FormData;
    expect(body.get("banco")).toBe("bbva");
    expect(body.get("periodo")).toBe("2026-07");
    expect((body.get("archivo") as File).name).toBe("estado.csv");
  });

  it("shows the backend error message on failure", async () => {
    vi.mocked(apiFetch).mockRejectedValue(
      new ApiError(400, "No se pudo interpretar el archivo"),
    );
    const user = userEvent.setup();
    renderForm();

    await user.selectOptions(screen.getByLabelText("Banco"), "bbva");
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    const file = new File(["a,b"], "estado.csv", { type: "text/csv" });
    await user.upload(screen.getByLabelText("Estado de cuenta (.xlsx o .csv)"), file);
    await user.click(
      screen.getByRole("button", { name: /subir estado de cuenta/i }),
    );

    await waitFor(() =>
      expect(
        screen.getByText("No se pudo interpretar el archivo"),
      ).toBeInTheDocument(),
    );
  });
});
