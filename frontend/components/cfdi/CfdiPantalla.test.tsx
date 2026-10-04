import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CfdiPantalla } from "./CfdiPantalla";
import { useCfdiColumnas, useCfdiListado, useCfdiResumen } from "@/hooks/useCfdis";
import { periodoRecordado } from "@/lib/periodo";
import type { CfdiColumna, CfdiResumenResponse, CfdiTotalesBloque } from "@/types/api";

const replaceMock = vi.fn();
let busqueda = "";
let ruta = "/empresas/e1/cfdi/emitidos";
vi.mock("next/navigation", () => ({
  useParams: () => ({ empresaId: "e1" }),
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => ruta,
  useSearchParams: () => new URLSearchParams(busqueda),
}));

vi.mock("@/hooks/useCfdis", () => ({
  useCfdiColumnas: vi.fn(),
  useCfdiListado: vi.fn(),
  useCfdiResumen: vi.fn(),
}));

vi.mock("@/hooks/usePeriodos", () => ({
  usePeriodos: () => ({ data: { periodos: ["2026-09", "2026-08"] } }),
}));

const col = (clave: string, etiqueta: string, tipo_dato: CfdiColumna["tipo_dato"]): CfdiColumna => ({
  clave, etiqueta, tipo_dato, grupo: "encabezado", visible_por_defecto: true, ordenable: true, filtrable: true, opciones: [],
});

const catalogo = { encabezado: [col("fecha_emision", "Fecha de expedición", "fecha"), col("total", "Total", "moneda")], concepto: [] };

const bloque = (conteo: number, total: number | null): CfdiTotalesBloque => ({
  conteo, retencion_iva: null, retencion_ieps: null, retencion_isr: null, traslado_iva: null, traslado_ieps: null,
  traslado_isr: null, total_retenciones: null, subtotal: null, descuento: null, neto: null, total,
});

const resumen = (extra: Partial<CfdiResumenResponse> = {}): CfdiResumenResponse => ({
  conteos: { I: 507, E: 12, T: 0, N: 33, P: 80 },
  totales: { periodo: bloque(507, 11100), acumulado: bloque(4200, 99000) },
  advertencias: [],
  ...extra,
});

const consulta = (data: unknown, extra: Record<string, unknown> = {}) =>
  ({ data, isError: false, isFetching: false, refetch: vi.fn(), ...extra }) as never;

const listadoCon = (items: Record<string, unknown>[], total = items.length) =>
  consulta({ items, total, pagina: 1, por_pagina: 30 });

function preparar({ listado = listadoCon([{ uuid: "U1", fecha_emision: "2026-09-05T10:00:00", total: 1160 }], 507), res = consulta(resumen()) } = {}) {
  vi.mocked(useCfdiColumnas).mockReturnValue(consulta(catalogo));
  vi.mocked(useCfdiListado).mockReturnValue(listado);
  vi.mocked(useCfdiResumen).mockReturnValue(res);
}

describe("CfdiPantalla", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    window.localStorage.clear();
    busqueda = "periodo=2026-09";
    ruta = "/empresas/e1/cfdi/emitidos";
    preparar();
  });

  it("titula la pantalla según la dirección", () => {
    const { unmount } = render(<CfdiPantalla direccion="emitidos" />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("CFDI emitidos");
    unmount();

    render(<CfdiPantalla direccion="recibidos" />);
    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("CFDI recibidos");
  });

  it("recargar con filtros en la URL pide exactamente esos filtros", () => {
    busqueda = "periodo=2026-09&tipo=E&metodo=PPD&pago=pendientes&q=abc&orden=total&dir=desc&pagina=2&por_pagina=50";

    render(<CfdiPantalla direccion="recibidos" />);

    const esperado = expect.objectContaining({
      periodo: "2026-09", tipo: "E", metodo: "PPD", pago: "pendientes", q: "abc",
      orden: "total", dir: "desc", pagina: 2, porPagina: 50,
    });
    expect(useCfdiListado).toHaveBeenCalledWith("e1", "recibidos", esperado);
    expect(useCfdiResumen).toHaveBeenCalledWith("e1", "recibidos", esperado);
    expect(useCfdiColumnas).toHaveBeenCalledWith("e1", "recibidos", "E");
  });

  it("pinta pestañas con conteo, totales y la tabla", () => {
    render(<CfdiPantalla direccion="emitidos" />);

    expect(screen.getByRole("tab", { name: /Ingreso/ })).toHaveTextContent("507");
    expect(within(screen.getByRole("row", { name: /^Periodo/ })).getByText("$11,100.00")).toBeInTheDocument();
    expect(screen.getByText("05/09/2026")).toBeInTheDocument();
  });

  it("cambiar de pestaña escribe el tipo y regresa a la página 1", async () => {
    busqueda = "periodo=2026-09&pagina=3";
    const user = userEvent.setup();
    render(<CfdiPantalla direccion="emitidos" />);

    await user.click(screen.getByRole("tab", { name: /Egreso/ }));

    expect(replaceMock).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-09&tipo=E", { scroll: false });
  });

  it("al cambiar de pestaña vuelve al orden por defecto", async () => {
    busqueda = "periodo=2026-09&orden=total&dir=desc";
    const user = userEvent.setup();
    render(<CfdiPantalla direccion="emitidos" />);

    await user.click(screen.getByRole("tab", { name: /Pago/ }));

    expect(replaceMock).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-09&tipo=P", { scroll: false });
  });

  it("ordenar por una columna lo escribe en la URL", async () => {
    const user = userEvent.setup();
    render(<CfdiPantalla direccion="emitidos" />);

    await user.click(screen.getByRole("button", { name: "Total" }));

    expect(replaceMock).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-09&orden=total", { scroll: false });
  });

  it("paginar no toca los filtros", async () => {
    busqueda = "periodo=2026-09&tipo=E&metodo=PPD";
    const user = userEvent.setup();
    render(<CfdiPantalla direccion="emitidos" />);

    await user.click(screen.getByRole("button", { name: "Siguiente" }));

    expect(replaceMock).toHaveBeenCalledWith(
      "/empresas/e1/cfdi/emitidos?periodo=2026-09&tipo=E&metodo=PPD&pagina=2",
      { scroll: false },
    );
  });

  it("elegir otro periodo lo recuerda para la empresa", async () => {
    const user = userEvent.setup();
    render(<CfdiPantalla direccion="emitidos" />);

    await user.click(screen.getByRole("combobox", { name: "Periodo" }));
    await user.click(await screen.findByRole("option", { name: "2026 - Agosto" }));

    expect(replaceMock).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-08", { scroll: false });
    expect(periodoRecordado("e1")).toBe("2026-08");
  });

  describe("advertencias de anticipos", () => {
    const advertencia = { tipo: "sin_egreso_anticipo", uuid_factura: "U9", mensaje: "La factura U9 aplica anticipo sin egreso" };

    it("se muestran en emitidos", () => {
      preparar({ res: consulta(resumen({ advertencias: [advertencia] })) });

      render(<CfdiPantalla direccion="emitidos" />);

      expect(screen.getByText("La factura U9 aplica anticipo sin egreso")).toBeInTheDocument();
    });

    it("no se muestran en recibidos", () => {
      preparar({ res: consulta(resumen({ advertencias: [advertencia] })) });

      render(<CfdiPantalla direccion="recibidos" />);

      expect(screen.queryByText("La factura U9 aplica anticipo sin egreso")).not.toBeInTheDocument();
    });
  });

  it("una empresa sin CFDI muestra el estado vacío y los totales con guiones", () => {
    const vacio = bloque(0, null);
    preparar({
      listado: listadoCon([], 0),
      res: consulta(resumen({ conteos: { I: 0, E: 0, T: 0, N: 0, P: 0 }, totales: { periodo: vacio, acumulado: vacio } })),
    });

    render(<CfdiPantalla direccion="emitidos" />);

    expect(screen.getByText("No hay CFDI con estos filtros")).toBeInTheDocument();
    expect(within(screen.getByRole("row", { name: /^Periodo/ })).queryByText(/\$/)).not.toBeInTheDocument();
  });

  it("limpiar los filtros conserva el periodo y el tipo", async () => {
    busqueda = "periodo=2026-09&tipo=E&q=zzz&metodo=PUE&estado=todos";
    preparar({ listado: listadoCon([], 0) });
    const user = userEvent.setup();
    render(<CfdiPantalla direccion="emitidos" />);

    await user.click(screen.getByRole("button", { name: "Limpiar filtros" }));

    expect(replaceMock).toHaveBeenCalledWith("/empresas/e1/cfdi/emitidos?periodo=2026-09&tipo=E", { scroll: false });
  });

  it("un error del listado no oculta la barra ni las pestañas", () => {
    preparar({ listado: consulta(undefined, { isError: true }) });

    render(<CfdiPantalla direccion="emitidos" />);

    expect(screen.getByRole("alert")).toHaveTextContent("No se pudieron cargar los CFDI.");
    expect(screen.getByRole("combobox", { name: "Periodo" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: /Ingreso/ })).toBeInTheDocument();
  });

  it("un error en los totales avisa sin tumbar el listado", () => {
    preparar({ res: consulta(undefined, { isError: true }) });

    render(<CfdiPantalla direccion="emitidos" />);

    expect(screen.getByRole("alert")).toHaveTextContent("No se pudieron cargar los totales.");
    expect(screen.getByText("05/09/2026")).toBeInTheDocument();
  });
});
