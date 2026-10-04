import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CedulaIvaTable } from "./CedulaIvaTable";
import type { CedulaIva } from "@/types/api";

const cedula: CedulaIva = {
  empresa_id: "e1",
  periodo: "2026-07",
  trasladado: {
    pue: { base: 1000, iva: 160 },
    ppd: { cobrado: 0, iva: 0 },
    notas_credito: { base: 0, iva: 0 },
    total: 160,
    no_considerados: { cfdi: 0, iva: 0 },
    reasignados: { cfdi: 0, iva: 0 },
  },
  acreditable: {
    pue: { base: 500, iva: 80 },
    ppd: { pagado: 0, iva: 0 },
    notas_credito: { base: 0, iva: 0 },
    excluido_efectivo: { iva: 0 },
    no_considerados: { cfdi: 0, iva: 0 },
    reasignados: { cfdi: 0, iva: 0 },
    bruto: 80,
    factor_prorrateo: 1,
    ajustado: 80,
  },
  iva_retenido: 0,
  retenciones_a_enterar: 0,
  advertencias: [],
  resultado: {
    iva_por_pagar: 80,
    saldo_a_cargo: 80,
    saldo_a_favor: 0,
  },
  comparativo_sat: {
    diot_iva_pagado: 80,
    diferencia: 0,
  },
};

describe("CedulaIvaTable", () => {
  it("renders the key IVA amounts", () => {
    render(<CedulaIvaTable cedula={cedula} />);
    expect(screen.getByText("IVA trasladado (total)")).toBeInTheDocument();
    expect(screen.getByText("IVA por pagar")).toBeInTheDocument();
    expect(screen.getAllByText(/\$80\.00/).length).toBeGreaterThan(0);
    expect(screen.getByText("Retenciones por enterar")).toBeInTheDocument();
    expect(screen.queryByRole("list", { name: "Advertencias de la cédula" })).not.toBeInTheDocument();
  });

  it("explica lo que no se acredita y muestra las advertencias", () => {
    render(
      <CedulaIvaTable
        cedula={{
          ...cedula,
          acreditable: { ...cedula.acreditable, no_considerados: { cfdi: 2, iva: 320 } },
          advertencias: [{ codigo: "sin_desglose", mensaje: "Hay CFDI sin desglose por tasa guardado.", cfdi: 3 }],
        }}
      />,
    );
    expect(screen.getByText(/2 CFDI recibidos no se acreditan/)).toBeInTheDocument();
    expect(screen.getByText(/Hay CFDI sin desglose por tasa guardado/)).toBeInTheDocument();
    expect(screen.getByText("(3 CFDI)")).toBeInTheDocument();
  });
});
