import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DeclaracionesPantalla } from "./DeclaracionesPantalla";
import { useComparativoDeclarado, useEliminarDeclaracion, useGuardarDeclaracion } from "@/hooks/useDeclaraciones";
import { ApiError } from "@/lib/api-client";
import { comparativo, declaracion, impuestoComparado } from "./fixtures";

vi.mock("next/navigation", () => ({
  useParams: () => ({ empresaId: "e1" }),
  useRouter: () => ({ replace: vi.fn() }),
  usePathname: () => "/empresas/e1/declaraciones",
  useSearchParams: () => new URLSearchParams("periodo=2026-09"),
}));
vi.mock("@/hooks/useDeclaraciones", () => ({ useComparativoDeclarado: vi.fn(), useGuardarDeclaracion: vi.fn(), useEliminarDeclaracion: vi.fn() }));
vi.mock("@/hooks/usePeriodos", () => ({ usePeriodos: () => ({ data: { periodos: ["2026-09"] } }) }));

const consulta = (data: unknown) => ({ data, isError: false, refetch: vi.fn() }) as never;
let guardar: ReturnType<typeof vi.fn>;
let eliminar: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  guardar = vi.fn().mockResolvedValue({});
  eliminar = vi.fn().mockResolvedValue(undefined);
  vi.mocked(useComparativoDeclarado).mockReturnValue(consulta(comparativo()));
  vi.mocked(useGuardarDeclaracion).mockReturnValue({ mutateAsync: guardar, isPending: false } as never);
  vi.mocked(useEliminarDeclaracion).mockReturnValue({ mutateAsync: eliminar, isPending: false } as never);
});

const iva = () => screen.getByRole("region", { name: "Comparativo de IVA" });
const isr = () => screen.getByRole("region", { name: "Comparativo de ISR" });

describe("DeclaracionesPantalla", () => {
  it("muestra por impuesto el estado, los renglones con su diferencia y el pendiente de pago", () => {
    render(<DeclaracionesPantalla />);

    expect(within(iva()).getByText("Con diferencias")).toBeInTheDocument();
    const fila = within(iva()).getByRole("row", { name: /IVA a cargo/ });
    expect(fila).toHaveTextContent("$150.00");
    expect(fila).toHaveTextContent("$160.00");
    expect(fila).toHaveTextContent("-$10.00");
    expect(within(iva()).getByText("Pendiente de pago: $50.00")).toBeInTheDocument();
    expect(within(isr()).getByText("Sin declaración capturada")).toBeInTheDocument();
    expect(screen.getByText(/En ISR se comparan las cifras del mes/)).toBeInTheDocument();
  });

  it("captura la declaración de ISR con importes opcionales y avisa que son cifras del mes", async () => {
    render(<DeclaracionesPantalla />);

    await userEvent.click(within(isr()).getByRole("button", { name: "Capturar declaración" }));
    const dialogo = screen.getByRole("dialog");
    expect(dialogo).toHaveTextContent("cifras del mes");
    expect(within(dialogo).queryByLabelText("Saldo a favor de periodos anteriores aplicado")).not.toBeInTheDocument();
    await userEvent.type(within(dialogo).getByLabelText("Ingresos acumulables del mes"), "1000");
    await userEvent.type(within(dialogo).getByLabelText("Monto pagado"), "90.50");
    await userEvent.click(within(dialogo).getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(guardar).toHaveBeenCalledTimes(1));
    const { impuesto, datos } = guardar.mock.calls[0][0];
    expect(impuesto).toBe("isr");
    expect(datos).toMatchObject({ tipo: "normal", ingresos: "1000", monto_pagado: "90.50", deducciones: null, impuesto_a_cargo: null });
  });

  it("bloquea importes inválidos y deja negativo solo el a cargo", async () => {
    render(<DeclaracionesPantalla />);

    await userEvent.click(within(iva()).getByRole("button", { name: "Corregir captura" }));
    const dialogo = screen.getByRole("dialog");
    const acreditable = within(dialogo).getByLabelText("IVA acreditable");
    await userEvent.type(acreditable, "-5");
    expect(within(dialogo).getByRole("button", { name: "Guardar" })).toBeDisabled();
    await userEvent.clear(acreditable);
    await userEvent.type(acreditable, "1.234");
    expect(within(dialogo).getByRole("button", { name: "Guardar" })).toBeDisabled();
    await userEvent.clear(acreditable);
    await userEvent.clear(within(dialogo).getByLabelText("IVA a cargo (+) o a favor (−)"));
    await userEvent.type(within(dialogo).getByLabelText("IVA a cargo (+) o a favor (−)"), "-50");
    expect(within(dialogo).getByRole("button", { name: "Guardar" })).toBeEnabled();
  });

  it("agrega una complementaria partiendo de la vigente", async () => {
    render(<DeclaracionesPantalla />);

    await userEvent.click(within(iva()).getByRole("button", { name: "Agregar complementaria" }));
    const dialogo = screen.getByRole("dialog");
    expect(dialogo).toHaveTextContent("Agregar complementaria de IVA");
    expect(within(dialogo).getByLabelText("IVA trasladado cobrado")).toHaveValue("160");
    await userEvent.click(within(dialogo).getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(guardar).toHaveBeenCalled());
    expect(guardar.mock.calls[0][0]).toMatchObject({ impuesto: "iva", datos: { tipo: "complementaria", impuesto_trasladado: "160" } });
  });

  it("con complementarias ya no ofrece corregir la normal y muestra el historial", () => {
    vi.mocked(useComparativoDeclarado).mockReturnValue(consulta(comparativo({
      iva: impuestoComparado({ declaraciones: 2, declaracion: declaracion({ secuencia: 2, tipo: "complementaria" }) }),
    })));
    render(<DeclaracionesPantalla />);

    expect(within(iva()).queryByRole("button", { name: "Corregir captura" })).not.toBeInTheDocument();
    expect(within(iva()).getByText(/Complementaria 1/)).toBeInTheDocument();
    expect(within(iva()).getByText(/2 declaraciones en el historial/)).toBeInTheDocument();
  });

  it("elimina la vigente", async () => {
    render(<DeclaracionesPantalla />);

    await userEvent.click(within(iva()).getByRole("button", { name: "Eliminar la declaración vigente de IVA" }));

    await waitFor(() => expect(eliminar).toHaveBeenCalledWith("iva"));
  });

  it("muestra el error del servidor al guardar (409) y mantiene el diálogo", async () => {
    guardar.mockRejectedValue(new ApiError(409, "Ya hay una complementaria"));
    render(<DeclaracionesPantalla />);

    await userEvent.click(within(iva()).getByRole("button", { name: "Corregir captura" }));
    await userEvent.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Guardar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Ya hay una complementaria");
    expect(screen.getByRole("dialog")).toBeInTheDocument();
  });

  it("muestra el error de carga", () => {
    vi.mocked(useComparativoDeclarado).mockReturnValue({ data: undefined, isError: true, refetch: vi.fn() } as never);
    render(<DeclaracionesPantalla />);

    expect(screen.getByText("No se pudo cargar el comparativo del periodo.")).toBeInTheDocument();
  });
});
