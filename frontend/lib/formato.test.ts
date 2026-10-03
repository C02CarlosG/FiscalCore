import { describe, expect, it } from "vitest";
import { formatFecha, formatFechaHora, textoCelda } from "./formato";
import { esPeriodoValido, etiquetaPeriodo, opcionesPeriodo } from "./periodo";

describe("fechas", () => {
  it("formatea dd/mm/aaaa sin mover de día por la zona horaria", () => {
    expect(formatFecha("2026-09-01")).toBe("01/09/2026");
    expect(formatFecha("2026-09-30T23:59:00")).toBe("30/09/2026");
    expect(formatFechaHora("2026-09-03T10:15:00")).toBe("03/09/2026 10:15");
    expect(formatFecha(null)).toBe("—");
  });
});

describe("textoCelda", () => {
  it("formatea según el tipo de dato", () => {
    expect(textoCelda({ tipo_dato: "moneda" }, 1234.5)).toContain("1,234.50");
    expect(textoCelda({ tipo_dato: "fecha" }, "2026-09-03")).toBe("03/09/2026");
    expect(textoCelda({ tipo_dato: "lista" }, ["A", "B"])).toBe("A, B");
    expect(textoCelda({ tipo_dato: "lista" }, [])).toBe("—");
    expect(textoCelda({ tipo_dato: "texto" }, null)).toBe("—");
  });
});

describe("periodo", () => {
  it("valida y etiqueta", () => {
    expect(esPeriodoValido("2026-09")).toBe(true);
    expect(esPeriodoValido("2026-13")).toBe(false);
    expect(etiquetaPeriodo("2026-09")).toBe("2026 - Septiembre");
  });

  it("ofrece los periodos con datos, el seleccionado y el mes actual, de nuevo a antiguo", () => {
    const opciones = opcionesPeriodo(["2026-07", "2026-08"], "2025-01");
    expect(opciones).toContain("2025-01");
    expect(opciones).toEqual([...opciones].sort().reverse());
    expect(new Set(opciones).size).toBe(opciones.length);
  });
});
