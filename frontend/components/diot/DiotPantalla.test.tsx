import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DiotPantalla } from "./DiotPantalla";
import { useClasificarTerceroDiot, useDiotFlujo } from "@/hooks/useDiotFlujo";
import { apiDescargar, ApiError } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import { diotFlujo } from "./fixtures";

vi.mock("next/navigation", () => ({
  useParams: () => ({ empresaId: "e1" }),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/empresas/e1/diot",
  useSearchParams: () => new URLSearchParams("periodo=2026-09"),
}));
vi.mock("@/hooks/useDiotFlujo", () => ({ useDiotFlujo: vi.fn(), useClasificarTerceroDiot: vi.fn() }));
vi.mock("@/hooks/usePeriodos", () => ({ usePeriodos: () => ({ data: { periodos: ["2026-09"] } }) }));
vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiDescargar: vi.fn() };
});
vi.mock("@/lib/descarga", () => ({ guardarArchivo: vi.fn() }));

const consulta = (data: unknown, extra: Record<string, unknown> = {}) =>
  ({ data, isLoading: false, isError: false, refetch: vi.fn(), ...extra }) as never;

let guardar: ReturnType<typeof vi.fn>;

function preparar(diot: unknown = consulta(diotFlujo())) {
  vi.mocked(useDiotFlujo).mockReturnValue(diot as never);
  guardar = vi.fn().mockResolvedValue({});
  vi.mocked(useClasificarTerceroDiot).mockReturnValue({ mutateAsync: guardar, isPending: false } as never);
}

describe("DiotPantalla", () => {
  beforeEach(() => {
    vi.mocked(apiDescargar).mockReset();
    vi.mocked(guardarArchivo).mockReset();
    window.localStorage.clear();
    preparar();
  });

  it("titula la pantalla y muestra la tabla de terceros", () => {
    render(<DiotPantalla />);

    expect(screen.getByRole("heading", { level: 1 })).toHaveTextContent("DIOT por flujo");
    expect(screen.getByRole("table", { name: "DIOT del periodo por tercero" })).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("cargando muestra un esqueleto y con error ofrece reintentar", async () => {
    preparar(consulta(undefined, { isLoading: true }));
    const { unmount } = render(<DiotPantalla />);
    expect(screen.getByRole("status", { name: "Cargando DIOT" })).toBeInTheDocument();
    unmount();

    const refetch = vi.fn();
    preparar(consulta(undefined, { isError: true, refetch }));
    render(<DiotPantalla />);
    await userEvent.click(screen.getByRole("button", { name: /reintentar/i }));
    expect(refetch).toHaveBeenCalled();
  });

  it("avisa si la DIOT no cuadra con el IVA acreditable del resumen", () => {
    preparar(consulta(diotFlujo({ cuadre_con_iva: { iva_acreditable_diot: 224, iva_acreditable_resumen: 230, cuadra: false } })));
    render(<DiotPantalla />);

    expect(screen.getByRole("alert")).toHaveTextContent("$224.00");
    expect(screen.getByRole("alert")).toHaveTextContent("$230.00");
  });

  it("muestra los avisos del periodo", () => {
    preparar(consulta(diotFlujo({ advertencias: [{ codigo: "sin_region", mensaje: "Hay actos a tasa de 8 % sin región." }] })));
    render(<DiotPantalla />);

    expect(screen.getByRole("list", { name: "Advertencias de la DIOT" })).toHaveTextContent("sin región");
  });

  it("clasificar un tercero guarda y, si falla, muestra el motivo del servidor", async () => {
    render(<DiotPantalla />);
    await userEvent.selectOptions(screen.getByLabelText("Tipo de operación de PROVEEDOR UNO"), "07");
    expect(guardar).toHaveBeenCalledWith({ proveedorId: "p1", datos: { tipo_operacion: "07" } });

    guardar.mockRejectedValueOnce(new ApiError(422, "La operación 87 solo aplica al proveedor global (15)"));
    await userEvent.selectOptions(screen.getByLabelText("Tipo de operación de PROVEEDOR UNO"), "87");
    expect(await screen.findByRole("alert")).toHaveTextContent("La operación 87 solo aplica");
  });

  it("exporta el Excel del periodo", async () => {
    vi.mocked(apiDescargar).mockResolvedValue({ blob: new Blob(["x"]), nombre: "x.xlsx" } as never);
    render(<DiotPantalla />);

    await userEvent.click(screen.getByRole("button", { name: /Exportar Excel/ }));

    await waitFor(() => expect(guardarArchivo).toHaveBeenCalled());
    expect(apiDescargar).toHaveBeenCalledWith("/api/v1/empresas/e1/diot-flujo/2026-09/exportar");
    expect(vi.mocked(guardarArchivo).mock.calls[0][1]).toBe("diot_2026-09.xlsx");
  });

  it("si exportar falla lo dice", async () => {
    vi.mocked(apiDescargar).mockRejectedValue(new Error("boom"));
    render(<DiotPantalla />);

    await userEvent.click(screen.getByRole("button", { name: /Exportar Excel/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("No se pudo exportar el Excel.");
  });
});
