import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import { ModalValidacionesYCierre } from "./ModalValidacionesYCierre";
import { Validacion } from "@/hooks/useCierre";

describe("ModalValidacionesYCierre", () => {
  const mockValidaciones: Validacion[] = [
    { nombre: "Al menos 1 ingreso", pasó: true, bloquea: true, mensaje: "OK" },
    { nombre: "Ingresos > 0", pasó: true, bloquea: true, mensaje: "OK" },
    { nombre: "Sin CFDI cancelados", pasó: false, bloquea: false, mensaje: "Hay 2 CFDI cancelados después del cierre" },
  ];

  it("no renderiza cuando open es false", () => {
    const { container } = render(
      <ModalValidacionesYCierre
        open={false}
        onOpenChange={vi.fn()}
        validaciones={mockValidaciones}
        onConfirm={vi.fn()}
      />
    );
    expect(container).toBeEmptyDOMElement();
  });

  it("renderiza cuando open es true", () => {
    render(
      <ModalValidacionesYCierre
        open={true}
        onOpenChange={vi.fn()}
        validaciones={mockValidaciones}
        onConfirm={vi.fn()}
      />
    );
    expect(screen.getByText("Confirmar cierre del período")).toBeInTheDocument();
  });

  it("muestra todas las validaciones", () => {
    render(
      <ModalValidacionesYCierre
        open={true}
        onOpenChange={vi.fn()}
        validaciones={mockValidaciones}
        onConfirm={vi.fn()}
      />
    );
    expect(screen.getByText("Al menos 1 ingreso")).toBeInTheDocument();
    expect(screen.getByText("Ingresos > 0")).toBeInTheDocument();
    expect(screen.getByText("Sin CFDI cancelados")).toBeInTheDocument();
  });

  it("llama onConfirm al hacer clic en Cerrar período", () => {
    const mockOnConfirm = vi.fn();
    render(
      <ModalValidacionesYCierre
        open={true}
        onOpenChange={vi.fn()}
        validaciones={mockValidaciones}
        onConfirm={mockOnConfirm}
      />
    );
    const button = screen.getByText("Cerrar período");
    fireEvent.click(button);
    expect(mockOnConfirm).toHaveBeenCalled();
  });

  it("llama onOpenChange cuando se hace clic en Cancelar", () => {
    const mockOnOpenChange = vi.fn();
    render(
      <ModalValidacionesYCierre
        open={true}
        onOpenChange={mockOnOpenChange}
        validaciones={mockValidaciones}
        onConfirm={vi.fn()}
      />
    );
    const button = screen.getByText("Cancelar");
    fireEvent.click(button);
    expect(mockOnOpenChange).toHaveBeenCalledWith(false);
  });

  it("deshabilita botones cuando loading es true", () => {
    render(
      <ModalValidacionesYCierre
        open={true}
        onOpenChange={vi.fn()}
        validaciones={mockValidaciones}
        onConfirm={vi.fn()}
        loading={true}
      />
    );
    expect(screen.getByText("Cerrando...")).toBeDisabled();
    expect(screen.getByText("Cancelar")).toBeDisabled();
  });
});
