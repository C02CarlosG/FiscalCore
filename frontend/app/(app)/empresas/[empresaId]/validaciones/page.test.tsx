import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import ValidacionesPage from "./page";
import { ValidacionesPanel } from "@/components/validaciones/ValidacionesPanel";

vi.mock("next/navigation", () => ({ useParams: () => ({ empresaId: "e1" }) }));
vi.mock("@/hooks/usePeriodoGlobal", () => ({ usePeriodoGlobal: () => ["2026-03", vi.fn()] }));
vi.mock("@/hooks/usePeriodos", () => ({ usePeriodos: () => ({ data: { periodos: ["2026-03"] } }) }));
vi.mock("@/components/validaciones/ValidacionesPanel", () => ({ ValidacionesPanel: vi.fn(() => null) }));

describe("ValidacionesPage", () => {
  it("revisa la empresa en el periodo global", () => {
    render(<ValidacionesPage />);
    expect(screen.getByText("Validaciones de CFDI")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: "Periodo" })).toHaveTextContent("2026 - Marzo");
    expect(vi.mocked(ValidacionesPanel).mock.calls[0][0]).toEqual({ empresaId: "e1", periodo: "2026-03" });
  });
});
