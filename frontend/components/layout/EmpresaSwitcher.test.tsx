import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EmpresaSwitcher } from "./EmpresaSwitcher";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import type { Empresa } from "@/types/api";

const pushMock = vi.fn();
const mockPathname = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: pushMock }),
  usePathname: () => mockPathname(),
}));

vi.mock("@/components/providers/EmpresaProvider", () => ({
  useEmpresaContext: vi.fn(),
}));

const empresaA = { id: "e1", rfc: "AAA010101AAA", razon_social: "Acme SA de CV" } as Empresa;
const empresaB = { id: "e2", rfc: "BBB020202BBB", razon_social: "Beta SA de CV" } as Empresa;

describe("EmpresaSwitcher", () => {
  beforeEach(() => {
    pushMock.mockClear();
    vi.mocked(useEmpresaContext).mockReturnValue({
      empresaId: "e1",
      empresas: [empresaA, empresaB],
      setLastEmpresaId: vi.fn(),
    });
  });

  it("navega a la misma sub-ruta al cambiar de empresa", async () => {
    mockPathname.mockReturnValue("/empresas/e1/ingesta");
    const user = userEvent.setup();
    render(<EmpresaSwitcher />);

    await user.click(screen.getByRole("button"));
    await user.click(screen.getByRole("menuitem", { name: /Beta SA de CV/ }));

    expect(pushMock).toHaveBeenCalledWith("/empresas/e2/ingesta");
  });

  it("navega a dashboard cuando no hay sub-ruta reconocible", async () => {
    mockPathname.mockReturnValue("/empresas");
    const user = userEvent.setup();
    render(<EmpresaSwitcher />);

    await user.click(screen.getByRole("button"));
    await user.click(screen.getByRole("menuitem", { name: /Beta SA de CV/ }));

    expect(pushMock).toHaveBeenCalledWith("/empresas/e2/dashboard");
  });

  it("incluye un enlace para administrar empresas", async () => {
    mockPathname.mockReturnValue("/empresas/e1/dashboard");
    const user = userEvent.setup();
    render(<EmpresaSwitcher />);

    await user.click(screen.getByRole("button"));

    expect(
      screen.getByRole("menuitem", { name: /Administrar empresas/ }),
    ).toHaveAttribute("href", "/empresas");
  });
});
