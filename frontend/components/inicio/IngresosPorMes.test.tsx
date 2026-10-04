import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { IngresosPorMes } from "./IngresosPorMes";
import { meses } from "./fixtures";

describe("IngresosPorMes", () => {
  it("lista los 12 meses con facturado, notas de crédito, neto y CFDI", () => {
    render(<IngresosPorMes meses={meses()} periodo="2026-09" />);

    const tabla = screen.getByRole("table", { name: "Ingresos por mes" });
    expect(within(tabla).getAllByRole("row")).toHaveLength(1 + 12 + 1);          // encabezado + meses + total
    expect(within(tabla).getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Mes", "Facturado", "Notas de crédito", "Neto", "CFDI",
    ]);
    const septiembre = within(tabla).getByRole("row", { name: /2026 - Septiembre/ });
    expect(septiembre).toHaveTextContent("$12,100.00");
    expect(septiembre).toHaveTextContent("$100.00");
    expect(septiembre).toHaveTextContent("$12,000.00");
  });

  it("el renglón de total suma los 12 meses sin error de redondeo", () => {
    const m = meses().map((x) => ({ ...x, ingresos: { facturado: 0.1, notas_credito: 0, neto: 0.1, cfdi: 1 } }));

    render(<IngresosPorMes meses={m} periodo="2026-09" />);

    const total = screen.getByRole("row", { name: /^Total/ });
    expect(total).toHaveTextContent("$1.20");           // 12 × 0.10, no 1.2000000000000002
    expect(total).toHaveTextContent("12");
  });

  it("marca el mes elegido", () => {
    render(<IngresosPorMes meses={meses()} periodo="2026-09" />);

    expect(screen.getByRole("row", { name: /2026 - Septiembre/ })).toHaveAttribute("aria-current", "true");
    expect(screen.getByRole("row", { name: /2026 - Agosto/ })).not.toHaveAttribute("aria-current");
  });

  it("el neto negativo se muestra con su signo", () => {
    const m = meses();
    m[0] = { ...m[0], ingresos: { facturado: 0, notas_credito: 500, neto: -500, cfdi: 1 } };

    render(<IngresosPorMes meses={m} periodo="2026-09" />);

    expect(screen.getByRole("row", { name: /2025 - Octubre/ })).toHaveTextContent("-$500.00");
  });
});
