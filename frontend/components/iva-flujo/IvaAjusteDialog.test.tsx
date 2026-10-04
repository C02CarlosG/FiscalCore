import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IvaAjusteDialog } from "./IvaAjusteDialog";
import { renglon } from "./fixtures";

function abrir(props: Partial<React.ComponentProps<typeof IvaAjusteDialog>> = {}) {
  const onConfirmar = vi.fn();
  const onCerrar = vi.fn();
  render(
    <IvaAjusteDialog accion="excluir" renglon={renglon()} periodo="2026-09" enviando={false} error={null}
      onConfirmar={onConfirmar} onCerrar={onCerrar} {...props} />,
  );
  return { onConfirmar, onCerrar };
}

describe("IvaAjusteDialog", () => {
  it("cerrado (sin renglón) no pinta nada", () => {
    abrir({ renglon: null });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
  });

  it("no considerar pide solo el motivo y no se puede guardar vacío", async () => {
    const user = userEvent.setup();
    const { onConfirmar } = abrir();

    expect(screen.getByRole("dialog", { name: "No considerar CFDI" })).toBeInTheDocument();
    expect(screen.queryByLabelText("Periodo destino")).not.toBeInTheDocument();
    const guardar = screen.getByRole("button", { name: "Guardar" });
    expect(guardar).toBeDisabled();

    await user.type(screen.getByLabelText("Motivo"), "   ");
    expect(guardar).toBeDisabled();
    await user.type(screen.getByLabelText("Motivo"), "factura duplicada");
    expect(guardar).toBeEnabled();
    await user.click(guardar);

    expect(onConfirmar).toHaveBeenCalledWith({ motivo: "factura duplicada" });
  });

  it("reasignar pide además el periodo destino, por defecto el mes siguiente", async () => {
    const user = userEvent.setup();
    const { onConfirmar } = abrir({ accion: "reasignar" });

    expect(screen.getByRole("dialog", { name: "Reasignar periodo" })).toBeInTheDocument();
    expect(screen.getByLabelText("Periodo destino")).toHaveValue("2026-10");
    await user.type(screen.getByLabelText("Motivo"), "se cobró en octubre");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onConfirmar).toHaveBeenCalledWith({ motivo: "se cobró en octubre", periodo_destino: "2026-10" });
  });

  it("no deja guardar si el periodo destino es inválido", async () => {
    const user = userEvent.setup();
    abrir({ accion: "reasignar" });

    await user.clear(screen.getByLabelText("Periodo destino"));
    await user.type(screen.getByLabelText("Motivo"), "x");

    expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
  });

  it("muestra el error del servidor y bloquea mientras guarda", () => {
    abrir({ error: "el periodo destino es el mismo de la emisión", enviando: true });

    expect(screen.getByRole("alert")).toHaveTextContent("el periodo destino es el mismo de la emisión");
    expect(screen.getByRole("button", { name: "Guardando…" })).toBeDisabled();
  });

  it("cancelar cierra", async () => {
    const user = userEvent.setup();
    const { onCerrar } = abrir();

    await user.click(screen.getByRole("button", { name: "Cancelar" }));

    expect(onCerrar).toHaveBeenCalled();
  });

  it("nombra el CFDI que se ajusta", () => {
    abrir();

    expect(screen.getByText(/1F3A0001-0000-4000-8000-000000000000/)).toBeInTheDocument();
  });
});
