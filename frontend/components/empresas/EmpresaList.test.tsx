import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EmpresaList } from "./EmpresaList";
import type { Empresa } from "@/types/api";

const empresa: Empresa = {
  id: "e1",
  rfc: "AAA010101AAA",
  razon_social: "Acme SA de CV",
  regimen_fiscal: null,
  cp_fiscal: null,
  curp: null,
  obligaciones: null,
  representante_legal: null,
  rfc_representante: null,
  activo: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("EmpresaList", () => {
  it("renders an Ingesta link pointing to the empresa's ingesta page", () => {
    render(<EmpresaList empresas={[empresa]} />);

    const link = screen.getByRole("link", { name: "Ingesta" });
    expect(link).toHaveAttribute("href", "/empresas/e1/ingesta");
  });

  it("still renders the Cédula de IVA link", () => {
    render(<EmpresaList empresas={[empresa]} />);

    const link = screen.getByRole("link", { name: "Cédula de IVA" });
    expect(link).toHaveAttribute("href", "/empresas/e1/cedula-iva");
  });
});
