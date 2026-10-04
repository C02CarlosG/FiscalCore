import { describe, expect, it } from "vitest";
import {
  ETIQUETA_MARCA,
  ETIQUETA_MOTIVO,
  etiquetaOrigen,
  leerEstadoIva,
  escribirEstadoIva,
  siguientePeriodo,
} from "./iva-flujo";

describe("leerEstadoIva", () => {
  it("sin parámetros usa los valores por defecto", () => {
    expect(leerEstadoIva(new URLSearchParams(""))).toEqual({ vista: "trasladado", origen: "contado", pagina: 1 });
  });

  it("lee vista, origen y página de la URL", () => {
    expect(leerEstadoIva(new URLSearchParams("vista=acreditable&origen=no_considerados&pagina=3"))).toEqual({
      vista: "acreditable", origen: "no_considerados", pagina: 3,
    });
  });

  it("ignora valores inválidos", () => {
    expect(leerEstadoIva(new URLSearchParams("vista=x&origen=y&pagina=-2"))).toEqual({ vista: "trasladado", origen: "contado", pagina: 1 });
    expect(leerEstadoIva(new URLSearchParams("pagina=abc")).pagina).toBe(1);
  });
});

describe("escribirEstadoIva", () => {
  it("omite los valores por defecto y conserva los demás parámetros (el periodo)", () => {
    const params = escribirEstadoIva(new URLSearchParams("periodo=2026-09&vista=acreditable"), { vista: "trasladado" });

    expect(params.toString()).toBe("periodo=2026-09");
  });

  it("cambiar de vista o de origen regresa a la página 1", () => {
    const base = new URLSearchParams("periodo=2026-09&origen=credito&pagina=4");

    expect(escribirEstadoIva(base, { vista: "acreditable" }).toString()).toBe("periodo=2026-09&vista=acreditable&origen=credito");
    expect(escribirEstadoIva(base, { origen: "notas_credito" }).toString()).toBe("periodo=2026-09&origen=notas_credito");
  });

  it("cambiar solo la página conserva lo demás", () => {
    const base = new URLSearchParams("periodo=2026-09&origen=credito");

    expect(escribirEstadoIva(base, { pagina: 2 }).toString()).toBe("periodo=2026-09&origen=credito&pagina=2");
  });
});

describe("etiquetas", () => {
  it("el origen de crédito se llama cobro en trasladado y pago en acreditable", () => {
    expect(etiquetaOrigen("credito", "trasladado")).toBe("Cobro de facturas de crédito");
    expect(etiquetaOrigen("credito", "acreditable")).toBe("Pago de facturas de crédito");
    expect(etiquetaOrigen("no_considerados", "acreditable")).toBe("No considerados");
    expect(etiquetaOrigen("reasignados", "trasladado")).toBe("Periodo reasignado");
  });

  it("cada marca y motivo conocido tiene texto en español", () => {
    for (const marca of ["aproximado", "pago_v1", "descuadre", "sin_desglose", "sin_equivalencia", "sin_tipo_cambio",
      "sin_proporcion", "anticipo", "aplicacion_anticipo", "aplicado_en_rep", "original_no_acreditable", "descuadre_retencion",
      "retencion_sin_desglose", "descuadre_rep", "equivalencia_sospechosa", "forma_pago_rep", "tc_distante",
      "objeto_imp_inconsistente", "objeto_sin_desglose"]) {
      expect(ETIQUETA_MARCA[marca]).toBeTruthy();
    }
    for (const motivo of ["efectivo", "uso_no_deducible", "manual", "reasignado", "aplicado_en_rep", "original_no_acreditable",
      "sin_equivalencia", "sin_tipo_cambio", "sin_proporcion", "pago_v1", "equivalencia_sospechosa"]) {
      expect(ETIQUETA_MOTIVO[motivo]).toBeTruthy();
    }
  });
});

describe("siguientePeriodo", () => {
  it("avanza un mes y cruza de año", () => {
    expect(siguientePeriodo("2026-09")).toBe("2026-10");
    expect(siguientePeriodo("2026-12")).toBe("2027-01");
  });
});
