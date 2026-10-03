import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import CedulaIvaPage from "./page";
import { useCedulaIva } from "@/hooks/useCedulaIva";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";

vi.mock("next/navigation", () => ({ useParams: () => ({ empresaId: "e1" }) }));
vi.mock("@/hooks/useCedulaIva", () => ({ useCedulaIva: vi.fn() }));
vi.mock("@/hooks/usePeriodoGlobal", () => ({ usePeriodoGlobal: vi.fn() }));
vi.mock("@/hooks/usePeriodos", () => ({ usePeriodos: () => ({ data: { periodos: ["2026-09"] } }) }));

describe("CedulaIvaPage", () => {
  beforeEach(() => {
    vi.mocked(usePeriodoGlobal).mockReturnValue(["2026-09", vi.fn()]);
    vi.mocked(useCedulaIva).mockReturnValue({
      data: undefined, isLoading: false, isError: false, refetch: vi.fn(),
    } as any);
  });

  it("calculates the cédula for the global period", () => {
    render(<CedulaIvaPage />);

    expect(useCedulaIva).toHaveBeenCalledWith("e1", "2026-09");
    expect(screen.getByRole("combobox", { name: "Periodo" })).toHaveTextContent("2026 - Septiembre");
  });

  it("no longer asks to pick a period: there is always one", () => {
    render(<CedulaIvaPage />);

    expect(screen.queryByText(/Selecciona un periodo/)).not.toBeInTheDocument();
  });
});
