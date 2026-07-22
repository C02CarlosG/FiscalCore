import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { RiesgosTable } from "./RiesgosTable";
import type { RiesgoAbierto } from "@/types/api";

const riesgo: RiesgoAbierto = {
  id: "r1",
  codigo: "R001",
  nombre: "Brecha de ingresos",
  severidad: "alto",
  monto_afectado: 12345.67,
  descripcion: "Depósitos bancarios sin CFDI",
  cfdi_id: null,
  movimiento_id: "m1",
  estado: "abierto",
  periodo: "2026-07",
  created_at: "2026-07-01T00:00:00Z",
};

describe("RiesgosTable", () => {
  it("shows an empty state message when there are no risks", () => {
    render(<RiesgosTable riesgos={[]} />);
    expect(
      screen.getByText("No hay riesgos abiertos en este periodo."),
    ).toBeInTheDocument();
  });

  it("renders a row per risk", () => {
    render(<RiesgosTable riesgos={[riesgo]} />);
    expect(screen.getByText("Brecha de ingresos")).toBeInTheDocument();
    expect(screen.getByText("Depósitos bancarios sin CFDI")).toBeInTheDocument();
  });
});
