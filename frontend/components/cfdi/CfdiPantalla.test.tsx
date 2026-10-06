import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CfdiPantalla } from "./CfdiPantalla";
import { useCfdiColumnas, useCfdiDetalle, useCfdiListado, useCfdiResumen } from "@/hooks/useCfdis";
import { periodoRecordado } from "@/lib/periodo";
import type { CfdiCifra, CfdiColumna, CfdiResumenResponse, CfdiTotalesBloque } from "@/types/api";

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
  useCfdiDetalle: vi.fn(),
  useCfdiListado: vi.fn(),
  useCfdiResumen: vi.fn(),
}));

vi.mock("@/hooks/useNotasCfdi", () => ({
  useEtiquetas: () => ({ data: [] }),
  useEtiquetarLote: () => ({ mutate: vi.fn(), isPending: false, isError: false, isSuccess: false }),
  useCrearEtiqueta: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));
vi.mock("@/components/cfdi/CfdiNotas", () => ({ CfdiNotas: () => null }));

const preferencias: Record<string, unknown> = {};
const guardarMutate = vi.fn();
const restablecerMutate = vi.fn();
const exportarMutate = vi.fn();
vi.mock("@/hooks/usePreferenciaTabla", () => ({
  usePreferenciaTabla: (vista: string) => ({ data: preferencias[vista] ?? null }),
  useGuardarPreferenciaTabla: (vista: string) => ({ mutate: (...a: unknown[]) => guardarMutate(vista, ...a), isPending: false, isError: false }),
  useRestablecerPreferenciaTabla: (vista: string) => ({ mutate: (...a: unknown[]) => restablecerMutate(vista, ...a), isPending: false, isError: false }),
}));
let exportarEstado: Record<string, unknown> = {};
vi.mock("@/hooks/useExportarCfdi", () => ({
  useExportarCfdi: () => ({ mutate: exportarMutate, isPending: false, isError: false, ...exportarEstado }),
}));

vi.mock("@/hooks/usePeriodos", () => ({
  usePeriodos: () => ({ data: { periodos: ["2026-09", "2026-08"] } }),
}));

const col = (clave: string, etiqueta: string, tipo_dato: CfdiColumna["tipo_dato"]): CfdiColumna => ({
  clave, etiqueta, tipo_dato, grupo: "encabezado", visible_por_defecto: true, ordenable: true, filtrable: true, opciones: [],
});

const catalogo = {
  encabezado: [col("fecha_emision", "Fecha de expedición", "fecha"), col("total", "Total", "moneda"), col("serie", "Serie", "texto")],
  concepto: [{ ...col("descripcion", "Descripción", "texto"), grupo: "concepto" as const }],
};

const cifras: CfdiCifra[] = [
  ["conteo", "CFDI", "entero"], ["retencion_iva", "Ret. IVA", "moneda"], ["retencion_ieps", "Ret. IEPS", "moneda"],
  ["retencion_isr", "Ret. ISR", "moneda"], ["traslado_iva", "Tras. IVA", "moneda"], ["traslado_ieps", "Tras. IEPS", "moneda"],
  ["traslado_isr", "Tras. ISR", "moneda"], ["total_retenciones", "Total ret.", "moneda"], ["subtotal", "Subtotal", "moneda"],
  ["descuento", "Descuento", "moneda"], ["neto", "Neto", "moneda"], ["total", "Total", "moneda"],
].map(([clave, etiqueta, formato]) => ({ clave, etiqueta, formato }) as CfdiCifra);

const bloque = (conteo: number, total: number | null): CfdiTotalesBloque => ({
  conteo, retencion_iva: null, retencion_ieps: null, retencion_isr: null, traslado_iva: null, traslado_ieps: null,
  traslado_isr: null, total_retenciones: null, subtotal: null, descuento: null, neto: null, total,
});

const resumen = (extra: Partial<CfdiResumenResponse> = {}): CfdiResumenResponse => ({
  conteos: { I: 507, E: 12, T: 0, N: 33, P: 80 },
  cifras,
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
  vi.mocked(useCfdiDetalle).mockReturnValue(consulta(undefined, { isLoading: true }));
}

describe("CfdiPantalla", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    window.localStorage.clear();
    busqueda = "periodo=2026-09";
    ruta = "/empresas/e1/cfdi/emitidos";
    for (const k of Object.keys(preferencias)) delete preferencias[k];
    guardarMutate.mockClear();
    restablecerMutate.mockClear();
    exportarMutate.mockClear();
    exportarEstado = {};
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

  describe("columnas, filtro avanzado y exportación (F3.4)", () => {
    it("aplica el orden y la visibilidad guardados por el usuario", () => {
      preferencias["cfdi-emitidos-I"] = [
        { clave: "total", visible: true }, { clave: "fecha_emision", visible: false }, { clave: "serie", visible: true },
      ];
      render(<CfdiPantalla direccion="emitidos" />);

      const cabeceras = screen.getAllByRole("columnheader").map((c) => c.textContent).filter((t) => t);
      expect(cabeceras.slice(-2)).toEqual(["Total", "Serie"]);
      expect(screen.queryByRole("columnheader", { name: /Fecha de expedición/ })).not.toBeInTheDocument();
    });

    it("guarda por usuario y por pestaña desde el editor de columnas", async () => {
      busqueda = "periodo=2026-09&tipo=E";
      const user = userEvent.setup();
      render(<CfdiPantalla direccion="recibidos" />);

      await user.click(screen.getByRole("button", { name: "Columnas" }));
      const dialogo = screen.getByRole("dialog", { name: "Columnas del listado" });
      await user.click(within(dialogo).getByRole("button", { name: "Subir Total" }));
      await user.click(within(dialogo).getByLabelText("Serie"));   // ocultar
      await user.click(within(dialogo).getByRole("button", { name: "Guardar" }));

      expect(guardarMutate).toHaveBeenCalledWith(
        "cfdi-recibidos-E",
        [{ clave: "total", visible: true }, { clave: "fecha_emision", visible: true }, { clave: "serie", visible: false }],
        expect.anything(),
      );
    });

    it("restablecer vuelve al catálogo", async () => {
      const user = userEvent.setup();
      render(<CfdiPantalla direccion="emitidos" />);

      await user.click(screen.getByRole("button", { name: "Columnas" }));
      await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Restablecer" }));

      expect(restablecerMutate).toHaveBeenCalledWith("cfdi-emitidos-I", undefined, expect.anything());
    });

    it("las columnas de totales tienen su propia preferencia", async () => {
      preferencias["cfdi-emitidos-I-totales"] = [{ clave: "total", visible: true }, { clave: "neto", visible: false }];
      const user = userEvent.setup();
      render(<CfdiPantalla direccion="emitidos" />);

      expect(screen.queryByRole("columnheader", { name: "Neto" })).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Columnas de totales" }));
      await user.click(within(screen.getByRole("dialog", { name: "Columnas de totales" })).getByRole("button", { name: "Guardar" }));

      expect(guardarMutate).toHaveBeenCalledWith("cfdi-emitidos-I-totales", expect.any(Array), expect.anything());
    });

    it("aplicar el filtro avanzado lo escribe en la URL y el botón cuenta los activos", async () => {
      const user = userEvent.setup();
      const { unmount } = render(<CfdiPantalla direccion="emitidos" />);

      await user.click(screen.getByRole("button", { name: "Filtro avanzado" }));
      const dialogo = screen.getByRole("dialog", { name: "Filtro avanzado" });
      await user.click(within(dialogo).getByRole("button", { name: "Agregar filtro" }));
      await user.selectOptions(within(dialogo).getByLabelText("Campo"), "total");
      await user.selectOptions(within(dialogo).getByLabelText("Operador"), "mayor");
      expect(within(dialogo).getByRole("button", { name: "Aplicar" })).toBeDisabled();   // falta el valor
      await user.type(within(dialogo).getByLabelText("Valor de Total"), "1000");
      await user.click(within(dialogo).getByRole("button", { name: "Aplicar" }));

      const filtros = JSON.stringify([{ campo: "total", op: "mayor", valor: 1000 }]);
      expect(replaceMock).toHaveBeenCalledWith(
        `/empresas/e1/cfdi/emitidos?periodo=2026-09&filtros=${encodeURIComponent(filtros)}`,
        { scroll: false },
      );
      unmount();

      busqueda = `periodo=2026-09&filtros=${encodeURIComponent(filtros)}`;
      render(<CfdiPantalla direccion="emitidos" />);
      expect(screen.getByLabelText("1 filtros activos")).toBeInTheDocument();
    });

    it("exporta lo filtrado con las columnas visibles en su orden", async () => {
      preferencias["cfdi-emitidos-I"] = [
        { clave: "total", visible: true }, { clave: "fecha_emision", visible: false }, { clave: "serie", visible: true },
      ];
      busqueda = "periodo=2026-09&q=abc";
      const user = userEvent.setup();
      render(<CfdiPantalla direccion="emitidos" />);

      await user.click(screen.getByRole("button", { name: "Exportar a Excel" }));

      expect(exportarMutate).toHaveBeenCalledWith({
        estado: expect.objectContaining({ periodo: "2026-09", q: "abc", tipo: "I" }),
        columnas: ["total", "serie"],
      });
    });

    it("muestra el error de la exportación con su motivo", () => {
      exportarEstado = { isError: true, error: new Error("El resultado tiene 60,000 CFDI y el máximo es 50,000") };
      render(<CfdiPantalla direccion="emitidos" />);
      expect(screen.getByRole("alert")).toHaveTextContent("60,000 CFDI");
    });
  });

  describe("conceptos y visor", () => {
    it("desplegar una fila pide el detalle de su CFDI", async () => {
      const user = userEvent.setup();
      render(<CfdiPantalla direccion="emitidos" />);
      expect(useCfdiDetalle).not.toHaveBeenCalledWith("e1", "U1");

      await user.click(screen.getByRole("button", { name: "Ver conceptos" }));

      expect(useCfdiDetalle).toHaveBeenCalledWith("e1", "U1");
    });

    it("el botón del visor abre la ventana del CFDI y cerrarla la quita", async () => {
      const user = userEvent.setup();
      render(<CfdiPantalla direccion="emitidos" />);
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "Abrir visor del CFDI" }));

      expect(screen.getByRole("dialog")).toBeInTheDocument();
      expect(useCfdiDetalle).toHaveBeenCalledWith("e1", "U1");

      await user.click(screen.getByRole("button", { name: "Cerrar" }));
      expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    });
  });

  describe("Nómina y Pago (F3.5b)", () => {
    const cifrasNomina: CfdiCifra[] = [
      ["conteo", "CFDI", "entero"], ["empleados", "Empleados", "entero"], ["sueldos", "Sueldos", "moneda"],
    ].map(([clave, etiqueta, formato]) => ({ clave, etiqueta, formato }) as CfdiCifra);

    it("la pestaña de Nómina muestra las cifras que manda el servidor y su editor de totales las lista", async () => {
      busqueda = "periodo=2026-09&tipo=N";
      preparar({ res: consulta(resumen({
        cifras: cifrasNomina,
        totales: { periodo: { conteo: 33, empleados: 31, sueldos: 250000 }, acumulado: { conteo: 90, empleados: 40, sueldos: 900000 } },
      })) });
      const user = userEvent.setup();
      render(<CfdiPantalla direccion="emitidos" />);

      expect(within(screen.getByRole("row", { name: /^Periodo/ })).getByText("31")).toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: "Empleados" })).toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "Columnas de totales" }));
      const dialogo = screen.getByRole("dialog", { name: "Columnas de totales" });
      expect(within(dialogo).getByLabelText("Sueldos")).toBeInTheDocument();
      expect(within(dialogo).queryByLabelText("Ret. IVA")).not.toBeInTheDocument();     // las de comprobante no aplican
      expect(within(dialogo).queryByLabelText("CFDI")).not.toBeInTheDocument();         // el conteo siempre va primero
    });

    it("la preferencia de totales es de cada pestaña", () => {
      busqueda = "periodo=2026-09&tipo=N";
      preferencias["cfdi-emitidos-N-totales"] = [{ clave: "sueldos", visible: false }];
      preparar({ res: consulta(resumen({
        cifras: cifrasNomina,
        totales: { periodo: { conteo: 1, empleados: 1, sueldos: 5 }, acumulado: { conteo: 1, empleados: 1, sueldos: 5 } },
      })) });
      render(<CfdiPantalla direccion="emitidos" />);

      expect(screen.queryByRole("columnheader", { name: "Sueldos" })).not.toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: "Empleados" })).toBeInTheDocument();
    });

    it("la pestaña de Pago avisa que los REP 1.0 no traen bases de IVA", () => {
      busqueda = "periodo=2026-09&tipo=P";
      render(<CfdiPantalla direccion="emitidos" />);
      expect(screen.getByText(/complemento de pago versión 2\.0/)).toBeInTheDocument();
    });

    it("las demás pestañas no muestran ese aviso", () => {
      render(<CfdiPantalla direccion="emitidos" />);
      expect(screen.queryByText(/complemento de pago versión 2\.0/)).not.toBeInTheDocument();
    });
  });
});
