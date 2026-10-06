import { describe, expect, it } from "vitest";
import { CAMPOS_POR_IMPUESTO, importeValido, valoresIniciales } from "./declaraciones";

describe("importeValido", () => {
  it("acepta vacío y hasta dos decimales", () => {
    expect(importeValido("", false)).toBe(true);
    expect(importeValido("  ", false)).toBe(true);
    expect(importeValido("1100", false)).toBe(true);
    expect(importeValido("1100.5", false)).toBe(true);
    expect(importeValido("1100.50", false)).toBe(true);
  });

  it("rechaza tres decimales, texto y negativos salvo en el que admite signo", () => {
    expect(importeValido("1.234", false)).toBe(false);
    expect(importeValido("abc", false)).toBe(false);
    expect(importeValido("-5", false)).toBe(false);
    expect(importeValido("-5", true)).toBe(true);
    expect(importeValido("1,000", true)).toBe(false);
  });
});

describe("campos por impuesto", () => {
  it("solo el a cargo admite signo", () => {
    for (const impuesto of ["iva", "isr"] as const) {
      expect(CAMPOS_POR_IMPUESTO[impuesto].filter((c) => c.signo).map((c) => c.campo)).toEqual(["impuesto_a_cargo"]);
    }
  });

  it("el saldo a favor aplicado es solo de IVA y ingresos/deducciones solo de ISR", () => {
    const claves = (i: "iva" | "isr") => CAMPOS_POR_IMPUESTO[i].map((c) => c.campo);
    expect(claves("iva")).toContain("saldo_a_favor_aplicado");
    expect(claves("isr")).not.toContain("saldo_a_favor_aplicado");
    expect(claves("isr")).toEqual(expect.arrayContaining(["ingresos", "deducciones"]));
  });

  it("valoresIniciales parte de la vigente o de vacío", () => {
    expect(valoresIniciales("iva", null).impuesto_trasladado).toBe("");
    const v = valoresIniciales("iva", {
      periodo: "2026-09", impuesto: "iva", secuencia: 1, tipo: "normal", fecha_presentacion: "2026-10-17", numero_operacion: "N1",
      ingresos: null, deducciones: null, impuesto_trasladado: 160, impuesto_acreditable: null, retenciones: null,
      retenciones_a_terceros: null, saldo_a_favor_aplicado: null, impuesto_a_cargo: -50.5, monto_pagado: null, notas: "x", updated_at: "",
    });
    expect(v).toMatchObject({ impuesto_trasladado: "160", impuesto_a_cargo: "-50.5", fecha_presentacion: "2026-10-17", numero_operacion: "N1", notas: "x" });
  });
});
