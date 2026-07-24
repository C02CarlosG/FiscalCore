import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { CfdiUploadForm } from "./CfdiUploadForm";

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
      <CfdiUploadForm empresaId="e1" />
    </QueryClientProvider>,
  );
}

describe("CfdiUploadForm", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("shows a validation error when there is no periodo", async () => {
    const user = userEvent.setup();
    renderForm();

    const file = new File(["<xml></xml>"], "cfdi.xml", { type: "text/xml" });
    await user.upload(screen.getByLabelText("Archivos XML"), file);
    await user.click(screen.getByRole("button", { name: /subir cfdi/i }));

    expect(screen.getByText("El periodo es obligatorio")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("shows a validation error when there are no files", async () => {
    const user = userEvent.setup();
    renderForm();

    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    await user.click(screen.getByRole("button", { name: /subir cfdi/i }));

    expect(
      screen.getByText("Selecciona al menos un archivo XML"),
    ).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("submits FormData with the files and periodo", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      mensaje: "1 CFDI procesado correctamente",
      registros_procesados: 1,
      errores: [],
      periodo: "2026-07",
    });
    const user = userEvent.setup();
    renderForm();

    const file = new File(["<xml></xml>"], "cfdi.xml", { type: "text/xml" });
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    await user.upload(screen.getByLabelText("Archivos XML"), file);
    await user.click(screen.getByRole("button", { name: /subir cfdi/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    const [path, options] = vi.mocked(apiFetch).mock.calls[0];
    expect(path).toBe("/api/v1/empresas/e1/cfdi/upload");
    const body = options?.body as FormData;
    expect(body.get("periodo")).toBe("2026-07");
    expect((body.get("archivos") as File).name).toBe("cfdi.xml");
  });

  it("shows the result summary including partial errors", async () => {
    vi.mocked(apiFetch).mockResolvedValue({
      mensaje: "1 CFDI procesado correctamente",
      registros_procesados: 1,
      errores: ["otro.xml: UUID duplicado"],
      periodo: "2026-07",
    });
    const user = userEvent.setup();
    renderForm();

    const file = new File(["<xml></xml>"], "cfdi.xml", { type: "text/xml" });
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    await user.upload(screen.getByLabelText("Archivos XML"), file);
    await user.click(screen.getByRole("button", { name: /subir cfdi/i }));

    await waitFor(() =>
      expect(screen.getByText("otro.xml: UUID duplicado")).toBeInTheDocument(),
    );
  });

  it("shows the backend error message on failure", async () => {
    vi.mocked(apiFetch).mockRejectedValue(
      new ApiError(400, "Archivo con extensión inválida"),
    );
    const user = userEvent.setup();
    renderForm();

    const file = new File(["not xml"], "cfdi.txt", { type: "text/plain" });
    await user.type(screen.getByLabelText("Periodo (YYYY-MM)"), "2026-07");
    await user.upload(screen.getByLabelText("Archivos XML"), file);
    await user.click(screen.getByRole("button", { name: /subir cfdi/i }));

    await waitFor(() =>
      expect(
        screen.getByText("Archivo con extensión inválida"),
      ).toBeInTheDocument(),
    );
  });
});
