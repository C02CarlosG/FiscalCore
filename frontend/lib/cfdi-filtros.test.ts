import { describe, expect, it } from "vitest";
import {
  contarActivos, leerFiltros, operadoresDe, renglonCompleto, renglonConOperador, renglonNuevo, serializarFiltros,
} from "./cfdi-filtros";
import type { CfdiColumna } from "@/types/api";

const col = (clave: string, tipo_dato: CfdiColumna["tipo_dato"], extra: Partial<CfdiColumna> = {}): CfdiColumna => ({
  clave, etiqueta: clave, tipo_dato, grupo: "encabezado", visible_por_defecto: true, ordenable: true, filtrable: true,
  opciones: [], ...extra,
});
const catalogo = [
  col("serie", "texto"), col("total", "moneda"), col("fecha_emision", "fecha"), col("cancelado", "booleano"),
  col("metodo_pago", "catalogo", { opciones: ["PUE", "PPD"] }), col("pagos_relacionados", "lista", { filtrable: false }),
];
const de = (clave: string) => catalogo.find((c) => c.clave === clave)!;

describe("operadores", () => {
  it("coinciden con los que acepta el servidor para cada tipo", () => {
    expect(operadoresDe(de("serie"))).toEqual(["contiene", "igual", "empieza"]);
    expect(operadoresDe(de("total"))).toEqual(["igual", "mayor", "menor", "entre"]);
    expect(operadoresDe(de("cancelado"))).toEqual(["igual"]);
    expect(operadoresDe(de("metodo_pago"))).toEqual(["igual", "en"]);
  });

  it("un renglón nuevo empieza con el primer operador y cambiarlo limpia el valor", () => {
    expect(renglonNuevo(de("total"))).toEqual({ campo: "total", op: "igual", valor: "" });
    expect(renglonNuevo(de("cancelado")).valor).toBe("true");
    expect(renglonConOperador({ campo: "total", op: "igual", valor: "5" }, "entre").valor).toBe("");
  });
});

describe("serializarFiltros", () => {
  it("convierte cada valor al tipo de su columna", () => {
    const json = serializarFiltros([
      { campo: "total", op: "mayor", valor: "1000.5" },
      { campo: "serie", op: "contiene", valor: " A " },
      { campo: "total", op: "entre", valor: "10|20" },
      { campo: "fecha_emision", op: "entre", valor: "2026-09-01|2026-09-15" },
      { campo: "cancelado", op: "igual", valor: "false" },
      { campo: "metodo_pago", op: "en", valor: "PUE|PPD" },
    ], catalogo);
    expect(JSON.parse(json)).toEqual([
      { campo: "total", op: "mayor", valor: 1000.5 },
      { campo: "serie", op: "contiene", valor: "A" },
      { campo: "total", op: "entre", valor: [10, 20] },
      { campo: "fecha_emision", op: "entre", valor: ["2026-09-01", "2026-09-15"] },
      { campo: "cancelado", op: "igual", valor: false },
      { campo: "metodo_pago", op: "en", valor: ["PUE", "PPD"] },
    ]);
  });

  it("sin renglones es vacío, para no escribir nada en la URL", () => {
    expect(serializarFiltros([], catalogo)).toBe("");
  });

  it("ida y vuelta: lo que se aplica se vuelve a leer igual", () => {
    const renglones = [{ campo: "total", op: "entre" as const, valor: "10|20" }];
    expect(leerFiltros(serializarFiltros(renglones, catalogo))).toEqual(renglones);
  });
});

describe("renglonCompleto", () => {
  it("rechaza valores vacíos o que no son del tipo", () => {
    expect(renglonCompleto({ campo: "total", op: "mayor", valor: "" }, de("total"))).toBe(false);
    expect(renglonCompleto({ campo: "total", op: "mayor", valor: "abc" }, de("total"))).toBe(false);
    expect(renglonCompleto({ campo: "total", op: "mayor", valor: "10" }, de("total"))).toBe(true);
    expect(renglonCompleto({ campo: "total", op: "entre", valor: "10|" }, de("total"))).toBe(false);
    expect(renglonCompleto({ campo: "total", op: "entre", valor: "10|20" }, de("total"))).toBe(true);
    expect(renglonCompleto({ campo: "metodo_pago", op: "en", valor: "" }, de("metodo_pago"))).toBe(false);
    expect(renglonCompleto({ campo: "serie", op: "contiene", valor: "  " }, de("serie"))).toBe(false);
  });

  it("rechaza un operador que no aplica al tipo o un campo desconocido", () => {
    expect(renglonCompleto({ campo: "serie", op: "mayor", valor: "1" }, de("serie"))).toBe(false);
    expect(renglonCompleto({ campo: "x", op: "igual", valor: "1" }, undefined)).toBe(false);
  });
});

describe("leerFiltros y contarActivos", () => {
  it("un JSON ilegible o ajeno no rompe la pantalla", () => {
    expect(leerFiltros("no es json")).toEqual([]);
    expect(leerFiltros('{"a":1}')).toEqual([]);
    expect(leerFiltros('[1, null, {"campo": 3}]')).toEqual([]);
  });

  it("cuenta solo los filtros cuyo campo sigue siendo filtrable en el catálogo", () => {
    const json = JSON.stringify([
      { campo: "total", op: "mayor", valor: 1 },
      { campo: "columna_vieja", op: "igual", valor: 1 },
      { campo: "pagos_relacionados", op: "igual", valor: 1 },
    ]);
    expect(contarActivos(json, catalogo)).toBe(1);
    expect(contarActivos("", catalogo)).toBe(0);
    expect(contarActivos(json, undefined)).toBe(0);
  });
});
