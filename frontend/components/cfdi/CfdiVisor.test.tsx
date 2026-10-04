import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CfdiVisor } from "./CfdiVisor";
import { useCfdiDetalle } from "@/hooks/useCfdis";
import { apiDescargar } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import type { CfdiDetalle } from "@/types/api";

vi.mock("@/hooks/useCfdis", () => ({ useCfdiDetalle: vi.fn() }));
vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiDescargar: vi.fn() };
});
vi.mock("@/lib/descarga", () => ({ guardarArchivo: vi.fn() }));

const UUID = "1F3A0001-0000-4000-8000-000000000000";

const detalle = (extra: Partial<CfdiDetalle> = {}): CfdiDetalle => ({
  encabezado: {
    uuid: UUID, version: "4.0", tipo_comprobante: "I", serie: "A", folio: "1",
    fecha_emision: "2026-03-10T09:30:00", fecha_timbrado: "2026-03-10T09:31:05", no_certificado: "30001000000500003416",
    lugar_expedicion: "68000", moneda: "MXN", tipo_cambio: 1, subtotal: 1000, descuento: 0,
    iva_trasladado: 160, iva_retenido: 0, isr_retenido: 0, total: 1160, saldo: 760,
    metodo_pago: "PPD", metodo_pago_desc: "PPD - Pago en parcialidades o diferido",
    forma_pago: "99", forma_pago_desc: "99 - Por definir", uso_cfdi: "G03",
    uso_cfdi_desc: "G03 - Gastos en general", estado: "vigente", estado_pago: "pagado_parcial",
  },
  emisor: { rfc: "EMI010101AAA", nombre: "EMISORA SA", regimen: "601", regimen_desc: "601 - General de Ley Personas Morales" },
  receptor: { rfc: "XAXX010101000", nombre: "CLIENTE", regimen: "612", regimen_desc: "612 - Personas Físicas con Actividades Empresariales", domicilio_fiscal: "68000" },
  impuestos: [{ ambito: "traslado", impuesto: "002", tipo_factor: "Tasa", tasa_o_cuota: 0.16, base: 1000, importe: 160 }],
  conceptos: [
    { linea: 1, clave_prod_serv: "84111506", cantidad: 1, clave_unidad: "E48", unidad: "Servicio", descripcion: "Servicio uno",
      valor_unitario: 600, importe: 600, descuento: 0, iva_traslado_importe: 96 },
  ],
  total_conceptos: 1,
  pagos: [{ uuid_pago: "REP-1", fecha_pago: "2026-03-20T12:00:00", parcialidad: 1, importe_pagado: 400, saldo_anterior: 1160, saldo_restante: 760 }],
  relacionados: [{ tipo_relacion: "04", descripcion: "04 - Sustitución de los CFDI previos", uuids: ["AAAAAAAA-0000-4000-8000-000000000000"] }],
  tiene_xml: true,
  ...extra,
});

const consulta = (data: unknown, extra: Record<string, unknown> = {}) =>
  ({ data, isError: false, isLoading: false, refetch: vi.fn(), ...extra }) as never;

function abrir(uuid: string | null = UUID, onCerrar = vi.fn()) {
  render(<CfdiVisor empresaId="e1" uuid={uuid} onCerrar={onCerrar} />);
  return onCerrar;
}

describe("CfdiVisor", () => {
  beforeEach(() => {
    vi.mocked(useCfdiDetalle).mockReset().mockReturnValue(consulta(detalle()));
    vi.mocked(apiDescargar).mockReset();
    vi.mocked(guardarArchivo).mockReset();
  });

  it("cerrado (sin uuid) no pinta nada ni pide el detalle", () => {
    abrir(null);

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(useCfdiDetalle).toHaveBeenCalledWith("e1", null);
  });

  it("titula con el tipo, el estado y la serie y folio", () => {
    abrir();

    const dialogo = screen.getByRole("dialog");
    expect(within(dialogo).getByRole("heading", { name: /Ingreso/ })).toHaveTextContent("A-1");
    expect(within(dialogo).getByText("Vigente")).toBeInTheDocument();
  });

  it("muestra emisor, receptor y datos fiscales con fechas dd/mm/aaaa", () => {
    abrir();

    expect(screen.getByText("EMISORA SA")).toBeInTheDocument();
    expect(screen.getByText("EMI010101AAA")).toBeInTheDocument();
    expect(screen.getByText("601 - General de Ley Personas Morales")).toBeInTheDocument();
    expect(screen.getByText("CLIENTE")).toBeInTheDocument();
    expect(screen.getByText(UUID)).toBeInTheDocument();
    expect(screen.getByText("10/03/2026 09:30")).toBeInTheDocument();
    expect(screen.getByText("10/03/2026 09:31")).toBeInTheDocument();
    expect(screen.getByText("30001000000500003416")).toBeInTheDocument();
    expect(screen.getByText("PPD - Pago en parcialidades o diferido")).toBeInTheDocument();
    expect(screen.getByText("99 - Por definir")).toBeInTheDocument();
    expect(screen.getByText("G03 - Gastos en general")).toBeInTheDocument();
  });

  it("lista los conceptos y los totales", () => {
    abrir();

    expect(screen.getByText("Servicio uno")).toBeInTheDocument();
    const totales = screen.getByRole("table", { name: "Totales" });
    expect(within(totales).getByText("$1,000.00")).toBeInTheDocument();
    expect(within(totales).getByText("$160.00")).toBeInTheDocument();
    expect(within(totales).getByText("$1,160.00")).toBeInTheDocument();
  });

  it("muestra pagos que lo liquidan y CFDI relacionados", () => {
    abrir();

    const pagos = screen.getByRole("table", { name: "Pagos aplicados" });
    expect(within(pagos).getByText("REP-1")).toBeInTheDocument();
    expect(within(pagos).getByText("20/03/2026 12:00")).toBeInTheDocument();
    expect(within(pagos).getByText("$400.00")).toBeInTheDocument();
    expect(screen.getByText("04 - Sustitución de los CFDI previos")).toBeInTheDocument();
    expect(screen.getByText("AAAAAAAA-0000-4000-8000-000000000000")).toBeInTheDocument();
  });

  it("sin pagos ni relacionados omite esas secciones", () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(consulta(detalle({ pagos: [], relacionados: [] })));

    abrir();

    expect(screen.queryByRole("table", { name: "Pagos aplicados" })).not.toBeInTheDocument();
    expect(screen.queryByText("CFDI relacionados")).not.toBeInTheDocument();
  });

  it("avisa si hay más conceptos de los que se muestran", () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(consulta(detalle({ total_conceptos: 800 })));

    abrir();

    expect(screen.getByText("Se muestran los primeros 1 de 800 conceptos")).toBeInTheDocument();
  });

  it("descarga el XML con el nombre del uuid", async () => {
    const blob = new Blob(["<x/>"]);
    vi.mocked(apiDescargar).mockResolvedValue(blob);
    const user = userEvent.setup();
    abrir();

    await user.click(screen.getByRole("button", { name: "Descargar XML" }));

    expect(apiDescargar).toHaveBeenCalledWith(`/api/v1/empresas/e1/cfdis/${UUID}/xml`);
    await waitFor(() => expect(guardarArchivo).toHaveBeenCalledWith(blob, `${UUID}.xml`));
  });

  it("si la descarga falla lo avisa y no guarda nada", async () => {
    vi.mocked(apiDescargar).mockRejectedValue(new Error("boom"));
    const user = userEvent.setup();
    abrir();

    await user.click(screen.getByRole("button", { name: "Descargar XML" }));

    expect(await screen.findByText("No se pudo descargar el XML.")).toBeInTheDocument();
    expect(guardarArchivo).not.toHaveBeenCalled();
  });

  it("sin XML guardado el botón de descarga está desactivado", () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(consulta(detalle({ tiene_xml: false })));

    abrir();

    expect(screen.getByRole("button", { name: "Descargar XML" })).toBeDisabled();
  });

  it("imprimir abre el diálogo de impresión del navegador", async () => {
    const imprimir = vi.spyOn(window, "print").mockImplementation(() => {});
    const user = userEvent.setup();
    abrir();

    await user.click(screen.getByRole("button", { name: "Imprimir" }));

    expect(imprimir).toHaveBeenCalledTimes(1);
  });

  it("cerrar avisa al padre", async () => {
    const user = userEvent.setup();
    const onCerrar = abrir();

    await user.click(screen.getByRole("button", { name: "Cerrar" }));

    expect(onCerrar).toHaveBeenCalled();
  });

  it("muestra la carga y el error con reintento", async () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(consulta(undefined, { isLoading: true }));
    const { unmount } = render(<CfdiVisor empresaId="e1" uuid={UUID} onCerrar={vi.fn()} />);
    expect(screen.getByRole("status", { name: "Cargando CFDI" })).toBeInTheDocument();
    unmount();

    const refetch = vi.fn();
    vi.mocked(useCfdiDetalle).mockReturnValue(consulta(undefined, { isError: true, refetch }));
    render(<CfdiVisor empresaId="e1" uuid={UUID} onCerrar={vi.fn()} />);
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar el CFDI.");
    await userEvent.setup().click(within(screen.getByRole("alert")).getByRole("button", { name: "Reintentar" }));
    expect(refetch).toHaveBeenCalled();
  });
});
