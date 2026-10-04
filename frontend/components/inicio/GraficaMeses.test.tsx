import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { GraficaMeses, etiquetaMesCorta } from "./GraficaMeses";
import { meses } from "./fixtures";

describe("etiquetaMesCorta", () => {
  it("abrevia el mes en español y agrega el año en enero y en el primer mes", () => {
    expect(etiquetaMesCorta("2026-03", false)).toBe("mar");
    expect(etiquetaMesCorta("2026-01", false)).toBe("ene 26");
    expect(etiquetaMesCorta("2025-10", true)).toBe("oct 25");
  });
});

describe("GraficaMeses", () => {
  it("dibuja una barra de ingresos y una de gastos por cada uno de los 12 meses", () => {
    const { container } = render(<GraficaMeses meses={meses()} periodo="2026-09" />);

    expect(container.querySelectorAll('rect[data-serie="ingresos"]')).toHaveLength(12);
    expect(container.querySelectorAll('rect[data-serie="gastos"]')).toHaveLength(12);
  });

  it("la altura es proporcional al mayor valor de la serie", () => {
    const { container } = render(<GraficaMeses meses={meses()} periodo="2026-09" />);
    const barras = Array.from(container.querySelectorAll('rect[data-serie="ingresos"]'));
    const alto = (n: number) => Number(barras[n].getAttribute("height"));

    expect(alto(11)).toBeGreaterThan(alto(5));                    // diciembre de la serie > marzo
    expect(alto(11) / alto(5)).toBeCloseTo(12 / 6, 1);            // 12000 vs 6000
  });

  it("resalta el mes elegido", () => {
    const { container } = render(<GraficaMeses meses={meses()} periodo="2026-09" />);

    const actuales = container.querySelectorAll('[data-actual="true"]');
    expect(actuales.length).toBeGreaterThan(0);
    actuales.forEach((el) => expect(el.getAttribute("data-mes")).toBe("2026-09"));
  });

  it("se describe para lector de pantalla y trae leyenda", () => {
    render(<GraficaMeses meses={meses()} periodo="2026-09" />);

    expect(screen.getByRole("img", { name: /Ingresos y gastos netos de los últimos 12 meses/ })).toBeInTheDocument();
    expect(screen.getByText("Ingresos")).toBeInTheDocument();
    expect(screen.getByText("Gastos")).toBeInTheDocument();
  });

  it("sin movimiento en la serie avisa y no dibuja barras con altura", () => {
    const vacios = meses().map((m) => ({ ...m, ingresos: { ...m.ingresos, neto: 0 }, gastos: { neto: 0 } }));
    const { container } = render(<GraficaMeses meses={vacios} periodo="2026-09" />);

    expect(screen.getByText("Sin movimientos en los últimos 12 meses")).toBeInTheDocument();
    container.querySelectorAll("rect[data-serie]").forEach((r) => expect(Number(r.getAttribute("height"))).toBe(0));
  });

  it("un mes con nota de crédito mayor que el facturado (neto negativo) no rompe la gráfica", () => {
    const m = meses();
    m[3] = { ...m[3], ingresos: { ...m[3].ingresos, neto: -500 } };

    const { container } = render(<GraficaMeses meses={m} periodo="2026-09" />);

    const barra = container.querySelectorAll('rect[data-serie="ingresos"]')[3];
    expect(Number(barra.getAttribute("height"))).toBe(0);
  });
});
