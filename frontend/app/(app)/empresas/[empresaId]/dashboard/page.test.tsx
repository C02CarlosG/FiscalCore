import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import DashboardPage from "./page";
import { useDashboard } from "@/hooks/useDashboard";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";

vi.mock("next/navigation", () => ({
  useParams: () => ({ empresaId: "e1" }),
}));

vi.mock("@/hooks/useDashboard", () => ({
  useDashboard: vi.fn(),
}));

vi.mock("@/hooks/usePeriodoGlobal", () => ({
  usePeriodoGlobal: vi.fn(),
}));

vi.mock("@/hooks/usePeriodos", () => ({
  usePeriodos: () => ({ data: { periodos: ["2026-09", "2026-08"] } }),
}));

const datos = {
  empresa: { razon_social: "Coplasur SA de CV" },
  score_actual: null,
  riesgos_abiertos: [],
  resumen_riesgos: { critico: 0, alto: 0, medio: 0, bajo: 0, monto_total_en_riesgo: 0 },
  tendencia_score: [
    { periodo: "2026-07", score: 74 },
    { periodo: "2026-08", score: 71 },
    { periodo: "2026-09", score: 80 },
  ],
  indicadores: { pct_conciliacion: 50 },
};

function dashboardCon(data: unknown) {
  vi.mocked(useDashboard).mockReturnValue({
    data,
    isLoading: false,
    isError: false,
    refetch: vi.fn(),
  } as any);
}

describe("DashboardPage", () => {
  beforeEach(() => {
    vi.mocked(usePeriodoGlobal).mockReturnValue(["2026-09", vi.fn()]);
    dashboardCon(undefined);
  });

  it("does not render a company selector", () => {
    render(<DashboardPage />);
    expect(screen.queryByRole("combobox", { name: /empresa/i })).not.toBeInTheDocument();
  });

  it("offers the global period selector", () => {
    render(<DashboardPage />);
    expect(screen.getByRole("combobox", { name: "Periodo" })).toHaveTextContent("2026 - Septiembre");
  });

  it("calls useDashboard with the empresaId and the global period", () => {
    render(<DashboardPage />);
    expect(useDashboard).toHaveBeenCalledWith("e1", "2026-09");
  });

  it("shows the score of the chosen period, not the last one of the trend", () => {
    vi.mocked(usePeriodoGlobal).mockReturnValue(["2026-08", vi.fn()]);
    dashboardCon(datos);

    render(<DashboardPage />);

    expect(screen.getByText("71/100")).toBeInTheDocument();
    expect(screen.queryByText("80/100")).not.toBeInTheDocument();
    expect(screen.getByText("-3 pts")).toBeInTheDocument();
    expect(screen.getByText("vs. 2026 - Julio")).toBeInTheDocument();
  });

  it("shows a dash when the period has no score yet", () => {
    vi.mocked(usePeriodoGlobal).mockReturnValue(["2026-10", vi.fn()]);
    dashboardCon(datos);

    render(<DashboardPage />);

    expect(screen.getByText("—")).toBeInTheDocument();
    expect(screen.queryByText("80/100")).not.toBeInTheDocument();
  });
});
