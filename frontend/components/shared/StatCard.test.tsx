import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { TrendingUp } from "lucide-react";
import { StatCard } from "./StatCard";

describe("StatCard", () => {
  it("renders the label and value", () => {
    render(<StatCard label="Score fiscal actual" value="78/100" icon={TrendingUp} />);
    expect(screen.getByText("Score fiscal actual")).toBeInTheDocument();
    expect(screen.getByText("78/100")).toBeInTheDocument();
  });

  it("renders an upward delta in the ok color", () => {
    render(
      <StatCard
        label="Score fiscal actual"
        value="78/100"
        icon={TrendingUp}
        delta={{ value: "+4 pts", direction: "up", label: "vs. Jul 2026" }}
      />,
    );
    const delta = screen.getByText("+4 pts");
    expect(delta).toBeInTheDocument();
    expect(delta.className).toContain("status-ok");
    expect(screen.getByText("vs. Jul 2026")).toBeInTheDocument();
  });

  it("renders a downward delta in the error color", () => {
    render(
      <StatCard
        label="Monto en riesgo"
        value="$284,320"
        icon={TrendingUp}
        delta={{ value: "+8.2%", direction: "down", label: "vs. Jul 2026" }}
      />,
    );
    expect(screen.getByText("+8.2%").className).toContain("status-error");
  });

  it("renders without a delta section when none is provided", () => {
    render(<StatCard label="Riesgos abiertos" value="12" icon={TrendingUp} />);
    expect(screen.queryByText(/vs\./)).not.toBeInTheDocument();
  });
});
