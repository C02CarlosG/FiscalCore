import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IvaAnual } from "./IvaAnual";
import { ivaAnual } from "./fixtures";

describe("IvaAnual", () => {
  it("abre en Trasladado cobrado con los 12 meses y su total", () => {
    render(<IvaAnual datos={ivaAnual()} periodo="2026-12" />);

    expect(screen.getByRole("tab", { name: "Trasladado cobrado" })).toHaveAttribute("aria-selected", "true");
    const tabla = screen.getByRole("table", { name: "IVA trasladado cobrado por mes" });
    expect(within(tabla).getAllByRole("row")).toHaveLength(1 + 12 + 1);
    expect(within(tabla).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Mes", "PUE", "PPD cobrado", "Notas de crédito", "Total",
    ]);
    expect(within(tabla).getByRole("row", { name: /2026 - Marzo/ })).toHaveTextContent("$480.00");
    expect(within(tabla).getByRole("row", { name: /^Total/ })).toHaveTextContent("$12,480.00");
  });

  it("Acreditable pagado muestra el efectivo excluido y el IVA ajustado", async () => {
    const user = userEvent.setup();
    render(<IvaAnual datos={ivaAnual()} periodo="2026-12" />);

    await user.click(screen.getByRole("tab", { name: "Acreditable pagado" }));

    const tabla = screen.getByRole("table", { name: "IVA acreditable pagado por mes" });
    expect(within(tabla).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Mes", "PUE", "PPD pagado", "Notas de crédito", "Efectivo excluido", "Acreditable",
    ]);
    expect(within(tabla).getByRole("row", { name: /2026 - Enero/ })).toHaveTextContent("$100.00");
    expect(within(tabla).getByRole("row", { name: /^Total/ })).toHaveTextContent("$7,800.00");
  });

  it("Resultado muestra a cargo y a favor por mes y el total del ejercicio", async () => {
    const user = userEvent.setup();
    const datos = ivaAnual();
    datos.meses[1].resultado = { iva_retenido: 0, iva_por_pagar: -50, saldo_a_cargo: 0, saldo_a_favor: 50 };
    render(<IvaAnual datos={datos} periodo="2026-12" />);

    await user.click(screen.getByRole("tab", { name: "Resultado" }));

    const tabla = screen.getByRole("table", { name: "Resultado del IVA por mes" });
    expect(within(tabla).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Mes", "Trasladado", "Acreditable", "Retenido", "A cargo", "A favor",
    ]);
    expect(within(tabla).getByRole("row", { name: /2026 - Febrero/ })).toHaveTextContent("$50.00");
    expect(within(tabla).getByRole("row", { name: /^Total/ })).toBeInTheDocument();
  });

  it("los meses posteriores al periodo elegido salen atenuados y sin importes", () => {
    render(<IvaAnual datos={ivaAnual()} periodo="2026-03" />);

    const abril = screen.getByRole("row", { name: /2026 - Abril/ });
    expect(abril).toHaveTextContent("—");
    expect(abril).not.toHaveTextContent("$");
    expect(screen.getByRole("row", { name: /2026 - Marzo/ })).toHaveTextContent("$480.00");
  });

  it("el total solo suma hasta el periodo elegido", () => {
    render(<IvaAnual datos={ivaAnual()} periodo="2026-03" />);

    expect(screen.getByRole("row", { name: /^Total/ })).toHaveTextContent("$960.00");     // 160 + 320 + 480
  });

  it("muestra las advertencias del servidor, con cuántos CFDI afectan, y no dice que coincide con la cédula", () => {
    render(<IvaAnual datos={ivaAnual()} periodo="2026-12" />);

    const lista = screen.getByRole("list", { name: "Advertencias del IVA" });
    expect(within(lista).getAllByRole("listitem")).toHaveLength(2);
    expect(within(lista).getByText(/se estima por la proporción pagada/)).toBeInTheDocument();
    expect(within(lista).getByText("3 CFDI")).toBeInTheDocument();
    expect(within(lista).getByText(/factor de prorrateo del acreditable es 1/)).toBeInTheDocument();
    expect(screen.queryByText(/coincide con la cédula/i)).not.toBeInTheDocument();
  });

  it("sin advertencias no dibuja la lista", () => {
    const datos = ivaAnual();
    datos.advertencias = [];

    render(<IvaAnual datos={datos} periodo="2026-12" />);

    expect(screen.queryByRole("list", { name: "Advertencias del IVA" })).not.toBeInTheDocument();
  });

  it("las pestañas se navegan con el teclado (flechas)", async () => {
    const user = userEvent.setup();
    render(<IvaAnual datos={ivaAnual()} periodo="2026-12" />);

    screen.getByRole("tab", { name: "Trasladado cobrado" }).focus();
    await user.keyboard("{ArrowRight}");

    expect(screen.getByRole("tab", { name: "Acreditable pagado" })).toHaveAttribute("aria-selected", "true");
  });
});
