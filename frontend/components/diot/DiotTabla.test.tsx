import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiotTabla } from "./DiotTabla";
import { diotFlujo, tercero } from "./fixtures";

const totales = diotFlujo().totales;

describe("DiotTabla", () => {
  it("muestra las cifras del tercero y el total", () => {
    render(<DiotTabla terceros={[tercero()]} totales={totales} guardando={false} onClasificar={vi.fn()} />);

    const fila = screen.getByRole("row", { name: /PROVEEDOR UNO/ });
    expect(within(fila).getByText("PRO010101AAA")).toBeInTheDocument();
    expect(within(fila).getAllByText("$1,500.00").length).toBeGreaterThan(0);
    expect(within(fila).getByText("$224.00")).toBeInTheDocument();
    expect(screen.getByRole("row", { name: /Total · 1 terceros/ })).toBeInTheDocument();
  });

  it("sin compras dice que no hay nada en el periodo", () => {
    render(<DiotTabla terceros={[]} totales={totales} guardando={false} onClasificar={vi.fn()} />);

    expect(screen.getByText(/No hay compras con efecto/)).toBeInTheDocument();
    expect(screen.queryByRole("table")).not.toBeInTheDocument();
  });

  it("cambiar el tipo de operación o de tercero guarda la clasificación del proveedor", async () => {
    const onClasificar = vi.fn();
    render(<DiotTabla terceros={[tercero()]} totales={totales} guardando={false} onClasificar={onClasificar} />);

    await userEvent.selectOptions(screen.getByLabelText("Tipo de operación de PROVEEDOR UNO"), "06");
    await userEvent.selectOptions(screen.getByLabelText("Tipo de tercero de PROVEEDOR UNO"), "15");

    expect(onClasificar).toHaveBeenNthCalledWith(1, "p1", { tipo_operacion: "06" });
    expect(onClasificar).toHaveBeenNthCalledWith(2, "p1", { tipo_tercero: "15" });
  });

  it("quitar la selección manda null para volver al catálogo", async () => {
    const onClasificar = vi.fn();
    render(<DiotTabla terceros={[tercero()]} totales={totales} guardando={false} onClasificar={onClasificar} />);

    await userEvent.selectOptions(screen.getByLabelText("Tipo de operación de PROVEEDOR UNO"), "");

    expect(onClasificar).toHaveBeenCalledWith("p1", { tipo_operacion: null });
  });

  it("un tercero que no está en el catálogo no se puede clasificar y avisa por qué", () => {
    render(
      <DiotTabla
        terceros={[tercero({ proveedor_id: null, tipo_tercero: null, tipo_operacion: null, advertencias: ["sin_catalogo", "sin_tipo_tercero"] })]}
        totales={totales}
        guardando={false}
        onClasificar={vi.fn()}
      />,
    );

    expect(screen.getByLabelText("Tipo de operación de PROVEEDOR UNO")).toBeDisabled();
    const avisos = screen.getByRole("list", { name: "Advertencias de PROVEEDOR UNO" });
    expect(within(avisos).getByText("No está en el catálogo de proveedores")).toBeInTheDocument();
    expect(within(avisos).getByText("Falta el tipo de tercero")).toBeInTheDocument();
  });

  it("mientras guarda bloquea los selectores", () => {
    render(<DiotTabla terceros={[tercero()]} totales={totales} guardando onClasificar={vi.fn()} />);

    expect(screen.getByLabelText("Tipo de tercero de PROVEEDOR UNO")).toBeDisabled();
  });

  it("el IVA no acreditable explica sus motivos al pasar el cursor", () => {
    const t = tercero({
      iva_no_acreditable: { proporcion: 0, total: 800, por_motivo: { efectivo: { cfdi: 1, iva: 800, base: 5000 } } },
    });
    render(<DiotTabla terceros={[t]} totales={totales} guardando={false} onClasificar={vi.fn()} />);

    expect(screen.getByText("$800.00")).toHaveAttribute("title", "Efectivo mayor a $2,000: $800.00");
  });

  it("dos operaciones del mismo tercero son dos renglones", () => {
    render(
      <DiotTabla
        terceros={[tercero({ tipo_operacion: "85" }), tercero({ tipo_operacion: "06", cfdi: 1 })]}
        totales={totales}
        guardando={false}
        onClasificar={vi.fn()}
      />,
    );

    expect(screen.getAllByLabelText("Tipo de operación de PROVEEDOR UNO")).toHaveLength(2);
  });
});
