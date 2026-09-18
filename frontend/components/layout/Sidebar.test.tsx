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

  it("renders the flat nav items with links scoped to the active empresa", () => {
    render(<Sidebar mobileOpen={false} onMobileOpenChange={() => {}} />);

    expect(screen.getByRole("link", { name: /Dashboard/ })).toHaveAttribute(
      "href",
      "/empresas/e1/dashboard",
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

  it("expands the Gestión de CFDI submenu with its 4 options on click", async () => {
    const user = userEvent.setup();
    render(<Sidebar mobileOpen={false} onMobileOpenChange={() => {}} />);

    expect(screen.queryByRole("link", { name: "Visor SAT" })).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Gestión de CFDI/ }));

    expect(screen.getByRole("link", { name: "Visor SAT" })).toHaveAttribute(
      "href",
      "/empresas/e1/cfdi",
    );
    expect(screen.getByRole("link", { name: "CFDI Emitidos" })).toHaveAttribute(
      "href",
      "/empresas/e1/cfdi/emitidos",
    );
    expect(screen.getByRole("link", { name: "CFDI Recibidos" })).toHaveAttribute(
      "href",
      "/empresas/e1/cfdi/recibidos",
    );
    expect(screen.getByRole("link", { name: "CFDI Nómina" })).toHaveAttribute(
      "href",
      "/empresas/e1/cfdi/nomina",
    );
  });

  it("auto-expands the Gestión de CFDI submenu when a cfdi route is active", () => {
    mockPathname.mockReturnValue("/empresas/e1/cfdi/nomina");
    render(<Sidebar mobileOpen={false} onMobileOpenChange={() => {}} />);

    expect(screen.getByRole("link", { name: "CFDI Nómina" })).toHaveAttribute(
      "href",
      "/empresas/e1/cfdi/nomina",
    );
  });

  it("disables all nav items when there is no empresa selected", () => {
    vi.mocked(useEmpresaContext).mockReturnValue({
      empresaId: null,
      empresas: [],
      setLastEmpresaId: vi.fn(),
    });
    render(<Sidebar mobileOpen={false} onMobileOpenChange={() => {}} />);

    expect(
      screen.queryByRole("link", { name: /Dashboard/ }),
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole("button", { name: /Gestión de CFDI/ }),
    ).not.toBeInTheDocument();
    expect(screen.getByText("Gestión de CFDI")).toBeInTheDocument();
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
