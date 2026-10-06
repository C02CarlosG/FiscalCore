import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IsrFlujoPantalla } from "./IsrFlujoPantalla";
import {
  useGuardarAjusteIsr,
  useGuardarPorcentajeNomina,
  useIsrFlujoDetalle,
  useIsrFlujoResumen,
  useQuitarAjusteIsr,
} from "@/hooks/useIsrFlujo";
import { apiDescargar } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import { renglonIsr, resumenIsr } from "./fixtures";

vi.mock("next/navigation", () => ({
  useParams: () => ({ empresaId: "e1" }),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/empresas/e1/isr-flujo",
  useSearchParams: () => new URLSearchParams("periodo=2026-09"),
}));
vi.mock("@/hooks/useIsrFlujo", () => ({
  useIsrFlujoResumen: vi.fn(),
  useIsrFlujoDetalle: vi.fn(),
  useGuardarAjusteIsr: vi.fn(),
  useQuitarAjusteIsr: vi.fn(),
  useGuardarPorcentajeNomina: vi.fn(),
  POR_PAGINA_ISR: 50,
}));
vi.mock("@/hooks/usePeriodos", () => ({ usePeriodos: () => ({ data: { periodos: ["2026-09"] } }) }));
vi.mock("@/components/cfdi/CfdiVisor", () => ({
  CfdiVisor: ({ uuid }: { uuid: string | null }) => (uuid ? <div role="dialog" aria-label="Visor">{uuid}</div> : null),
}));
vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiDescargar: vi.fn() };
});
vi.mock("@/lib/descarga", () => ({ guardarArchivo: vi.fn() }));

const consulta = (data: unknown) => ({ data, isError: false, isFetching: false, refetch: vi.fn() }) as never;
let guardar: ReturnType<typeof vi.fn>;
let quitar: ReturnType<typeof vi.fn>;
let pct: ReturnType<typeof vi.fn>;

function preparar(resumen: unknown = consulta(resumenIsr()), items = [renglonIsr()]) {
  vi.mocked(useIsrFlujoResumen).mockReturnValue(resumen as never);
  vi.mocked(useIsrFlujoDetalle).mockReturnValue(consulta({ items, total: items.length, pagina: 1, por_pagina: 50 }));
  guardar = vi.fn().mockResolvedValue({});
  quitar = vi.fn().mockResolvedValue(undefined);
  pct = vi.fn().mockResolvedValue({});
  vi.mocked(useGuardarAjusteIsr).mockReturnValue({ mutateAsync: guardar, isPending: false } as never);
  vi.mocked(useQuitarAjusteIsr).mockReturnValue({ mutateAsync: quitar, isPending: false } as never);
  vi.mocked(useGuardarPorcentajeNomina).mockReturnValue({ mutateAsync: pct, isPending: false } as never);
}

describe("IsrFlujoPantalla", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    preparar();
  });

  it("muestra el resumen del mes con la utilidad fiscal estimada", () => {
    render(<IsrFlujoPantalla />);

    expect(screen.getByRole("table", { name: "Mes" })).toBeInTheDocument();
    expect(screen.getByText(/Utilidad fiscal estimada:/)).toHaveTextContent("$206.00");
  });

  it("cambia al acumulado y pide el detalle acumulado", async () => {
    render(<IsrFlujoPantalla />);

    await userEvent.click(screen.getByRole("button", { name: "Acumulado del ejercicio" }));

    expect(screen.getByRole("table", { name: "Acumulado del ejercicio" })).toBeInTheDocument();
    expect(screen.getByText(/Utilidad fiscal estimada:/)).toHaveTextContent("$999.00");
    expect(vi.mocked(useIsrFlujoDetalle).mock.calls.at(-1)).toEqual(["e1", "2026-09", "ingreso", "contado", true, 1]);
  });

  it("avisa cuando el régimen no usa el flujo y muestra los avisos del régimen", () => {
    preparar(consulta(resumenIsr({ regimen: { codigo: "601", modulo: "coeficiente", avisos: ["aviso X"] } })));
    render(<IsrFlujoPantalla />);

    expect(screen.getByRole("status")).toHaveTextContent("coeficiente de utilidad");
    expect(screen.getByText("aviso X")).toBeInTheDocument();
  });

  it("no considera un CFDI pidiendo el motivo", async () => {
    render(<IsrFlujoPantalla />);

    await userEvent.click(screen.getByRole("button", { name: /No considerar AAAAAAAA/ }));
    const guardarBtn = screen.getByRole("button", { name: "Guardar" });
    expect(guardarBtn).toBeDisabled();
    await userEvent.type(screen.getByLabelText("Motivo"), "duplicado");
    await userEvent.click(guardarBtn);

    await waitFor(() => expect(guardar).toHaveBeenCalledWith({ uuid: "AAAAAAAA-1111-2222-3333-444444444444", lado: "ingreso", motivo: "duplicado" }));
  });

  it("deshace un ajuste manual", async () => {
    preparar(consulta(resumenIsr()), [renglonIsr({ motivo: "manual" })]);
    render(<IsrFlujoPantalla />);

    await userEvent.click(screen.getByRole("button", { name: /Deshacer ajuste/ }));

    await waitFor(() => expect(quitar).toHaveBeenCalledWith({ uuid: "AAAAAAAA-1111-2222-3333-444444444444", lado: "ingreso" }));
  });

  it("guarda el porcentaje de nómina exenta", async () => {
    render(<IsrFlujoPantalla />);

    await userEvent.selectOptions(screen.getByLabelText("Nómina exenta deducible"), "0.53");

    await waitFor(() => expect(pct).toHaveBeenCalledWith(0.53));
  });

  it("exporta la cifra elegida a Excel", async () => {
    vi.mocked(apiDescargar).mockResolvedValue({} as never);
    render(<IsrFlujoPantalla />);

    await userEvent.click(screen.getByRole("button", { name: "Nómina" }));
    await userEvent.click(screen.getByRole("button", { name: "Exportar" }));

    await waitFor(() => expect(guardarArchivo).toHaveBeenCalled());
    expect(vi.mocked(apiDescargar).mock.calls[0][0]).toBe(
      "/api/v1/empresas/e1/isr-flujo/2026-09/exportar?lado=deduccion&bloque=nomina&acumulado=false",
    );
  });
});
