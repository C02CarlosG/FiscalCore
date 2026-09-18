import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Header } from "./Header";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import { saveSession, getToken } from "@/lib/auth";
import type { Empresa, LoginResponse } from "@/types/api";

const replaceMock = vi.fn();
const pushMock = vi.fn();
const mockPathname = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock, push: pushMock }),
  usePathname: () => mockPathname(),
}));

vi.mock("@/components/providers/EmpresaProvider", () => ({
  useEmpresaContext: vi.fn(),
}));

const empresaA = { id: "e1", rfc: "AAA010101AAA", razon_social: "Acme SA de CV" } as Empresa;

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "ana@example.com",
  nombre: "Ana Torres",
  empresas: [],
};

describe("Header", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    pushMock.mockClear();
    mockPathname.mockReturnValue("/empresas/e1/dashboard");
    window.localStorage.clear();
    vi.mocked(useEmpresaContext).mockReturnValue({
      empresaId: "e1",
      empresas: [empresaA],
      setLastEmpresaId: vi.fn(),
    });
  });

  it("shows the breadcrumb label for the current route", () => {
    render(<Header onMenuClick={() => {}} />);
    expect(screen.getByText("Dashboard")).toBeInTheDocument();
  });

  it("shows the Visor SAT breadcrumb and not Empresas on the cfdi route", () => {
    mockPathname.mockReturnValue("/empresas/e1/cfdi");
    render(<Header onMenuClick={() => {}} />);
    expect(screen.getByText("Visor SAT")).toBeInTheDocument();
    expect(screen.queryByText("Empresas")).not.toBeInTheDocument();
  });

  it("navigates to the matched empresa on search", async () => {
    const user = userEvent.setup();
    render(<Header onMenuClick={() => {}} />);

    await user.type(screen.getByPlaceholderText(/Buscar empresa/), "Acme");
    await user.click(screen.getByRole("option", { name: /Acme SA de CV/ }));

    expect(pushMock).toHaveBeenCalledWith("/empresas/e1/dashboard");
  });

  it("clears the session and redirects to /login on logout", async () => {
    saveSession(loginResponse);
    const user = userEvent.setup();
    render(<Header onMenuClick={() => {}} />);

    await user.click(screen.getByRole("button", { name: /Ana Torres/ }));
    await user.click(screen.getByRole("menuitem", { name: "Cerrar sesión" }));

    expect(getToken()).toBeNull();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });
});
