import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import DashboardPage from "./page";
import { useDashboard } from "@/hooks/useDashboard";

vi.mock("next/navigation", () => ({
  useParams: () => ({ empresaId: "e1" }),
}));

vi.mock("@/hooks/usePeriodo", () => ({
  usePeriodo: () => ["2026-09", vi.fn()],
  usePeriodosConDatos: () => ({ data: [] }),
}));

vi.mock("@/hooks/useDashboard", () => ({
  useDashboard: vi.fn(),
}));

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.mocked(useDashboard).mockReturnValue({
      data: undefined,
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any);
  });

  it("renders only the period selector, no company selector", () => {
    render(<DashboardPage />);
    expect(screen.getAllByRole("combobox")).toHaveLength(1);
    expect(screen.getByRole("combobox", { name: "Periodo" })).toBeInTheDocument();
  });

  it("shows the score of the selected periodo, not the last of the trend", () => {
    vi.mocked(useDashboard).mockReturnValue({
      data: {
        empresa: { razon_social: "ACME" },
        riesgos_abiertos: [],
        resumen_riesgos: { monto_total_en_riesgo: 0 },
        tendencia_score: [
          { periodo: "2026-08", score: 70 },
          { periodo: "2026-09", score: 80 },
          { periodo: "2026-10", score: 90 },
        ],
        indicadores: {},
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any);
    render(<DashboardPage />);
    expect(screen.getByText("80/100")).toBeInTheDocument();
    expect(screen.getByText("+10 pts")).toBeInTheDocument();
  });

  it("calls useDashboard with the empresaId from the URL", () => {
    render(<DashboardPage />);
    expect(useDashboard).toHaveBeenCalledWith("e1", "2026-09");
  });
});
