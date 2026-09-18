import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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

async function abrirMenuAcciones() {
  const user = userEvent.setup();
  await user.click(screen.getByRole("button", { name: /Acciones para/ }));
  return user;
}

describe("EmpresaList", () => {
  it("shows the empty state message when there are no empresas", () => {
    render(<EmpresaList empresas={[]} />);
    expect(
      screen.getByText("Aún no hay empresas registradas."),
    ).toBeInTheDocument();
  });

  it("renders an Ingesta link pointing to the empresa's ingesta page", async () => {
    render(<EmpresaList empresas={[empresa]} />);
    await abrirMenuAcciones();

    const link = screen.getByRole("menuitem", { name: "Ingesta" });
    expect(link).toHaveAttribute("href", "/empresas/e1/ingesta");
  });

  it("still renders the Cédula de IVA and Conciliación links", async () => {
    render(<EmpresaList empresas={[empresa]} />);
    await abrirMenuAcciones();

    expect(screen.getByRole("menuitem", { name: "Cédula de IVA" })).toHaveAttribute(
      "href",
      "/empresas/e1/cedula-iva",
    );
    expect(screen.getByRole("menuitem", { name: "Conciliación" })).toHaveAttribute(
      "href",
      "/empresas/e1/conciliacion",
    );
  });
});
