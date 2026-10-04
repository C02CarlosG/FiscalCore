import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { ValidacionesPanel } from "./ValidacionesPanel";
import type { ResumenValidaciones } from "./tipos";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

const BASE = "/api/v1/validaciones-cfdi/empresas/e1";

const tarjeta = (clave: string, titulo: string, periodo: number | null, acumulado: number | null, activa = true) =>
  ({ clave, titulo, descripcion: `Descripción de ${titulo}`, activa, periodo, acumulado }) as const;

const resumen: ResumenValidaciones = {
  periodo: "2026-03",
  configuracion: { inactivas: ["pue_con_rep"], umbral_efectivo: "2000.00" },
  emitidos: [
    tarjeta("pue_forma_99", "PUE con forma de pago 99", 1, 2),
    tarjeta("pue_con_rep", "PUE con complemento de pago", null, null, false),
    tarjeta("egreso_sin_relacion", "Egresos sin CFDI relacionado", 0, 3),
  ] as ResumenValidaciones["emitidos"],
  recibidos: [
    tarjeta("pue_forma_99", "PUE con forma de pago 99", 0, 0),
    tarjeta("pue_con_rep", "PUE con complemento de pago", null, null, false),
    tarjeta("egreso_sin_relacion", "Egresos sin CFDI relacionado", 0, 0),
    tarjeta("no_bancarizado", "Gastos no bancarizados", 4, 9),
  ] as ResumenValidaciones["recibidos"],
};

const lista = {
  total_filas: 2,
  cfdis: [
    {
      uuid: "AAAA0001-0000-4000-8000-000000000000", fecha_emision: "2026-03-10T12:00:00+00:00", serie: "A",
      folio: "15", rfc: "PRV010101AA1", nombre: "PROVEEDOR UNO", total: 2550, moneda: "USD",
      forma_pago: "01", metodo_pago: "PUE", tipo_comprobante: "I",
    },
  ],
};

function renderPanel() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <ValidacionesPanel empresaId="e1" periodo="2026-03" />
    </QueryClientProvider>,
  );
}

describe("ValidacionesPanel", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiFetch).mockImplementation(async (ruta: string, opciones?: RequestInit) => {
      if (ruta === `${BASE}?periodo=2026-03`) return resumen;
      if (ruta.startsWith(`${BASE}/cfdis?`)) return lista;
      if (ruta === `${BASE}/configuracion` && opciones?.method === "PUT") return JSON.parse(String(opciones.body));
      throw new Error(`llamada inesperada: ${ruta}`);
    });
  });

  it("muestra una tarjeta por validación con el periodo y el acumulado", async () => {
    renderPanel();
    const emitidos = await screen.findByRole("region", { name: "Emitidos" });
    const pue99 = within(emitidos).getByRole("button", { name: /PUE con forma de pago 99/ });
    expect(pue99).toHaveTextContent("1");
    expect(pue99).toHaveTextContent("Acumulado: 2");
    const recibidos = screen.getByRole("region", { name: "Recibidos" });
    expect(within(recibidos).getByRole("button", { name: /Gastos no bancarizados/ })).toHaveTextContent("Acumulado: 9");
  });

  it("una validación desactivada no se puede abrir", async () => {
    renderPanel();
    const emitidos = await screen.findByRole("region", { name: "Emitidos" });
    const rep = within(emitidos).getByRole("button", { name: /PUE con complemento de pago/ });
    expect(rep).toBeDisabled();
    expect(rep).toHaveTextContent("Desactivada");
  });

  it("el clic en una tarjeta abre la lista del periodo y permite ver el acumulado", async () => {
    const user = userEvent.setup();
    renderPanel();
    const recibidos = await screen.findByRole("region", { name: "Recibidos" });
    await user.click(within(recibidos).getByRole("button", { name: /Gastos no bancarizados/ }));

    const dialogo = await screen.findByRole("dialog");
    expect(await within(dialogo).findByText("PROVEEDOR UNO")).toBeInTheDocument();
    expect(within(dialogo).getByText("PRV010101AA1")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith(
      `${BASE}/cfdis?periodo=2026-03&direccion=recibidos&validacion=no_bancarizado&alcance=periodo`,
    );

    await user.click(within(dialogo).getByRole("button", { name: "Acumulado del ejercicio" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        `${BASE}/cfdis?periodo=2026-03&direccion=recibidos&validacion=no_bancarizado&alcance=acumulado`,
      ),
    );
  });

  it("la configuración guarda validaciones apagadas y el umbral", async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByRole("region", { name: "Emitidos" });
    await user.click(screen.getByRole("button", { name: "Configurar validaciones" }));

    const dialogo = await screen.findByRole("dialog");
    expect(within(dialogo).getByRole("checkbox", { name: "PUE con complemento de pago" })).not.toBeChecked();
    await user.click(within(dialogo).getByRole("checkbox", { name: "PUE con complemento de pago" }));
    await user.click(within(dialogo).getByRole("checkbox", { name: "Gastos no bancarizados" }));
    const umbral = within(dialogo).getByLabelText("Umbral de efectivo (pesos)");
    await user.clear(umbral);
    await user.type(umbral, "3000");
    await user.click(within(dialogo).getByRole("button", { name: "Guardar" }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(`${BASE}/configuracion`, {
        method: "PUT",
        body: JSON.stringify({ inactivas: ["no_bancarizado"], umbral_efectivo: "3000" }),
      }),
    );
  });

  it("no guarda un umbral inválido y muestra el error del backend", async () => {
    const user = userEvent.setup();
    renderPanel();
    await screen.findByRole("region", { name: "Emitidos" });
    await user.click(screen.getByRole("button", { name: "Configurar validaciones" }));
    const dialogo = await screen.findByRole("dialog");
    const umbral = within(dialogo).getByLabelText("Umbral de efectivo (pesos)");
    await user.clear(umbral);
    await user.type(umbral, "-5");
    await user.click(within(dialogo).getByRole("button", { name: "Guardar" }));
    expect(await within(dialogo).findByText("El umbral debe ser un importe de 0 o más")).toBeInTheDocument();

    vi.mocked(apiFetch).mockRejectedValueOnce(new ApiError(422, "umbral_efectivo fuera de rango"));
    await user.clear(umbral);
    await user.type(umbral, "5");
    await user.click(within(dialogo).getByRole("button", { name: "Guardar" }));
    expect(await within(dialogo).findByText("umbral_efectivo fuera de rango")).toBeInTheDocument();
  });
});
