import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { Sidebar } from "./Sidebar";
import { useEmpresaContext } from "@/components/providers/EmpresaProvider";
import { saveSession, getToken } from "@/lib/auth";
import type { LoginResponse } from "@/types/api";

const replaceMock = vi.fn();
const mockPathname = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => mockPathname(),
}));

vi.mock("@/components/providers/EmpresaProvider", () => ({
  useEmpresaContext: vi.fn(),
}));

const loginResponse: LoginResponse = {
  access_token: "token-123",
  token_type: "bearer",
  user_id: "u1",
  email: "ana@example.com",
  nombre: "Ana Torres",
  empresas: [],
};

describe("Sidebar", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    mockPathname.mockReturnValue("/empresas/e1/dashboard");
    window.localStorage.clear();
    vi.mocked(useEmpresaContext).mockReturnValue({
      empresaId: "e1",
      empresas: [],
      setLastEmpresaId: vi.fn(),
    });
  });

  it("renders the 5 nav items with links scoped to the active empresa", () => {
    render(<Sidebar mobileOpen={false} onMobileOpenChange={() => {}} />);

    expect(screen.getByRole("link", { name: /Dashboard/ })).toHaveAttribute(
      "href",
      "/empresas/e1/dashboard",
    );
    expect(screen.getByRole("link", { name: /Empresas/ })).toHaveAttribute(
      "href",
      "/empresas",
    );
    expect(screen.getByRole("link", { name: /Ingesta/ })).toHaveAttribute(
      "href",
      "/empresas/e1/ingesta",
    );
    expect(screen.getByRole("link", { name: /Conciliación/ })).toHaveAttribute(
      "href",
      "/empresas/e1/conciliacion",
    );
    expect(screen.getByRole("link", { name: /Cédula de IVA/ })).toHaveAttribute(
      "href",
      "/empresas/e1/cedula-iva",
    );
  });

  it("disables empresa-scoped items when there is no empresa selected", () => {
    vi.mocked(useEmpresaContext).mockReturnValue({
      empresaId: null,
      empresas: [],
      setLastEmpresaId: vi.fn(),
    });
    render(<Sidebar mobileOpen={false} onMobileOpenChange={() => {}} />);

    expect(
      screen.queryByRole("link", { name: /Dashboard/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: /Empresas/ })).toBeInTheDocument();
  });

  it("clears the session and redirects to /login on logout", async () => {
    saveSession(loginResponse);
    const user = userEvent.setup();
    render(<Sidebar mobileOpen={false} onMobileOpenChange={() => {}} />);

    await user.click(screen.getByRole("button", { name: "Cerrar sesión" }));

    expect(getToken()).toBeNull();
    expect(replaceMock).toHaveBeenCalledWith("/login");
  });
});
