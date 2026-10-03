import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ListadoCfdi } from "./ListadoCfdi";
import { useCfdiColumnas, useCfdiListado, useCfdiResumen } from "@/hooks/useCfdiListado";

const push = vi.fn();
let search = "periodo=2026-09";
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, replace: vi.fn() }),
  usePathname: () => "/empresas/e1/cfdi/emitidos",
  useSearchParams: () => new URLSearchParams(search),
}));
vi.mock("@/hooks/usePeriodo", () => ({
  usePeriodo: () => ["2026-09", vi.fn()],
  usePeriodosConDatos: () => ({ data: ["2026-09"] }),
}));
vi.mock("@/hooks/useCfdiListado", () => ({
  useCfdiListado: vi.fn(),
  useCfdiResumen: vi.fn(),
  useCfdiColumnas: vi.fn(),
}));

const totalesVacios = {
  conteo: 0, retencion_iva: null, retencion_ieps: null, retencion_isr: null, traslado_iva: null, traslado_ieps: null,
  traslado_isr: null, total_retenciones: null, subtotal: null, descuento: null, neto: null, total: null,
};
const consulta = (data: unknown, extra = {}) => ({ data, isError: false, refetch: vi.fn(), ...extra }) as any;

beforeEach(() => {
  push.mockReset();
  search = "periodo=2026-09";
  vi.mocked(useCfdiColumnas).mockReturnValue(consulta({
    encabezado: [
      { clave: "fecha_emision", etiqueta: "Fecha expedición", tipo_dato: "fecha", visible_por_defecto: true, ordenable: true },
      { clave: "uuid", etiqueta: "UUID", tipo_dato: "texto", visible_por_defecto: false, ordenable: true },
      { clave: "total", etiqueta: "Total", tipo_dato: "moneda", visible_por_defecto: true, ordenable: true },
      { clave: "estado", etiqueta: "Estado", tipo_dato: "catalogo", visible_por_defecto: true, ordenable: false },
    ],
    concepto: [],
  }));
  vi.mocked(useCfdiResumen).mockReturnValue(consulta({
    conteos: { I: 12, E: 1, T: 0, N: 3, P: 2 },
    totales: { periodo: { ...totalesVacios, conteo: 12, total: 1160 }, acumulado: totalesVacios },
    advertencias: [],
  }));
  vi.mocked(useCfdiListado).mockReturnValue(consulta({
    items: [{ uuid: "U1", fecha_emision: "2026-09-03T10:00:00", total: 1160, estado: "vigente" }],
    total: 61, pagina: 1, por_pagina: 30,
  }));
});

describe("ListadoCfdi", () => {
  it("muestra pestañas con conteo, totales, solo las columnas visibles y fechas dd/mm/aaaa", () => {
    render(<ListadoCfdi empresaId="e1" direccion="emitidos" />);
    expect(screen.getByRole("tab", { name: /Ingreso\s*12/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Nómina\s*3/ })).toBeInTheDocument();
    expect(screen.getByText("Acumulado")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: /Fecha expedición/ })).toBeInTheDocument();
    expect(screen.queryByRole("columnheader", { name: "UUID" })).not.toBeInTheDocument();
    expect(screen.getByText("03/09/2026")).toBeInTheDocument();
    expect(screen.getByText("Vigente")).toBeInTheDocument();
    expect(screen.getByText("1–30 de 61")).toBeInTheDocument();
  });

  it("muestra guiones en los totales sin datos del acumulado", () => {
    render(<ListadoCfdi empresaId="e1" direccion="emitidos" />);
    expect(screen.getAllByText("—").length).toBeGreaterThan(5);
  });

  it("cambiar de pestaña actualiza la URL conservando el periodo", async () => {
    render(<ListadoCfdi empresaId="e1" direccion="emitidos" />);
    await userEvent.setup().click(screen.getByRole("tab", { name: /Egreso/ }));
    expect(push).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-09&tipo=E");
  });

  it("ordenar por una columna alterna el sentido en la URL", async () => {
    search = "periodo=2026-09&orden=total&dir=asc";
    render(<ListadoCfdi empresaId="e1" direccion="emitidos" />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Total" }));
    expect(push).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-09&orden=total&dir=desc");
  });

  it("paginar pide la siguiente página al servidor", async () => {
    render(<ListadoCfdi empresaId="e1" direccion="emitidos" />);
    await userEvent.setup().click(screen.getByRole("button", { name: "Siguiente" }));
    expect(push).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-09&pagina=2");
  });

  it("el sub-filtro de pago solo aparece con PPD", async () => {
    const { unmount } = render(<ListadoCfdi empresaId="e1" direccion="emitidos" />);
    expect(screen.queryByRole("group", { name: "Pago de PPD" })).not.toBeInTheDocument();
    unmount();
    search = "periodo=2026-09&metodo=PPD";
    render(<ListadoCfdi empresaId="e1" direccion="emitidos" />);
    expect(screen.getByRole("group", { name: "Pago de PPD" })).toBeInTheDocument();
  });

  it("sin resultados ofrece limpiar los filtros", async () => {
    vi.mocked(useCfdiListado).mockReturnValue(consulta({ items: [], total: 0, pagina: 1, por_pagina: 30 }));
    search = "periodo=2026-09&estado=cancelado";
    render(<ListadoCfdi empresaId="e1" direccion="emitidos" />);
    expect(screen.getByText("No hay CFDI con estos filtros")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Limpiar filtros" }));
    expect(push).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-09");
  });

  it("muestra error con reintento", () => {
    vi.mocked(useCfdiListado).mockReturnValue(consulta(undefined, { isError: true }));
    render(<ListadoCfdi empresaId="e1" direccion="emitidos" />);
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudieron cargar los CFDI.");
  });

  it("muestra las advertencias de anticipos", () => {
    vi.mocked(useCfdiResumen).mockReturnValue(consulta({
      conteos: { I: 1, E: 0, T: 0, N: 0, P: 0 },
      totales: { periodo: totalesVacios, acumulado: totalesVacios },
      advertencias: [{ tipo: "sin_egreso_anticipo", uuid_factura: "U1", mensaje: "La factura U1 aplica anticipo" }],
    }));
    render(<ListadoCfdi empresaId="e1" direccion="emitidos" />);
    expect(screen.getByText("La factura U1 aplica anticipo")).toBeInTheDocument();
  });
});
