import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IvaOrigenes } from "./IvaOrigenes";
import { direccionResumen } from "./fixtures";

const renderizar = (props: Partial<React.ComponentProps<typeof IvaOrigenes>> = {}) => {
  const onElegir = vi.fn();
  render(<IvaOrigenes direccion="trasladado" datos={direccionResumen()} origen="contado" onElegir={onElegir} {...props} />);
  return onElegir;
};

describe("IvaOrigenes", () => {
  it("muestra el total y una tarjeta por origen con su IVA", () => {
    renderizar();

    expect(screen.getByRole("group", { name: "Totales" })).toHaveTextContent("$3,190,362.48");
    expect(screen.getByRole("button", { name: /Facturas de contado/ })).toHaveTextContent("$2,275,302.33");
    expect(screen.getByRole("button", { name: /Cobro de facturas de crédito/ })).toHaveTextContent("$915,100.15");
    expect(screen.getByRole("button", { name: /No considerados/ })).toHaveTextContent("134");
    expect(screen.getByRole("button", { name: /Periodo reasignado/ })).toHaveTextContent("2");
  });

  it("crédito muestra pagos contra documentos", () => {
    renderizar();

    expect(screen.getByRole("button", { name: /Cobro de facturas de crédito/ })).toHaveTextContent("95 / 80");
  });

  it("las notas de crédito se ven restando", () => {
    renderizar();

    expect(screen.getByRole("button", { name: /Notas de crédito/ })).toHaveTextContent("-$368.00");
  });

  it("en acreditable el origen de crédito se llama pago", () => {
    renderizar({ direccion: "acreditable" });

    expect(screen.getByRole("button", { name: /Pago de facturas de crédito/ })).toBeInTheDocument();
  });

  it("marca el origen elegido y avisa al elegir otro", async () => {
    const user = userEvent.setup();
    const onElegir = renderizar({ origen: "credito" });

    expect(screen.getByRole("button", { name: /Cobro de facturas/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /Facturas de contado/ })).toHaveAttribute("aria-pressed", "false");

    await user.click(screen.getByRole("button", { name: /No considerados/ }));
    expect(onElegir).toHaveBeenCalledWith("no_considerados");
  });

  it("el desglose por tasa trae base e IVA de cada tasa y las retenciones", () => {
    renderizar();

    const tabla = screen.getByRole("table", { name: "Bases e IVA por tasa" });
    expect(within(tabla).getByRole("row", { name: /^16 %/ })).toHaveTextContent("$19,939,000.00");
    expect(within(tabla).getByRole("row", { name: /^8 %/ })).toHaveTextContent("$500.00");
    expect(within(tabla).getByRole("row", { name: /^0 %/ })).toHaveTextContent("$300.00");
    expect(within(tabla).getByRole("row", { name: /^Exento/ })).toHaveTextContent("$200.00");
    expect(within(tabla).getByRole("row", { name: /^Otras tasas/ })).toBeInTheDocument();
    expect(within(tabla).getByRole("row", { name: /^No objeto/ })).toHaveTextContent("$700.00");
    expect(within(tabla).getByRole("row", { name: /^Retenciones de IVA/ })).toHaveTextContent("$3,786.75");
  });

  it("en acreditable muestra el IVA ajustado por el factor de prorrateo", () => {
    renderizar({ direccion: "acreditable", datos: direccionResumen({ ajustado: 1000 }), factor: 0.5 });

    expect(screen.getByText(/Factor de prorrateo 0\.5/).closest("p")).toHaveTextContent("$1,000.00");
  });
});
