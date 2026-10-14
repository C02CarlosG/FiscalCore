import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CriterioEfectivo } from "./CriterioEfectivo";
import { useCambiarCriterioEfectivo, useCriterioEfectivo } from "@/hooks/useCriterioEfectivo";
import { ApiError } from "@/lib/api-client";

vi.mock("@/hooks/useCriterioEfectivo", () => ({ useCriterioEfectivo: vi.fn(), useCambiarCriterioEfectivo: vi.fn() }));

let cambiar: ReturnType<typeof vi.fn>;

function preparar(criterio: "legal" | "estricto") {
  vi.mocked(useCriterioEfectivo).mockReturnValue({
    data: { criterio_efectivo: criterio, umbral_efectivo: criterio === "legal" ? 2000 : 0 },
  } as never);
  cambiar = vi.fn().mockResolvedValue({});
  vi.mocked(useCambiarCriterioEfectivo).mockReturnValue({ mutateAsync: cambiar, isPending: false } as never);
}

describe("CriterioEfectivo", () => {
  beforeEach(() => vi.clearAllMocks());

  it("con criterio legal muestra la opción legal y no la insignia", () => {
    preparar("legal");
    render(<CriterioEfectivo empresaId="e1" />);
    expect(screen.getByLabelText("Criterio de efectivo")).toHaveValue("legal");
    expect(screen.getByRole("option", { name: "Legal (efectivo mayor a $2,000)" })).toBeInTheDocument();
    expect(screen.queryByText("Criterio: Estricto")).not.toBeInTheDocument();
  });

  it("con criterio estricto muestra la insignia", () => {
    preparar("estricto");
    render(<CriterioEfectivo empresaId="e1" />);
    expect(screen.getByLabelText("Criterio de efectivo")).toHaveValue("estricto");
    expect(screen.getByText("Criterio: Estricto")).toBeInTheDocument();
  });

  it("al elegir estricto envía el cambio", async () => {
    preparar("legal");
    render(<CriterioEfectivo empresaId="e1" />);
    await userEvent.selectOptions(screen.getByLabelText("Criterio de efectivo"), "estricto");
    expect(cambiar).toHaveBeenCalledWith("estricto");
  });

  it("si el servidor rechaza el cambio muestra el mensaje y conserva el valor del servidor", async () => {
    preparar("legal");
    cambiar.mockRejectedValue(new ApiError(403, "Solo un administrador de la empresa puede cambiar el criterio de efectivo"));
    render(<CriterioEfectivo empresaId="e1" />);
    await userEvent.selectOptions(screen.getByLabelText("Criterio de efectivo"), "estricto");
    expect(await screen.findByRole("alert")).toHaveTextContent("Solo un administrador");
    await waitFor(() => expect(screen.getByLabelText("Criterio de efectivo")).toHaveValue("legal"));
  });
});
