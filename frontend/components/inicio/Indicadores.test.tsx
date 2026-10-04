import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { Indicadores } from "./Indicadores";
import { resumen } from "./fixtures";

describe("Indicadores", () => {
  it("muestra ingresos y gastos netos del periodo y del ejercicio", () => {
    render(<Indicadores resumen={resumen()} />);

    const seccion = screen.getByRole("region", { name: "Ingresos y gastos" });
    expect(within(seccion).getByText("Ingresos netos del periodo").closest(".min-w-0")).toHaveTextContent("$21,407,798.40");
    expect(within(seccion).getByText("Ingresos netos del ejercicio").closest(".min-w-0")).toHaveTextContent("$216,844,592.64");
    expect(within(seccion).getByText("Gastos netos del periodo").closest(".min-w-0")).toHaveTextContent("$12,803,855.07");
    expect(within(seccion).getByText("Gastos netos del ejercicio").closest(".min-w-0")).toHaveTextContent("$100,000.00");
  });

  it("indica el número de CFDI de ingresos del periodo", () => {
    render(<Indicadores resumen={resumen()} />);

    expect(screen.getByText("153 CFDI de ingreso y notas de crédito")).toBeInTheDocument();
  });

  it("la nómina del periodo se muestra aparte y aclara que no está en los gastos", () => {
    render(<Indicadores resumen={resumen()} />);

    expect(screen.getByText(/Nómina del periodo: \$2,195,408\.04/)).toBeInTheDocument();
    expect(screen.getByText(/no incluida en los gastos netos/)).toBeInTheDocument();
  });

  it("sin nómina no dibuja esa línea", () => {
    const r = resumen();
    r.gastos.periodo.nomina = 0;

    render(<Indicadores resumen={r} />);

    expect(screen.queryByText(/Nómina del periodo/)).not.toBeInTheDocument();
  });

  it("una empresa sin movimientos muestra ceros, no guiones", () => {
    const vacio = { facturado: 0, notas_credito: 0, neto: 0, cfdi: 0 };
    render(<Indicadores resumen={resumen({ ingresos: { periodo: vacio, acumulado: vacio } })} />);

    expect(screen.getByText("Ingresos netos del periodo").closest(".min-w-0")).toHaveTextContent("$0.00");
  });
});
