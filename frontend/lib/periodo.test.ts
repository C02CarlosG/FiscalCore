import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  esPeriodoValido,
  etiquetaPeriodo,
  periodoActual,
  periodoRecordado,
  recordarPeriodo,
  resolverPeriodo,
} from "./periodo";

const HOY = new Date(2026, 9, 3); // 3 de octubre de 2026 (hora local)

describe("esPeriodoValido", () => {
  it.each(["2026-09", "2000-01", "2099-12"])("acepta %s", (p) => {
    expect(esPeriodoValido(p)).toBe(true);
  });

  it.each(["2026-13", "2026-00", "26-09", "2026-9", "1999-12", "2100-01", "", "2026-09-01", "abcd-ef"])(
    "rechaza %j",
    (p) => {
      expect(esPeriodoValido(p)).toBe(false);
    },
  );
});

describe("periodoActual", () => {
  it("usa el mes de la hora local", () => {
    expect(periodoActual(HOY)).toBe("2026-10");
  });

  it("rellena el mes con cero", () => {
    expect(periodoActual(new Date(2027, 0, 31))).toBe("2027-01");
  });
});

describe("etiquetaPeriodo", () => {
  it("escribe año y mes en español", () => {
    expect(etiquetaPeriodo("2026-09")).toBe("2026 - Septiembre");
  });

  it("cubre los doce meses", () => {
    const meses = [
      "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
      "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
    ];
    meses.forEach((mes, i) => {
      expect(etiquetaPeriodo(`2026-${String(i + 1).padStart(2, "0")}`)).toBe(`2026 - ${mes}`);
    });
  });

  it("devuelve el texto tal cual si no es un periodo", () => {
    expect(etiquetaPeriodo("hola")).toBe("hola");
  });
});

describe("periodo recordado", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("se guarda por empresa", () => {
    recordarPeriodo("e1", "2026-08");

    expect(periodoRecordado("e1")).toBe("2026-08");
    expect(periodoRecordado("e2")).toBeNull();
  });

  it("ignora un valor guardado que ya no es un periodo", () => {
    window.localStorage.setItem("fiscalcore-periodo-e1", "basura");

    expect(periodoRecordado("e1")).toBeNull();
  });

  it("no rompe si localStorage lanza excepción", () => {
    const getItem = vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });
    const setItem = vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => {
      throw new Error("bloqueado");
    });

    expect(periodoRecordado("e1")).toBeNull();
    expect(() => recordarPeriodo("e1", "2026-08")).not.toThrow();

    getItem.mockRestore();
    setItem.mockRestore();
  });
});

describe("resolverPeriodo", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("prefiere el periodo de la URL", () => {
    recordarPeriodo("e1", "2026-08");

    expect(resolverPeriodo({ url: "2026-09", empresaId: "e1", hoy: HOY })).toBe("2026-09");
  });

  it("si la URL no sirve, usa el recordado de la empresa", () => {
    recordarPeriodo("e1", "2026-08");

    expect(resolverPeriodo({ url: "2026-99", empresaId: "e1", hoy: HOY })).toBe("2026-08");
    expect(resolverPeriodo({ url: null, empresaId: "e1", hoy: HOY })).toBe("2026-08");
  });

  it("sin URL ni recordado usa el mes actual", () => {
    expect(resolverPeriodo({ url: null, empresaId: "e1", hoy: HOY })).toBe("2026-10");
  });

  it("no usa el periodo recordado de otra empresa", () => {
    recordarPeriodo("e2", "2026-08");

    expect(resolverPeriodo({ url: null, empresaId: "e1", hoy: HOY })).toBe("2026-10");
  });
});
