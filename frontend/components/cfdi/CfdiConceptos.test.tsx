import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CfdiConceptos } from "./CfdiConceptos";
import { useCfdiDetalle } from "@/hooks/useCfdis";
import type { CfdiColumna, CfdiConcepto } from "@/types/api";

vi.mock("@/hooks/useCfdis", () => ({ useCfdiDetalle: vi.fn() }));

const col = (clave: string, etiqueta: string, tipo_dato: CfdiColumna["tipo_dato"], visible = true): CfdiColumna => ({
  clave, etiqueta, tipo_dato, grupo: "concepto", visible_por_defecto: visible, ordenable: false, filtrable: false, opciones: [],
});

const columnas = [
  col("descripcion", "Descripción", "texto"),
  col("cantidad", "Cantidad", "numero"),
  col("importe", "Importe", "moneda"),
  col("iva_traslado_tasa", "Tasa o cuota IVA traslado", "numero"),
  col("no_identificacion", "No. identificación", "texto", false),
];

const concepto = (n: number, extra: Partial<CfdiConcepto> = {}): CfdiConcepto => ({
  linea: n, descripcion: `Concepto ${n}`, cantidad: 1.5, importe: 100 * n, iva_traslado_tasa: 0.16,
  no_identificacion: `SKU-${n}`, ...extra,
});

const consulta = (data: unknown, extra: Record<string, unknown> = {}) =>
  ({ data, isError: false, isLoading: false, refetch: vi.fn(), ...extra }) as never;

const detalle = (conceptos: CfdiConcepto[], total = conceptos.length) => consulta({ conceptos, total_conceptos: total });

describe("CfdiConceptos", () => {
  beforeEach(() => vi.mocked(useCfdiDetalle).mockReset());

  it("pide el detalle del CFDI y muestra solo las columnas visibles", () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(detalle([concepto(1)]));

    render(<CfdiConceptos empresaId="e1" uuid="U-1" columnas={columnas} />);

    expect(useCfdiDetalle).toHaveBeenCalledWith("e1", "U-1");
    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual([
      "Descripción", "Cantidad", "Importe", "Tasa o cuota IVA traslado",
    ]);
    expect(screen.getByText("Concepto 1")).toBeInTheDocument();
    expect(screen.getByText("$100.00")).toBeInTheDocument();
    expect(screen.getByText("1.5")).toBeInTheDocument();
    expect(screen.getByText("0.16")).toBeInTheDocument();
  });

  it("indica cuántos conceptos tiene", () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(detalle([concepto(1), concepto(2)]));

    render(<CfdiConceptos empresaId="e1" uuid="U-1" columnas={columnas} />);

    expect(screen.getByText("2 conceptos")).toBeInTheDocument();
  });

  it("pagina de 10 en 10 en el navegador", async () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(detalle(Array.from({ length: 23 }, (_, i) => concepto(i + 1))));
    const user = userEvent.setup();
    render(<CfdiConceptos empresaId="e1" uuid="U-1" columnas={columnas} />);

    expect(screen.getAllByRole("row")).toHaveLength(11); // encabezado + 10
    expect(screen.getByText("Página 1 de 3")).toBeInTheDocument();
    expect(screen.queryByText("Concepto 11")).not.toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getByText("Concepto 11")).toBeInTheDocument();
    expect(screen.getByText("Página 2 de 3")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    expect(screen.getAllByRole("row")).toHaveLength(4); // encabezado + 3
    expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
  });

  it("con diez o menos no muestra paginación", () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(detalle(Array.from({ length: 10 }, (_, i) => concepto(i + 1))));

    render(<CfdiConceptos empresaId="e1" uuid="U-1" columnas={columnas} />);

    expect(screen.queryByRole("button", { name: "Siguiente" })).not.toBeInTheDocument();
  });

  it("avisa cuando el servidor recortó la lista", () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(detalle([concepto(1)], 800));

    render(<CfdiConceptos empresaId="e1" uuid="U-1" columnas={columnas} />);

    expect(screen.getByText("800 conceptos · Se muestran los primeros 1")).toBeInTheDocument();
  });

  it("un CFDI sin conceptos guardados lo dice", () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(detalle([]));

    render(<CfdiConceptos empresaId="e1" uuid="U-1" columnas={columnas} />);

    expect(screen.getByText("Este CFDI no tiene conceptos guardados")).toBeInTheDocument();
  });

  it("muestra el estado de carga", () => {
    vi.mocked(useCfdiDetalle).mockReturnValue(consulta(undefined, { isLoading: true }));

    render(<CfdiConceptos empresaId="e1" uuid="U-1" columnas={columnas} />);

    expect(screen.getByRole("status", { name: "Cargando conceptos" })).toBeInTheDocument();
  });

  it("si falla permite reintentar", async () => {
    const refetch = vi.fn();
    vi.mocked(useCfdiDetalle).mockReturnValue(consulta(undefined, { isError: true, refetch }));
    const user = userEvent.setup();
    render(<CfdiConceptos empresaId="e1" uuid="U-1" columnas={columnas} />);

    expect(screen.getByRole("alert")).toHaveTextContent("No se pudieron cargar los conceptos.");
    await user.click(within(screen.getByRole("alert")).getByRole("button"));
    expect(refetch).toHaveBeenCalled();
  });
});
