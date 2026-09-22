import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ParesTable } from "./ParesTable";
import type { ParConciliacion } from "@/types/api";

const par: ParConciliacion = {
  id: "c1",
  tipo_match: "sin_cfdi",
  monto_movimiento: 5000,
  monto_cfdi: null,
  diferencia: null,
  porcentaje_match: null,
  periodo: "2026-07",
  movimiento_id: "m1",
  mov_fecha: "2026-07-10",
  concepto: "Depósito SPEI",
  mov_monto: 5000,
  mov_tipo: "ingreso",
  rfc_detectado: null,
};

describe("ParesTable", () => {
  it("shows an empty state message when there are no pairs", () => {
    render(<ParesTable pares={[]} />);
    expect(
      screen.getByText(
        "No hay movimientos pendientes de conciliar en este periodo.",
      ),
    ).toBeInTheDocument();
  });

  it("renders a row per pair", () => {
    render(<ParesTable pares={[par]} />);
    expect(screen.getByText("Sin CFDI")).toBeInTheDocument();
    expect(screen.getByText("Depósito SPEI")).toBeInTheDocument();
  });
});
