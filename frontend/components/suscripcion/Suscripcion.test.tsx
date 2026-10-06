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
  puede_agregar_rfc: true, es_admin_plataforma: false, dias_para_vencer: null, ...cambios,
});

function renderCon(ui: React.ReactElement, datos: MiSuscripcionDatos = mia()) {
  vi.mocked(apiFetch).mockImplementation(async (ruta: string, opciones?: RequestInit) => {
    if (ruta === "/api/v1/suscripcion") return datos;
    if (ruta === "/api/v1/suscripcion/planes") return planes;
    if (ruta === "/api/v1/suscripcion/historial") {
      return [{ fecha: "2026-10-01T12:00:00+00:00", plan_clave: "basico", plan_nombre: "Básico", estado: "activa",
                vigente_hasta: null }];
    }
    if (ruta === "/api/v1/suscripcion/datos-fiscales") {
      return { rfc: "ACE010101AA1", razon_social: "ACME SA DE CV", regimen_fiscal: "601", codigo_postal: "68000",
               uso_cfdi: "G03" };
    }
    if (ruta === "/api/v1/suscripcion/pagos") {
      return [{ id: "p1", fecha: "2026-10-01", monto: "1499.00", referencia: "SPEI 123", folio_cfdi: "A-15" }];
    }
    if (ruta === "/api/v1/suscripcion/admin/cuentas/u9/datos-fiscales" && !opciones?.method) return null;
    if (ruta === "/api/v1/suscripcion/admin/cuentas/u9/pagos" && !opciones?.method) {
      return [{ id: "p1", fecha: "2026-10-01", monto: "1499.00", referencia: null, folio_cfdi: null,
                registrado_por: "admin@despacho.mx" }];
    }
    if (opciones?.method === "POST") return {};
    if (ruta === "/api/v1/suscripcion/admin/cuentas/u9/historial") {
      return [{ fecha: "2026-10-01T12:00:00+00:00", plan_clave: "basico", plan_nombre: "Básico", estado: "suspendida",
                vigente_hasta: "2026-12-31", notas: "pago SPEI", asignada_por: "admin@despacho.mx" }];
    }
    if (ruta.startsWith("/api/v1/suscripcion/admin/cuentas?")) {
      return [{ usuario_id: "u9", email: "ana@despacho.mx", nombre: "Ana", es_admin_plataforma: false,
                plan_clave: null, estado: null, vigente_hasta: null, notas: null, uso_rfc: 1, dias_para_vencer: 3 }];
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

  it("avisa del vencimiento próximo", async () => {
    renderCon(<MiSuscripcion />, mia({ dias_para_vencer: 3 }));
    expect(await screen.findByText(/Tu suscripción vence en 3 días/)).toBeInTheDocument();
  });

  it("muestra mis datos fiscales y mis pagos", async () => {
    renderCon(<MiSuscripcion />);
    expect(await screen.findByText("ACE010101AA1")).toBeInTheDocument();
    const tabla = await screen.findByRole("table", { name: "Pagos de la suscripción" });
    expect(within(tabla).getByText("A-15")).toBeInTheDocument();
    expect(within(tabla).queryByText("Registró")).not.toBeInTheDocument();
  });

  it("el administrador abre el detalle de una cuenta", async () => {
    const user = userEvent.setup();
    renderCon(<AdminSuscripciones />, mia({ es_admin_plataforma: true }));
    expect(await screen.findByText("Vence en 3 días")).toBeInTheDocument();
    await user.click(await screen.findByRole("button", { name: "Detalle de ana@despacho.mx" }));
    const tabla = await screen.findByRole("table", { name: "Historial de plan" });
    expect(within(tabla).getByText("pago SPEI")).toBeInTheDocument();
    expect(within(tabla).getByText("admin@despacho.mx")).toBeInTheDocument();
    expect(within(tabla).getByText("Suspendida")).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith("/api/v1/suscripcion/admin/cuentas/u9/historial");
  });

  it("el administrador registra un pago y guarda los datos fiscales", async () => {
    const user = userEvent.setup();
    renderCon(<AdminSuscripciones />, mia({ es_admin_plataforma: true }));
    await user.click(await screen.findByRole("button", { name: "Detalle de ana@despacho.mx" }));
    const pago = await screen.findByRole("form", { name: "Registrar pago de ana@despacho.mx" });
    expect(within(pago).getByRole("button", { name: "Registrar pago" })).toBeDisabled();
    await user.type(within(pago).getByLabelText("Fecha"), "2026-10-01");
    await user.type(within(pago).getByLabelText("Monto (MXN)"), "1499.50");
    await user.type(within(pago).getByLabelText("Folio del CFDI"), "A-16");
    await user.click(within(pago).getByRole("button", { name: "Registrar pago" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/v1/suscripcion/admin/cuentas/u9/pagos", {
        method: "POST",
        body: JSON.stringify({ fecha: "2026-10-01", monto: "1499.50", referencia: null, folio_cfdi: "A-16" }),
      }),
    );
    expect(await within(pago).findByText("Pago registrado.")).toBeInTheDocument();

    const fiscales = screen.getByRole("form", { name: "Datos fiscales de ana@despacho.mx" });
    await user.type(within(fiscales).getByLabelText("RFC"), "ACE010101AA1");
    await user.type(within(fiscales).getByLabelText("Razón social"), "ACME");
    await user.type(within(fiscales).getByLabelText("Régimen fiscal"), "601");
    await user.type(within(fiscales).getByLabelText("Código postal"), "68000");
    await user.type(within(fiscales).getByLabelText("Uso del CFDI"), "G03");
    await user.click(within(fiscales).getByRole("button", { name: "Guardar datos fiscales" }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith("/api/v1/suscripcion/admin/cuentas/u9/datos-fiscales", {
        method: "PUT",
        body: JSON.stringify({ rfc: "ACE010101AA1", razon_social: "ACME", regimen_fiscal: "601",
                               codigo_postal: "68000", uso_cfdi: "G03" }),
      }),
    );
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
