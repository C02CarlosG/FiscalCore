import { describe, expect, it } from "vitest";
import { consultaExportacion } from "./useExportarCfdi";
import { POR_DEFECTO, type CfdiEstadoUrl } from "@/lib/cfdi-url";

const estado: CfdiEstadoUrl = { ...POR_DEFECTO, periodo: "2026-09", q: "acme", orden: "total", dir: "desc", pagina: 3, porPagina: 50 };

describe("consultaExportacion", () => {
  it("lleva los filtros de la pantalla, sin paginar, y las columnas en orden", () => {
    const c = consultaExportacion(estado, "recibidos", ["total", "serie", "estado"]);
    expect(Object.fromEntries(c)).toMatchObject({
      direccion: "recibidos", periodo: "2026-09", tipo: "I", q: "acme", orden: "total", dir: "desc",
      columnas: "total,serie,estado",
    });
    expect(c.has("pagina")).toBe(false);
    expect(c.has("por_pagina")).toBe(false);
  });

  it("incluye el filtro avanzado y el sub-filtro de pago de PPD", () => {
    const filtros = JSON.stringify([{ campo: "total", op: "mayor", valor: 10 }]);
    const c = consultaExportacion({ ...estado, filtros, metodo: "PPD", pago: "pendientes" }, "emitidos", ["total"]);
    expect(c.get("filtros")).toBe(filtros);
    expect(c.get("metodo")).toBe("PPD");
    expect(c.get("pago")).toBe("pendientes");
  });
});
