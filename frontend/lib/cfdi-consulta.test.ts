import { describe, expect, it } from "vitest";
import { actualizarParams, leerConsulta, queryDeApi, CONSULTA_INICIAL } from "./cfdi-consulta";

describe("leerConsulta", () => {
  it("usa los valores por defecto con una URL vacía", () => {
    expect(leerConsulta(new URLSearchParams())).toEqual(CONSULTA_INICIAL);
  });

  it("ignora valores fuera de lo permitido", () => {
    const c = leerConsulta(new URLSearchParams("tipo=X&estado=hola&pagina=-3&por_pagina=77&dir=sideways"));
    expect(c).toMatchObject({ tipo: "I", estado: "vigente", pagina: 1, por_pagina: 30, dir: "asc" });
  });

  it("solo conserva el sub-filtro de pago con PPD", () => {
    expect(leerConsulta(new URLSearchParams("metodo=PUE&pago=pendientes")).pago).toBe("todos");
    expect(leerConsulta(new URLSearchParams("metodo=PPD&pago=pendientes")).pago).toBe("pendientes");
  });
});

describe("actualizarParams", () => {
  it("conserva el periodo, quita lo que vuelve al valor por defecto y reinicia la página", () => {
    const params = actualizarParams(new URLSearchParams("periodo=2026-09&tipo=E&pagina=4"), { estado: "cancelado" });
    expect(params.get("periodo")).toBe("2026-09");
    expect(params.get("tipo")).toBe("E");
    expect(params.get("estado")).toBe("cancelado");
    expect(params.has("pagina")).toBe(false);
    expect(actualizarParams(params, { estado: "vigente" }).has("estado")).toBe(false);
  });

  it("respeta un cambio explícito de página", () => {
    expect(actualizarParams(new URLSearchParams(), { pagina: 3 }).get("pagina")).toBe("3");
  });

  it("limpia el pago al salir de PPD", () => {
    const ppd = actualizarParams(new URLSearchParams(), { metodo: "PPD", pago: "pendientes" });
    expect(ppd.get("pago")).toBe("pendientes");
    expect(actualizarParams(ppd, { metodo: "PUE" }).has("pago")).toBe(false);
  });
});

describe("queryDeApi", () => {
  it("arma el querystring del listado y del resumen", () => {
    const c = { ...CONSULTA_INICIAL, q: " ABC ", orden: "total", dir: "desc" as const, pagina: 2 };
    const listado = new URLSearchParams(queryDeApi("emitidos", "2026-09", c, true));
    expect(Object.fromEntries(listado)).toMatchObject({
      direccion: "emitidos", periodo: "2026-09", tipo: "I", q: "ABC", orden: "total", dir: "desc", pagina: "2", por_pagina: "30",
    });
    const resumen = new URLSearchParams(queryDeApi("emitidos", "2026-09", c, false));
    expect(resumen.has("pagina")).toBe(false);
    expect(resumen.has("orden")).toBe(false);
  });
});
