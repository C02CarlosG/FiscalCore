import { describe, expect, it } from "vitest";
import { scoreDelPeriodo } from "./score";

const tendencia = [
  { periodo: "2026-06", score: 70 },
  { periodo: "2026-07", score: 74 },
  { periodo: "2026-08", score: 71 },
  { periodo: "2026-09", score: 80 },
];

describe("scoreDelPeriodo", () => {
  it("devuelve el score del periodo elegido, no el último de la tendencia", () => {
    expect(scoreDelPeriodo(tendencia, "2026-07").score).toBe(74);
  });

  it("calcula el cambio contra el periodo anterior de la tendencia", () => {
    expect(scoreDelPeriodo(tendencia, "2026-08").delta).toEqual({ puntos: -3, contra: "2026-07" });
    expect(scoreDelPeriodo(tendencia, "2026-09").delta).toEqual({ puntos: 9, contra: "2026-08" });
  });

  it("el primer periodo no tiene cambio", () => {
    expect(scoreDelPeriodo(tendencia, "2026-06")).toEqual({ score: 70, delta: null });
  });

  it("un periodo sin score devuelve null, no el último", () => {
    expect(scoreDelPeriodo(tendencia, "2026-10")).toEqual({ score: null, delta: null });
  });

  it("sin tendencia devuelve null", () => {
    expect(scoreDelPeriodo([], "2026-09")).toEqual({ score: null, delta: null });
  });

  it("no depende del orden en que llegue la tendencia", () => {
    const desordenada = [tendencia[2], tendencia[0], tendencia[3], tendencia[1]];

    expect(scoreDelPeriodo(desordenada, "2026-08").delta).toEqual({ puntos: -3, contra: "2026-07" });
  });
});
