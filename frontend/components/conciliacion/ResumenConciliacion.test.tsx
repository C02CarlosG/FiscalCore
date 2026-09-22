import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResumenConciliacion } from "./ResumenConciliacion";
import type { ConciliacionResumen } from "@/types/api";

const resumen: ConciliacionResumen = {
  total: 20,
  exacto: 12,
  parcial: 3,
  sin_cfdi: 4,
  sin_movimiento: 1,
  pct_conciliado: 75,
};

describe("ResumenConciliacion", () => {
  it("renders the counts for each match type", () => {
    render(<ResumenConciliacion resumen={resumen} />);
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("Exactos")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Parciales")).toBeInTheDocument();
    expect(screen.getByText("4")).toBeInTheDocument();
    expect(screen.getByText("Sin CFDI")).toBeInTheDocument();
    expect(screen.getByText("1")).toBeInTheDocument();
    expect(screen.getByText("Sin movimiento")).toBeInTheDocument();
  });

  it("renders the reconciliation percentage and total movements", () => {
    render(<ResumenConciliacion resumen={resumen} />);
    expect(screen.getByText("75%")).toBeInTheDocument();
    expect(screen.getByText("Conciliado (20 movimientos)")).toBeInTheDocument();
  });
});
