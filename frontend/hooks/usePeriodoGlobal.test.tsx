import { beforeEach, describe, expect, it, vi } from "vitest";
import { act, renderHook } from "@testing-library/react";
import { usePeriodoGlobal } from "./usePeriodoGlobal";
import { periodoActual, periodoRecordado, recordarPeriodo } from "@/lib/periodo";

const replaceMock = vi.fn();
let busqueda = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => "/empresas/e1/cedula-iva",
  useSearchParams: () => new URLSearchParams(busqueda),
}));

describe("usePeriodoGlobal", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    window.localStorage.clear();
    busqueda = "";
  });

  it("usa el periodo de la URL y lo recuerda para la empresa", () => {
    busqueda = "periodo=2026-09";

    const { result } = renderHook(() => usePeriodoGlobal("e1"));

    expect(result.current[0]).toBe("2026-09");
    expect(periodoRecordado("e1")).toBe("2026-09");
    expect(replaceMock).not.toHaveBeenCalled();
  });

  it("sin periodo en la URL usa el recordado y lo agrega a la URL", () => {
    recordarPeriodo("e1", "2026-08");

    const { result } = renderHook(() => usePeriodoGlobal("e1"));

    expect(result.current[0]).toBe("2026-08");
    expect(replaceMock).toHaveBeenCalledWith("/empresas/e1/cedula-iva?periodo=2026-08", { scroll: false });
  });

  it("sin URL ni recordado usa el mes actual", () => {
    const { result } = renderHook(() => usePeriodoGlobal("e1"));

    expect(result.current[0]).toBe(periodoActual());
    expect(replaceMock).toHaveBeenCalledWith(`/empresas/e1/cedula-iva?periodo=${periodoActual()}`, { scroll: false });
  });

  it("un periodo inválido en la URL se reemplaza", () => {
    busqueda = "periodo=2026-99";
    recordarPeriodo("e1", "2026-07");

    const { result } = renderHook(() => usePeriodoGlobal("e1"));

    expect(result.current[0]).toBe("2026-07");
    expect(replaceMock).toHaveBeenCalledWith("/empresas/e1/cedula-iva?periodo=2026-07", { scroll: false });
  });

  it("elegir un periodo lo escribe en la URL y lo guarda solo para esa empresa", () => {
    busqueda = "periodo=2026-09";
    const { result } = renderHook(() => usePeriodoGlobal("e1"));
    replaceMock.mockClear();

    act(() => result.current[1]("2026-05"));

    expect(replaceMock).toHaveBeenCalledWith("/empresas/e1/cedula-iva?periodo=2026-05", { scroll: false });
    expect(periodoRecordado("e1")).toBe("2026-05");
    expect(periodoRecordado("e2")).toBeNull();
  });

  it("conserva los demás parámetros y regresa a la página 1 al cambiar de periodo", () => {
    busqueda = "periodo=2026-09&tipo=E&pagina=4";
    const { result } = renderHook(() => usePeriodoGlobal("e1"));
    replaceMock.mockClear();

    act(() => result.current[1]("2026-05"));

    expect(replaceMock).toHaveBeenCalledWith("/empresas/e1/cedula-iva?periodo=2026-05&tipo=E", { scroll: false });
  });
});
