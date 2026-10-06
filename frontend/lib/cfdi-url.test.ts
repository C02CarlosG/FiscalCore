import { describe, expect, it } from "vitest";
import { consultaApi, escribirEstado, leerEstado } from "./cfdi-url";

const params = (texto = "") => new URLSearchParams(texto);

describe("leerEstado", () => {
  it("con la URL vacía devuelve los valores por defecto", () => {
    expect(leerEstado(params(), "2026-09")).toEqual({
      periodo: "2026-09",
      tipo: "I",
      estado: "vigente",
      metodo: "todos",
      pago: "todos",
      q: "",
      etiqueta: "",
      filtros: "",
      orden: "fecha_emision",
      dir: "asc",
      pagina: 1,
      porPagina: 30,
    });
  });

  it("lee los valores válidos de la URL", () => {
    const estado = leerEstado(
      params("tipo=E&estado=cancelado&metodo=PPD&pago=pendientes&q=abc&orden=total&dir=desc&pagina=3&por_pagina=100"),
      "2026-09",
    );

    expect(estado).toMatchObject({
      tipo: "E", estado: "cancelado", metodo: "PPD", pago: "pendientes",
      q: "abc", orden: "total", dir: "desc", pagina: 3, porPagina: 100,
    });
  });

  it("ignora los valores inválidos y usa el por defecto", () => {
    const estado = leerEstado(
      params("tipo=X&estado=roto&metodo=ppd&pago=nada&dir=lado&pagina=-3&por_pagina=999"),
      "2026-09",
    );

    expect(estado).toMatchObject({
      tipo: "I", estado: "vigente", metodo: "todos", pago: "todos",
      dir: "asc", pagina: 1, porPagina: 30,
    });
  });

  it("una página que no es número entero vuelve a 1", () => {
    expect(leerEstado(params("pagina=abc"), "2026-09").pagina).toBe(1);
    expect(leerEstado(params("pagina=2.5"), "2026-09").pagina).toBe(1);
    expect(leerEstado(params("pagina=0"), "2026-09").pagina).toBe(1);
  });

  it("conserva el filtro avanzado tal cual, para F3.4", () => {
    const filtros = '[{"campo":"total","op":"mayor","valor":100}]';

    expect(leerEstado(params(`filtros=${encodeURIComponent(filtros)}`), "2026-09").filtros).toBe(filtros);
  });
});

describe("escribirEstado", () => {
  it("no escribe los valores por defecto", () => {
    const resultado = escribirEstado(params("tipo=E&periodo=2026-09"), { tipo: "I" });

    expect(resultado.toString()).toBe("periodo=2026-09");
  });

  it("escribe los valores que cambian con los nombres de la URL", () => {
    const resultado = escribirEstado(params(), { porPagina: 50, orden: "total", dir: "desc" });

    expect(resultado.get("por_pagina")).toBe("50");
    expect(resultado.get("orden")).toBe("total");
    expect(resultado.get("dir")).toBe("desc");
  });

  it("al cambiar un filtro regresa a la página 1", () => {
    const resultado = escribirEstado(params("pagina=4&tipo=E"), { metodo: "PUE" });

    expect(resultado.has("pagina")).toBe(false);
    expect(resultado.get("tipo")).toBe("E");
    expect(resultado.get("metodo")).toBe("PUE");
  });

  it("cambiar solo la página no toca los filtros", () => {
    const resultado = escribirEstado(params("tipo=E&metodo=PPD&q=abc"), { pagina: 3 });

    expect(resultado.get("pagina")).toBe("3");
    expect(resultado.get("tipo")).toBe("E");
    expect(resultado.get("metodo")).toBe("PPD");
    expect(resultado.get("q")).toBe("abc");
  });

  it("quita el sub-filtro de pago cuando el método deja de ser PPD", () => {
    const resultado = escribirEstado(params("metodo=PPD&pago=pendientes"), { metodo: "PUE" });

    expect(resultado.has("pago")).toBe(false);
  });

  it("conserva los parámetros que no son del listado", () => {
    const resultado = escribirEstado(params("otro=1"), { tipo: "E" });

    expect(resultado.get("otro")).toBe("1");
  });

  it("una búsqueda vacía quita el parámetro", () => {
    const resultado = escribirEstado(params("q=abc"), { q: "" });

    expect(resultado.has("q")).toBe(false);
  });
});

describe("consultaApi", () => {
  it("usa los nombres de parámetros de la API", () => {
    const estado = leerEstado(params("tipo=E&metodo=PPD&pago=pendientes&q=abc&orden=total&dir=desc&pagina=2&por_pagina=50"), "2026-09");

    const consulta = consultaApi(estado, "recibidos");

    expect(Object.fromEntries(consulta)).toEqual({
      direccion: "recibidos",
      periodo: "2026-09",
      tipo: "E",
      estado: "vigente",
      metodo: "PPD",
      pago: "pendientes",
      q: "abc",
      orden: "total",
      dir: "desc",
      pagina: "2",
      por_pagina: "50",
    });
  });

  it("no manda q ni filtros cuando están vacíos", () => {
    const consulta = consultaApi(leerEstado(params(), "2026-09"), "emitidos");

    expect(consulta.has("q")).toBe(false);
    expect(consulta.has("filtros")).toBe(false);
  });
});

describe("etiqueta", () => {
  const id = "11111111-1111-4111-8111-111111111111";

  it("se lee solo si tiene forma de UUID y viaja a la API", () => {
    expect(leerEstado(params(`etiqueta=${id}`), "2026-09").etiqueta).toBe(id);
    expect(leerEstado(params("etiqueta=x"), "2026-09").etiqueta).toBe("");
    expect(consultaApi(leerEstado(params(`etiqueta=${id}`), "2026-09"), "emitidos").get("etiqueta")).toBe(id);
    expect(consultaApi(leerEstado(params(), "2026-09"), "emitidos").has("etiqueta")).toBe(false);
  });

  it("un cambio de etiqueta regresa a la página 1 y su valor por defecto se quita de la URL", () => {
    const con = escribirEstado(params("pagina=3"), { etiqueta: id });
    expect(con.get("etiqueta")).toBe(id);
    expect(con.has("pagina")).toBe(false);
    expect(escribirEstado(con, { etiqueta: "" }).has("etiqueta")).toBe(false);
  });
});
