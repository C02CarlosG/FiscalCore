import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { InicioFinanciero } from "./InicioFinanciero";
import { useInicioIvaAnual, useInicioResumen } from "@/hooks/useInicio";
import { ivaAnual, resumen } from "./fixtures";

vi.mock("@/hooks/useInicio", () => ({ useInicioResumen: vi.fn(), useInicioIvaAnual: vi.fn() }));

const consulta = (data: unknown, extra: Record<string, unknown> = {}) =>
  ({ data, isLoading: false, isError: false, refetch: vi.fn(), ...extra }) as never;

function preparar(res: unknown = consulta(resumen()), iva: unknown = consulta(ivaAnual())) {
  vi.mocked(useInicioResumen).mockReturnValue(res as never);
  vi.mocked(useInicioIvaAnual).mockReturnValue(iva as never);
}

describe("InicioFinanciero", () => {
  beforeEach(() => {
    vi.mocked(useInicioResumen).mockReset();
    vi.mocked(useInicioIvaAnual).mockReset();
    preparar();
  });

  it("pide los datos de la empresa y del periodo", () => {
    render(<InicioFinanciero empresaId="e1" periodo="2026-09" />);

    expect(useInicioResumen).toHaveBeenCalledWith("e1", "2026-09");
    expect(useInicioIvaAnual).toHaveBeenCalledWith("e1", "2026-09");
  });

  it("muestra indicadores, gráfica, ingresos por mes e IVA del ejercicio", () => {
    render(<InicioFinanciero empresaId="e1" periodo="2026-09" />);

    expect(screen.getByText("Ingresos netos del periodo")).toBeInTheDocument();
    expect(screen.getByRole("img", { name: /últimos 12 meses/ })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "Ingresos por mes" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "IVA del ejercicio 2026" })).toBeInTheDocument();
    expect(screen.getByRole("table", { name: "IVA trasladado cobrado por mes" })).toBeInTheDocument();
  });

  it("mientras carga muestra un estado de carga por bloque", () => {
    preparar(consulta(undefined, { isLoading: true }), consulta(undefined, { isLoading: true }));

    render(<InicioFinanciero empresaId="e1" periodo="2026-09" />);

    expect(screen.getByRole("status", { name: "Cargando ingresos y gastos" })).toBeInTheDocument();
    expect(screen.getByRole("status", { name: "Cargando IVA del ejercicio" })).toBeInTheDocument();
  });

  it("un error en ingresos y gastos no tumba el IVA y permite reintentar", async () => {
    const refetch = vi.fn();
    preparar(consulta(undefined, { isError: true, refetch }));
    const user = userEvent.setup();
    render(<InicioFinanciero empresaId="e1" periodo="2026-09" />);

    const alerta = screen.getByRole("alert");
    expect(alerta).toHaveTextContent("No se pudieron cargar los ingresos y gastos.");
    await user.click(within(alerta).getByRole("button", { name: "Reintentar" }));
    expect(refetch).toHaveBeenCalled();
    expect(screen.getByRole("table", { name: "IVA trasladado cobrado por mes" })).toBeInTheDocument();
  });

  it("un error en el IVA no tumba los ingresos", () => {
    preparar(consulta(resumen()), consulta(undefined, { isError: true }));

    render(<InicioFinanciero empresaId="e1" periodo="2026-09" />);

    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar el IVA del ejercicio.");
    expect(screen.getByRole("table", { name: "Ingresos por mes" })).toBeInTheDocument();
  });

  it("una empresa sin CFDI avisa cómo cargarlos", () => {
    const vacio = { facturado: 0, notas_credito: 0, neto: 0, cfdi: 0 };
    const sinGastos = { ...vacio, nomina: 0 };
    const r = resumen({
      ingresos: { periodo: vacio, acumulado: vacio },
      gastos: { periodo: sinGastos, acumulado: sinGastos },
      meses: resumen().meses.map((m) => ({ ...m, ingresos: vacio, gastos: { neto: 0 } })),
    });
    preparar(consulta(r));

    render(<InicioFinanciero empresaId="e1" periodo="2026-09" />);

    expect(screen.getByText(/aún no tiene CFDI/)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Cargar CFDI" })).toHaveAttribute("href", "/empresas/e1/ingesta");
    expect(screen.getByRole("link", { name: "Conexión SAT" })).toHaveAttribute("href", "/empresas/e1/sat");
  });

  it("con CFDI solo en meses anteriores de la serie no muestra el aviso de vacío", () => {
    const r = resumen();
    r.ingresos.periodo = { facturado: 0, notas_credito: 0, neto: 0, cfdi: 0 };
    r.gastos.periodo = { ...r.gastos.periodo, facturado: 0, neto: 0, cfdi: 0, nomina: 0 };

    preparar(consulta(r));
    render(<InicioFinanciero empresaId="e1" periodo="2026-09" />);

    expect(screen.queryByText(/aún no tiene CFDI/)).not.toBeInTheDocument();
  });
});
