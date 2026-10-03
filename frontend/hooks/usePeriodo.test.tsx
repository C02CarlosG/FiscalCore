import { beforeEach, describe, expect, it, vi } from "vitest";
import { renderHook } from "@testing-library/react";
import { usePeriodo } from "./usePeriodo";
import { guardarPeriodo, mesActual } from "@/lib/periodo";

const replace = vi.fn();
const push = vi.fn();
let search = "";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace, push }),
  usePathname: () => "/empresas/e1/cfdi/emitidos",
  useSearchParams: () => new URLSearchParams(search),
}));

describe("usePeriodo", () => {
  beforeEach(() => {
    replace.mockReset();
    push.mockReset();
    search = "";
    window.localStorage.clear();
  });

  it("devuelve el periodo de la URL sin tocarla", () => {
    search = "periodo=2026-09&tipo=E";
    const { result } = renderHook(() => usePeriodo("e1"));
    expect(result.current[0]).toBe("2026-09");
    expect(replace).not.toHaveBeenCalled();
  });

  it("sin periodo en la URL usa el recordado de la empresa", () => {
    guardarPeriodo("e1", "2026-03");
    renderHook(() => usePeriodo("e1"));
    expect(replace).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-03");
  });

  it("sin recordado usa el mes actual", () => {
    const { result } = renderHook(() => usePeriodo("e1"));
    expect(result.current[0]).toBe("");
    expect(replace).toHaveBeenCalledWith(`/empresas/e1/cfdi/emitidos?periodo=${mesActual()}`);
  });

  it("ignora un periodo inválido en la URL", () => {
    search = "periodo=basura";
    renderHook(() => usePeriodo("e1"));
    expect(replace).toHaveBeenCalled();
  });

  it("al cambiar conserva los demás parámetros, quita la página y recuerda el periodo", () => {
    search = "periodo=2026-09&tipo=E&pagina=3";
    const { result } = renderHook(() => usePeriodo("e1"));
    result.current[1]("2026-08");
    expect(push).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-08&tipo=E");
    expect(window.localStorage.getItem("fiscalcore.periodo.e1")).toBe("2026-09");
  });
});
