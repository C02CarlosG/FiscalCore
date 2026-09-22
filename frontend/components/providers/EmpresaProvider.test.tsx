import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { EmpresaProvider, useEmpresaContext } from "./EmpresaProvider";
import type { Empresa } from "@/types/api";

const mockParams = vi.fn();
vi.mock("next/navigation", () => ({
  useParams: () => mockParams(),
}));

vi.mock("@/hooks/useEmpresas", () => ({
  useEmpresas: () => ({
    data: [
      { id: "e1", rfc: "AAA010101AAA", razon_social: "Acme SA de CV" } as Empresa,
    ],
  }),
}));

function Consumer() {
  const { empresaId, empresas } = useEmpresaContext();
  return (
    <p>
      {empresaId ?? "sin-empresa"} / {empresas.length} empresas
    </p>
  );
}

function renderWithClient(ui: React.ReactNode) {
  const client = new QueryClient();
  return render(
    <QueryClientProvider client={client}>{ui}</QueryClientProvider>,
  );
}

describe("EmpresaProvider", () => {
  beforeEach(() => {
    mockParams.mockReturnValue({});
    window.localStorage.clear();
  });

  it("expone empresaId=null y la lista de empresas cuando la URL no trae empresaId", () => {
    renderWithClient(
      <EmpresaProvider>
        <Consumer />
      </EmpresaProvider>,
    );
    expect(screen.getByText("sin-empresa / 1 empresas")).toBeInTheDocument();
  });

  it("expone el empresaId de la URL cuando existe", () => {
    mockParams.mockReturnValue({ empresaId: "e1" });
    renderWithClient(
      <EmpresaProvider>
        <Consumer />
      </EmpresaProvider>,
    );
    expect(screen.getByText("e1 / 1 empresas")).toBeInTheDocument();
  });
});
