import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IvaFlujoPantalla } from "./IvaFlujoPantalla";
import { useGuardarAjusteIva, useIvaFlujoDetalle, useIvaFlujoResumen, useQuitarAjusteIva } from "@/hooks/useIvaFlujo";
import { apiDescargar, ApiError } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import { renglon, resumenIva } from "./fixtures";

const replaceMock = vi.fn();
let busqueda = "periodo=2026-09";
vi.mock("next/navigation", () => ({
  useParams: () => ({ empresaId: "e1" }),
  useRouter: () => ({ replace: replaceMock }),
  usePathname: () => "/empresas/e1/iva-flujo",
  useSearchParams: () => new URLSearchParams(busqueda),
}));

vi.mock("@/hooks/useIvaFlujo", () => ({
  useIvaFlujoResumen: vi.fn(),
  useIvaFlujoDetalle: vi.fn(),
  useGuardarAjusteIva: vi.fn(),
  useQuitarAjusteIva: vi.fn(),
  POR_PAGINA_IVA: 50,
}));
vi.mock("@/hooks/usePeriodos", () => ({ usePeriodos: () => ({ data: { periodos: ["2026-09", "2026-08"] } }) }));
vi.mock("@/components/cfdi/CfdiVisor", () => ({
  CfdiVisor: ({ uuid }: { uuid: string | null }) => (uuid ? <div role="dialog" aria-label="Visor">{uuid}</div> : null),
}));
vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiDescargar: vi.fn() };
});
vi.mock("@/lib/descarga", () => ({ guardarArchivo: vi.fn() }));

const consulta = (data: unknown, extra: Record<string, unknown> = {}) =>
  ({ data, isLoading: false, isError: false, refetch: vi.fn(), ...extra }) as never;
const detalleCon = (items = [renglon()], total = items.length) => consulta({ items, total, pagina: 1, por_pagina: 50 });

let guardar: ReturnType<typeof vi.fn>;
let quitar: ReturnType<typeof vi.fn>;

function preparar(resumen: unknown = consulta(resumenIva()), detalle: unknown = detalleCon()) {
  vi.mocked(useIvaFlujoResumen).mockReturnValue(resumen as never);
  vi.mocked(useIvaFlujoDetalle).mockReturnValue(detalle as never);
  guardar = vi.fn().mockResolvedValue({});
  quitar = vi.fn().mockResolvedValue(undefined);
  vi.mocked(useGuardarAjusteIva).mockReturnValue({ mutateAsync: guardar, isPending: false } as never);
  vi.mocked(useQuitarAjusteIva).mockReturnValue({ mutateAsync: quitar, isPending: false } as never);
}

describe("IvaFlujoPantalla", () => {
  beforeEach(() => {
    replaceMock.mockClear();
    vi.mocked(apiDescargar).mockReset();
    vi.mocked(guardarArchivo).mockReset();
    window.localStorage.clear();
    busqueda = "periodo=2026-09";
    preparar();
  });

  it("titula la pantalla, ofrece el periodo global y muestra las tres tarjetas", () => {
    render(<IvaFlujoPantalla />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("IVA base flujo");
    expect(screen.getByRole("combobox", { name: "Periodo" })).toHaveTextContent("2026 - Septiembre");
    expect(screen.getByRole("tab", { name: /Trasladado/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Acreditable/ })).toBeInTheDocument();
  });

  it("pide el resumen y el detalle del estado de la URL", () => {
    busqueda = "periodo=2026-09&vista=acreditable&origen=credito&pagina=2";

    render(<IvaFlujoPantalla />);

    expect(useIvaFlujoResumen).toHaveBeenCalledWith("e1", "2026-09");
    expect(useIvaFlujoDetalle).toHaveBeenCalledWith("e1", "2026-09", "acreditable", "credito", 2);
  });

  it("cambiar de vista u origen lo escribe en la URL", async () => {
    const user = userEvent.setup();
    render(<IvaFlujoPantalla />);

    await user.click(screen.getByRole("tab", { name: /Acreditable/ }));
    expect(replaceMock).toHaveBeenLastCalledWith("/empresas/e1/iva-flujo?periodo=2026-09&vista=acreditable", { scroll: false });

    await user.click(screen.getByRole("button", { name: /Cobro de facturas de crédito/ }));
    expect(replaceMock).toHaveBeenLastCalledWith("/empresas/e1/iva-flujo?periodo=2026-09&origen=credito", { scroll: false });
  });

  it("la vista A cargo muestra la resta del mes y no consulta detalle", () => {
    busqueda = "periodo=2026-09&vista=a-cargo";

    render(<IvaFlujoPantalla />);

    expect(screen.getByRole("table", { name: "Resultado del IVA del mes" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Exportar" })).not.toBeInTheDocument();
    expect(useIvaFlujoDetalle).toHaveBeenCalledWith("e1", "2026-09", null, "contado", 1);
  });

  it("muestra las advertencias del servidor", () => {
    render(<IvaFlujoPantalla />);

    const lista = screen.getByRole("list", { name: "Advertencias del IVA" });
    expect(within(lista).getByText(/versión 1\.0/)).toBeInTheDocument();
    expect(within(lista).getByText("2 CFDI")).toBeInTheDocument();
  });

  it("el UUID de un renglón abre el visor del CFDI", async () => {
    const user = userEvent.setup();
    render(<IvaFlujoPantalla />);

    await user.click(screen.getByRole("button", { name: /Ver CFDI 1F3A0001/ }));

    expect(screen.getByRole("dialog", { name: "Visor" })).toHaveTextContent("1F3A0001-0000-4000-8000-000000000000");
  });

  it("no considerar guarda el ajuste con su motivo y cierra la ventana", async () => {
    const user = userEvent.setup();
    render(<IvaFlujoPantalla />);

    await user.click(screen.getByRole("button", { name: /No considerar 1F3A0001/ }));
    await user.type(screen.getByLabelText("Motivo"), "factura duplicada");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(guardar).toHaveBeenCalledWith({
      uuid: "1F3A0001-0000-4000-8000-000000000000", direccion: "trasladado", accion: "excluir", motivo: "factura duplicada",
    });
    await waitFor(() => expect(screen.queryByRole("dialog", { name: "No considerar CFDI" })).not.toBeInTheDocument());
  });

  it("reasignar manda el periodo destino", async () => {
    const user = userEvent.setup();
    render(<IvaFlujoPantalla />);

    await user.click(screen.getByRole("button", { name: /Reasignar periodo 1F3A0001/ }));
    await user.type(screen.getByLabelText("Motivo"), "se cobró en octubre");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(guardar).toHaveBeenCalledWith(expect.objectContaining({ accion: "reasignar", periodo_destino: "2026-10" }));
  });

  it("si el servidor rechaza el ajuste deja la ventana abierta con su mensaje", async () => {
    guardar.mockRejectedValue(new ApiError(422, "el periodo destino es el mismo de la emisión"));
    const user = userEvent.setup();
    render(<IvaFlujoPantalla />);

    await user.click(screen.getByRole("button", { name: /Reasignar periodo/ }));
    await user.type(screen.getByLabelText("Motivo"), "x");
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByText("el periodo destino es el mismo de la emisión")).toBeInTheDocument();
    expect(screen.getByRole("dialog", { name: "Reasignar periodo" })).toBeInTheDocument();
  });

  it("deshacer un ajuste lo quita", async () => {
    const ajuste = { accion: "excluir" as const, periodo_destino: null, motivo: "x" };
    preparar(consulta(resumenIva()), detalleCon([renglon({ motivo: "manual", ajuste })]));
    busqueda = "periodo=2026-09&origen=no_considerados";
    const user = userEvent.setup();
    render(<IvaFlujoPantalla />);

    await user.click(screen.getByRole("button", { name: /Deshacer ajuste/ }));

    expect(quitar).toHaveBeenCalledWith({ uuid: "1F3A0001-0000-4000-8000-000000000000", direccion: "trasladado" });
  });

  it("exportar descarga el Excel de la tarjeta con su nombre", async () => {
    const blob = new Blob(["x"]);
    vi.mocked(apiDescargar).mockResolvedValue(blob);
    const user = userEvent.setup();
    render(<IvaFlujoPantalla />);

    await user.click(screen.getByRole("button", { name: "Exportar" }));

    expect(apiDescargar).toHaveBeenCalledWith(
      "/api/v1/empresas/e1/iva-flujo/2026-09/exportar?direccion=trasladado&origen=contado",
    );
    await waitFor(() => expect(guardarArchivo).toHaveBeenCalledWith(blob, "iva_trasladado_contado_2026-09.xlsx"));
  });

  it("si exportar falla lo avisa con el motivo del servidor", async () => {
    vi.mocked(apiDescargar).mockRejectedValue(new ApiError(422, "son 60000 renglones; el máximo es 50000"));
    const user = userEvent.setup();
    render(<IvaFlujoPantalla />);

    await user.click(screen.getByRole("button", { name: "Exportar" }));

    expect(await screen.findByText("son 60000 renglones; el máximo es 50000")).toBeInTheDocument();
    expect(guardarArchivo).not.toHaveBeenCalled();
  });

  it("muestra la carga y el error del resumen con reintento", async () => {
    preparar(consulta(undefined, { isLoading: true }));
    const { unmount } = render(<IvaFlujoPantalla />);
    expect(screen.getByRole("status", { name: "Cargando IVA" })).toBeInTheDocument();
    unmount();

    const refetch = vi.fn();
    preparar(consulta(undefined, { isError: true, refetch }));
    render(<IvaFlujoPantalla />);
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar el IVA del periodo.");
    await userEvent.setup().click(within(screen.getByRole("alert")).getByRole("button", { name: "Reintentar" }));
    expect(refetch).toHaveBeenCalled();
  });
});
