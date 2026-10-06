import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { MiSuscripcion } from "./MiSuscripcion";
import { AdminSuscripciones } from "./AdminSuscripciones";
import type { MiSuscripcionDatos, Plan } from "./tipos";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

const planes: Plan[] = [
  { clave: "prueba", nombre: "Prueba", precio_mensual: "0.00", max_rfc: 1, activo: true, por_defecto: true },
  { clave: "despacho", nombre: "Despacho", precio_mensual: "1499.00", max_rfc: 15, activo: true, por_defecto: false },
  { clave: "ilimitado", nombre: "Ilimitado", precio_mensual: "3999.00", max_rfc: null, activo: true, por_defecto: false },
];

const mia = (cambios: Partial<MiSuscripcionDatos> = {}): MiSuscripcionDatos => ({
  plan: planes[1], estado: "activa", vigente_hasta: "2026-12-31", motivo: null, uso_rfc: 2,
  puede_agregar_rfc: true, es_admin_plataforma: false, ...cambios,
});

function renderCon(ui: React.ReactElement, datos: MiSuscripcionDatos = mia()) {
  vi.mocked(apiFetch).mockImplementation(async (ruta: string, opciones?: RequestInit) => {
    if (ruta === "/api/v1/suscripcion") return datos;
    if (ruta === "/api/v1/suscripcion/planes") return planes;
    if (ruta === "/api/v1/suscripcion/historial") {
      return [{ fecha: "2026-10-01T12:00:00+00:00", plan_clave: "basico", plan_nombre: "Básico", estado: "activa",
                vigente_hasta: null }];
    }
    if (ruta === "/api/v1/suscripcion/admin/cuentas/u9/historial") {
      return [{ fecha: "2026-10-01T12:00:00+00:00", plan_clave: "basico", plan_nombre: "Básico", estado: "suspendida",
                vigente_hasta: "2026-12-31", notas: "pago SPEI", asignada_por: "admin@despacho.mx" }];
    }
    if (ruta.startsWith("/api/v1/suscripcion/admin/cuentas?")) {
      return [{ usuario_id: "u9", email: "ana@despacho.mx", nombre: "Ana", es_admin_plataforma: false,
                plan_clave: null, estado: null, vigente_hasta: null, notas: null, uso_rfc: 1 }];
    }
    if (opciones?.method === "PUT") return {};
    throw new Error(`llamada inesperada: ${ruta}`);
  });
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>);
}

describe("MiSuscripcion", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("muestra plan, precio más IVA, vigencia y uso", async () => {
    renderCon(<MiSuscripcion />);
    expect(await screen.findByRole("heading", { name: "Despacho" })).toBeInTheDocument();
    expect(screen.getByText(/\$1,499\.00 al mes más IVA/)).toBeInTheDocument();
    expect(screen.getByText("Vigente hasta 31/12/2026")).toBeInTheDocument();
    expect(screen.getByText("2 de 15 RFC")).toBeInTheDocument();
    expect(screen.getByRole("progressbar", { name: "RFC usados" })).toHaveAttribute("aria-valuenow", "2");
  });

  it("avisa al llegar al límite y explica por qué aplica el plan por defecto", async () => {
    renderCon(<MiSuscripcion />, mia({ plan: planes[0], motivo: "vencida", uso_rfc: 1, puede_agregar_rfc: false, estado: "activa" }));
    expect(await screen.findByText(/Ya usaste todos los RFC de tu plan/)).toBeInTheDocument();
    expect(screen.getByText(/Tu suscripción venció/)).toBeInTheDocument();
  });

  it("plan ilimitado y catálogo de planes", async () => {
    renderCon(<MiSuscripcion />, mia({ plan: planes[2], uso_rfc: 30 }));
    expect(await screen.findByText("30 RFC · sin límite")).toBeInTheDocument();
    const catalogo = screen.getByRole("table", { name: "Planes disponibles" });
    expect(within(catalogo).getByText("Prueba")).toBeInTheDocument();
    expect(within(catalogo).getByText("Sin límite")).toBeInTheDocument();
  });
});

describe("AdminSuscripciones", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("muestra el historial de mi plan sin notas internas", async () => {
    renderCon(<MiSuscripcion />);
    const tabla = await screen.findByRole("table", { name: "Historial de plan" });
    expect(within(tabla).getByText("Básico")).toBeInTheDocument();
    expect(within(tabla).getByText("Sin vencimiento")).toBeInTheDocument();
    expect(within(tabla).queryByText("Notas")).not.toBeInTheDocument();
  });

  it("el administrador abre el historial completo de una cuenta", async () => {
    const user = userEvent.setup();
    renderCon(<AdminSuscripciones />, mia({ es_admin_plataforma: true }));
    await user.click(await screen.findByRole("button", { name: "Historial de ana@despacho.mx" }));
    const tabla = await screen.findByRole("table", { name: "Historial de plan" });
    expect(within(tabla).getByText("pago SPEI")).toBeInTheDocument();
    expect(within(tabla).getByText("admin@despacho.mx")).toBeInTheDocument();
    expect(within(tabla).getByText("Suspendida")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith("/api/v1/suscripcion/admin/cuentas/u9/historial");
  });

  it("asigna un plan a una cuenta", async () => {
    const user = userEvent.setup();
    renderCon(<AdminSuscripciones />);
    const fila = (await screen.findByText("ana@despacho.mx")).closest("tr") as HTMLElement;
    await user.selectOptions(within(fila).getByRole("combobox", { name: "Plan de ana@despacho.mx" }), "despacho");
    await user.type(within(fila).getByLabelText("Vigente hasta para ana@despacho.mx"), "2026-12-31");
    await user.type(within(fila).getByLabelText("Notas para ana@despacho.mx"), "SPEI 01/10");
    await user.click(within(fila).getByRole("button", { name: "Guardar plan de ana@despacho.mx" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/v1/suscripcion/admin/cuentas/u9", {
        method: "PUT",
        body: JSON.stringify({ plan_clave: "despacho", estado: "activa", vigente_hasta: "2026-12-31", notas: "SPEI 01/10" }),
      }),
    );
  });

  it("edita un plan del catálogo y muestra el error del backend", async () => {
    const user = userEvent.setup();
    renderCon(<AdminSuscripciones />);
    const fila = (await screen.findByDisplayValue("Despacho")).closest("tr") as HTMLElement;
    const limite = within(fila).getByLabelText("Máximo de RFC de despacho");
    await user.clear(limite);
    await user.type(limite, "20");
    await user.click(within(fila).getByRole("button", { name: "Guardar despacho" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/v1/suscripcion/admin/planes/despacho", {
        method: "PUT",
        body: JSON.stringify({ nombre: "Despacho", precio_mensual: "1499.00", max_rfc: 20, activo: true }),
      }),
    );

    vi.mocked(apiFetch).mockRejectedValueOnce(new ApiError(422, "precio_mensual debe ser un importe de 0 o más"));
    await user.click(within(fila).getByRole("button", { name: "Guardar despacho" }));
    expect(await screen.findByText("precio_mensual debe ser un importe de 0 o más")).toBeInTheDocument();
  });
});
