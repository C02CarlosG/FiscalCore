import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import ConciliacionPage from "./page";
import { useConciliacionResumen, useConciliacionesAccionables } from "@/hooks/useConciliaciones";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";

vi.mock("next/navigation", () => ({ useParams: () => ({ empresaId: "e1" }) }));
vi.mock("@/hooks/useConciliaciones", () => ({
  useConciliacionResumen: vi.fn(),
  useConciliacionesAccionables: vi.fn(),
}));
vi.mock("@/hooks/usePeriodoGlobal", () => ({ usePeriodoGlobal: vi.fn() }));
vi.mock("@/hooks/usePeriodos", () => ({ usePeriodos: () => ({ data: { periodos: ["2026-09"] } }) }));

describe("ConciliacionPage", () => {
  beforeEach(() => {
    vi.mocked(usePeriodoGlobal).mockReturnValue(["2026-09", vi.fn()]);
    const vacio = { data: undefined, isLoading: false, isError: false, refetch: vi.fn() } as any;
    vi.mocked(useConciliacionResumen).mockReturnValue(vacio);
    vi.mocked(useConciliacionesAccionables).mockReturnValue(vacio);
  });

  it("queries the conciliation for the global period", () => {
    render(<ConciliacionPage />);

    expect(useConciliacionResumen).toHaveBeenCalledWith("e1", "2026-09");
    expect(useConciliacionesAccionables).toHaveBeenCalledWith("e1", "2026-09");
    expect(screen.getByRole("combobox", { name: "Periodo" })).toHaveTextContent("2026 - Septiembre");
  });
});
