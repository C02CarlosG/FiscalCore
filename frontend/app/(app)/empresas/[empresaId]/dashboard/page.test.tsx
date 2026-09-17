import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import DashboardPage from "./page";
import { useDashboard } from "@/hooks/useDashboard";

vi.mock("next/navigation", () => ({
  useParams: () => ({ empresaId: "e1" }),
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

  it("does not render a company selector", () => {
    render(<DashboardPage />);
    expect(screen.queryByRole("combobox")).not.toBeInTheDocument();
  });

  it("calls useDashboard with the empresaId from the URL", () => {
    render(<DashboardPage />);
    expect(useDashboard).toHaveBeenCalledWith("e1", "");
  });
});
