import { describe, expect, it } from "vitest";
import { formatearFecha, formatearFechaHora, formatearMoneda } from "./formato";

describe("formatearFecha", () => {
  it("escribe dd/mm/aaaa", () => {
    expect(formatearFecha("2026-09-05")).toBe("05/09/2026");
  });

  it("toma solo la fecha de un ISO con hora", () => {
    expect(formatearFecha("2026-09-05T13:07:09")).toBe("05/09/2026");
  });

  it("no desplaza el día por la zona horaria del navegador", () => {
    // 23:30 del 31 de diciembre es hora local del emisor: sigue siendo 31, no 1 de enero.
    expect(formatearFecha("2026-12-31T23:30:00")).toBe("31/12/2026");
  });

  it.each([null, undefined, "", "hola", "2026-9-5", "05/09/2026"])("devuelve guion ante %j", (valor) => {
    expect(formatearFecha(valor)).toBe("—");
  });
});

describe("formatearFechaHora", () => {
  it("escribe dd/mm/aaaa hh:mm", () => {
    expect(formatearFechaHora("2026-09-05T13:07:09")).toBe("05/09/2026 13:07");
  });

  it("si no trae hora, muestra solo la fecha", () => {
    expect(formatearFechaHora("2026-09-05")).toBe("05/09/2026");
  });

  it("conserva la hora del comprobante sin convertirla", () => {
    expect(formatearFechaHora("2026-12-31T23:59:59")).toBe("31/12/2026 23:59");
  });

  it.each([null, undefined, "", "hola"])("devuelve guion ante %j", (valor) => {
    expect(formatearFechaHora(valor)).toBe("—");
  });
});

describe("formatearMoneda", () => {
  it("usa formato de pesos mexicanos", () => {
    expect(formatearMoneda(1234.5)).toBe("$1,234.50");
  });

  it("respeta el cero y los negativos", () => {
    expect(formatearMoneda(0)).toBe("$0.00");
    expect(formatearMoneda(-50)).toBe("-$50.00");
  });

  it.each([null, undefined])("devuelve guion ante %j, nunca cero", (valor) => {
    expect(formatearMoneda(valor)).toBe("—");
  });
});
