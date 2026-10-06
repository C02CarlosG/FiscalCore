import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CfdiToolbar } from "./CfdiToolbar";

vi.mock("@/hooks/useNotasCfdi", () => ({
  useEtiquetas: () => ({ data: [{ id: "11111111-1111-4111-8111-111111111111", nombre: "Revisar", color: "#ff0000", cfdis: 2 }] }),
}));
import { leerEstado } from "@/lib/cfdi-url";

const estado = (texto = "") => leerEstado(new URLSearchParams(texto), "2026-09");

function renderBarra(texto = "", onCambio = vi.fn()) {
  render(<CfdiToolbar empresaId="e1" estado={estado(texto)} periodosConDatos={["2026-09"]} onCambio={onCambio} />);
  return onCambio;
}

describe("CfdiToolbar", () => {
  afterEach(() => vi.useRealTimers());

  it("muestra el periodo elegido", () => {
    renderBarra();

    expect(screen.getByRole("combobox", { name: "Periodo" })).toHaveTextContent("2026 - Septiembre");
  });

  it("marca el estado y el método actuales", () => {
    renderBarra("estado=cancelado&metodo=PUE");

    expect(screen.getByRole("button", { name: "Cancelados" })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: "Vigentes" })).toHaveAttribute("aria-pressed", "false");
    expect(screen.getByRole("button", { name: "PUE" })).toHaveAttribute("aria-pressed", "true");
  });

  it("cambiar el estado avisa solo ese parche", async () => {
    const user = userEvent.setup();
    const onCambio = renderBarra();

    await user.click(screen.getByRole("button", { name: "Todos los estados" }));

    expect(onCambio).toHaveBeenCalledWith({ estado: "todos" });
  });

  it("cambiar el método avisa solo ese parche", async () => {
    const user = userEvent.setup();
    const onCambio = renderBarra();

    await user.click(screen.getByRole("button", { name: "PPD" }));

    expect(onCambio).toHaveBeenCalledWith({ metodo: "PPD" });
  });

  it("el sub-filtro de pago solo aparece con PPD", () => {
    renderBarra("metodo=PUE");
    expect(screen.queryByRole("button", { name: "Pendientes de pago" })).not.toBeInTheDocument();
  });

  it("con PPD ofrece pendientes, pagadas y todas", async () => {
    const user = userEvent.setup();
    const onCambio = renderBarra("metodo=PPD&pago=pendientes");

    expect(screen.getByRole("button", { name: "Pendientes de pago" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Pagadas" }));

    expect(onCambio).toHaveBeenCalledWith({ pago: "pagadas" });
  });

  describe("búsqueda", () => {
    beforeEach(() => vi.useFakeTimers());

    it("espera 300 ms sin teclear y avisa una sola vez", () => {
      const onCambio = renderBarra();
      const caja = screen.getByRole("searchbox", { name: "Buscar" });

      fireEvent.change(caja, { target: { value: "a" } });
      act(() => vi.advanceTimersByTime(200));
      fireEvent.change(caja, { target: { value: "abc" } });
      act(() => vi.advanceTimersByTime(299));
      expect(onCambio).not.toHaveBeenCalled();

      act(() => vi.advanceTimersByTime(1));

      expect(onCambio).toHaveBeenCalledTimes(1);
      expect(onCambio).toHaveBeenCalledWith({ q: "abc" });
    });

    it("muestra la búsqueda que viene en la URL y no la reenvía", () => {
      const onCambio = renderBarra("q=pemex");

      expect(screen.getByRole("searchbox", { name: "Buscar" })).toHaveValue("pemex");
      act(() => vi.advanceTimersByTime(1000));
      expect(onCambio).not.toHaveBeenCalled();
    });

    it("quita espacios sobrantes antes de buscar", () => {
      const onCambio = renderBarra();

      fireEvent.change(screen.getByRole("searchbox", { name: "Buscar" }), { target: { value: "  abc  " } });
      act(() => vi.advanceTimersByTime(300));

      expect(onCambio).toHaveBeenCalledWith({ q: "abc" });
    });
  });
});
