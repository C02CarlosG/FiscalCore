import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IvaResultado } from "./IvaResultado";
import { resumenIva } from "./fixtures";

describe("IvaResultado", () => {
  it("muestra la resta del mes: trasladado − acreditable − retenciones = IVA por pagar", () => {
    render(<IvaResultado resumen={resumenIva()} />);

    const tabla = screen.getByRole("table", { name: "Resultado del IVA del mes" });
    expect(tabla).toHaveTextContent("IVA trasladado cobrado");
    expect(tabla).toHaveTextContent("$3,190,362.48");
    expect(tabla).toHaveTextContent("-$2,162,403.41");
    expect(tabla).toHaveTextContent("-$3,786.75");
    expect(screen.getByRole("row", { name: /IVA a cargo/ })).toHaveTextContent("$1,024,172.32");
  });

  it("con saldo a favor lo llama así", () => {
    const r = resumenIva();
    r.resultado = { ...r.resultado, iva_por_pagar: -320, saldo_a_cargo: 0, saldo_a_favor: 320 };

    render(<IvaResultado resumen={r} />);

    expect(screen.getByRole("row", { name: /Saldo a favor/ })).toHaveTextContent("$320.00");
  });

  it("avisa de las retenciones que la empresa debe enterar y que no reducen el acreditable", () => {
    render(<IvaResultado resumen={resumenIva()} />);

    expect(screen.getByText(/Retenciones de IVA que la empresa debe enterar/)).toHaveTextContent("$53.34");
    expect(screen.getByText(/no reducen el IVA acreditable/i)).toBeInTheDocument();
  });
});
