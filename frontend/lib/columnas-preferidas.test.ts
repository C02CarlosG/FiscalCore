import { describe, expect, it } from "vitest";
import { columnasVisibles, resolverColumnas } from "./columnas-preferidas";

const catalogo = [
  { clave: "fecha", visible_por_defecto: true },
  { clave: "total", visible_por_defecto: true },
  { clave: "uuid", visible_por_defecto: false },
];

describe("resolverColumnas", () => {
  it("sin preferencia usa el orden y la visibilidad del catálogo", () => {
    expect(resolverColumnas(catalogo, null).map((c) => [c.clave, c.visible])).toEqual([
      ["fecha", true], ["total", true], ["uuid", false],
    ]);
    expect(resolverColumnas(catalogo, undefined)).toHaveLength(3);
  });

  it("respeta el orden y la visibilidad guardados", () => {
    const r = resolverColumnas(catalogo, [
      { clave: "uuid", visible: true }, { clave: "total", visible: false }, { clave: "fecha", visible: true },
    ]);
    expect(r.map((c) => [c.clave, c.visible])).toEqual([["uuid", true], ["total", false], ["fecha", true]]);
  });

  it("ignora claves que ya no existen y repetidas", () => {
    const r = resolverColumnas(catalogo, [
      { clave: "vieja", visible: true }, { clave: "total", visible: true }, { clave: "total", visible: false },
    ]);
    expect(r.map((c) => c.clave)).toEqual(["total", "fecha", "uuid"]);
    expect(r[0].visible).toBe(true);
  });

  it("las columnas nuevas del catálogo aparecen al final con su visibilidad por defecto", () => {
    const r = resolverColumnas(catalogo, [{ clave: "total", visible: true }]);
    expect(r.map((c) => [c.clave, c.visible])).toEqual([["total", true], ["fecha", true], ["uuid", false]]);
  });
});

describe("columnasVisibles", () => {
  it("devuelve solo las visibles, en orden y sin la marca interna", () => {
    const r = columnasVisibles(catalogo, [{ clave: "total", visible: true }, { clave: "fecha", visible: false }]);
    expect(r).toEqual([{ clave: "total", visible_por_defecto: true }]);
  });
});
