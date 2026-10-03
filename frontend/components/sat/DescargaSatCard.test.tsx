import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DescargaSatCard } from "./DescargaSatCard";
import type { FielEstado, SatSolicitud } from "@/types/api";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch } from "@/lib/api-client";

const ESTADO_URL = "/api/v1/sat/empresas/e1/fiel/estado";
const SOLICITUDES_URL = "/api/v1/sat/solicitudes?empresa_id=e1";
const SYNC_URL = "/api/v1/sat/empresas/e1/fiel/sync";
const AVANZAR_URL = "/api/v1/sat/empresas/e1/fiel/sync/avanzar";

const solicitud: SatSolicitud = {
  id: "s1",
  tipo: "emitidos",
  periodo_inicio: "2026-09",
  periodo_fin: "2026-09",
  estado: "descargado",
  num_cfdi: 289,
  cfdi_importados: 289,
  error_msg: null,
  created_at: "2026-09-29T19:07:00Z",
  updated_at: "2026-09-29T19:09:00Z",
};

function mockApi(estado: FielEstado, solicitudes: SatSolicitud[] = []) {
  vi.mocked(apiFetch).mockImplementation(async (path: string) => {
    if (path === ESTADO_URL) return estado;
    if (path === SOLICITUDES_URL) return solicitudes;
    if (path === SYNC_URL) return { mensaje: "Sync iniciado", solicitudes: [], periodo: "2026-09", tipos: [] };
    if (path === AVANZAR_URL) return { avanzadas: [] };
    throw new Error(`llamada inesperada: ${path}`);
  });
}

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <DescargaSatCard empresaId="e1" />
    </QueryClientProvider>,
  );
}

describe("DescargaSatCard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("blocks the download until an e.firma is stored", async () => {
    mockApi({ tiene_fiel: false });
    renderCard();

    expect(await screen.findByText(/Guarda primero la e\.firma/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Descargar del SAT" })).toBeDisabled();
  });

  it("requires a period", async () => {
    mockApi({ tiene_fiel: true, vencida: false });
    const user = userEvent.setup();
    renderCard();
    await waitFor(() => expect(screen.getByRole("button", { name: "Descargar del SAT" })).toBeEnabled());

    await user.click(screen.getByRole("button", { name: "Descargar del SAT" }));

    expect(screen.getByRole("alert")).toHaveTextContent("El periodo es obligatorio");
    expect(vi.mocked(apiFetch).mock.calls.some(([path]) => path === SYNC_URL)).toBe(false);
  });

  it("requests emitidos and recibidos for the period by default", async () => {
    mockApi({ tiene_fiel: true, vencida: false });
    const user = userEvent.setup();
    renderCard();
    await waitFor(() => expect(screen.getByRole("button", { name: "Descargar del SAT" })).toBeEnabled());

    await user.type(screen.getByLabelText("Periodo a descargar"), "2026-09");
    await user.click(screen.getByRole("button", { name: "Descargar del SAT" }));

    await waitFor(() => {
      expect(vi.mocked(apiFetch).mock.calls.some(([path]) => path === SYNC_URL)).toBe(true);
    });
    const [, options] = vi.mocked(apiFetch).mock.calls.find(([path]) => path === SYNC_URL)!;
    const body = options!.body as FormData;
    expect(options!.method).toBe("POST");
    expect(body.get("periodo")).toBe("2026-09");
    expect(body.get("tipo")).toBe("ambos");
    expect(await screen.findByText(/Solicitud enviada al SAT/)).toBeInTheDocument();
  });

  it("shows which type the SAT rejected when the other one was accepted", async () => {
    mockApi({ tiene_fiel: true, vencida: false });
    const base = vi.mocked(apiFetch).getMockImplementation()!;
    const rechazo = "emitidos: El SAT ya no acepta más solicitudes de este periodo (código 5002)";
    vi.mocked(apiFetch).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === SYNC_URL) {
        return { mensaje: "ok", solicitudes: [{ id: "s2", tipo: "recibidos" }], periodo: "2026-09",
          tipos: ["emitidos", "recibidos"], errores: [rechazo] };
      }
      return base(path, options);
    });
    const user = userEvent.setup();
    renderCard();

    await user.type(await screen.findByLabelText(/periodo/i), "2026-09");
    await user.click(screen.getByRole("button", { name: /descargar del sat/i }));

    expect(await screen.findByText(/Solicitud enviada al SAT/)).toBeInTheDocument();
    expect(screen.getByRole("alert")).toHaveTextContent(rechazo);
  });

  it("lists previous downloads with their status and imported count", async () => {
    mockApi({ tiene_fiel: true, vencida: false }, [solicitud]);
    renderCard();

    expect(await screen.findByText("Emitidos")).toBeInTheDocument();
    expect(screen.getByText("2026-09")).toBeInTheDocument();
    expect(screen.getByText("Descargado")).toBeInTheDocument();
    expect(screen.getByText("289 de 289")).toBeInTheDocument();
  });

  it("muestra la fecha de la solicitud como dd/mm/aaaa hh:mm", async () => {
    mockApi({ tiene_fiel: true, vencida: false }, [{ ...solicitud, created_at: "2026-09-29T19:07:00" }]);
    renderCard();

    expect(await screen.findByText("29/09/2026 19:07")).toBeInTheDocument();
  });

  it("shows the SAT error of a failed download", async () => {
    mockApi({ tiene_fiel: true, vencida: false }, [
      { ...solicitud, estado: "fallo", cfdi_importados: 0, error_msg: "SAT reportó estado: rechazada" },
    ]);
    renderCard();

    expect(await screen.findByText("SAT reportó estado: rechazada")).toBeInTheDocument();
  });

  it("flags a download that is missing CFDI reported by the SAT", async () => {
    const aviso =
      "Descarga incompleta: se importaron 287 de los 289 CFDI que reportó el SAT; 2 no se pudieron importar.";
    mockApi({ tiene_fiel: true, vencida: false }, [
      { ...solicitud, cfdi_importados: 287, error_msg: aviso },
    ]);
    renderCard();

    expect(await screen.findByText("Incompleta")).toBeInTheDocument();
    expect(screen.queryByText("Descargado")).not.toBeInTheDocument();
    expect(screen.getByText(aviso)).toBeInTheDocument();
    expect(screen.getByText("287 de 289")).toBeInTheDocument();
  });

  it("asks the backend to advance downloads that are still in progress", async () => {
    mockApi({ tiene_fiel: true, vencida: false }, [{ ...solicitud, estado: "solicitado" }]);
    renderCard();

    await waitFor(() => {
      expect(vi.mocked(apiFetch).mock.calls.some(([path]) => path === AVANZAR_URL)).toBe(true);
    });
    const [, options] = vi.mocked(apiFetch).mock.calls.find(([path]) => path === AVANZAR_URL)!;
    expect(options!.method).toBe("POST");
  });

  it("stops advancing and shows the error when a pass fails", async () => {
    mockApi({ tiene_fiel: true, vencida: false }, [{ ...solicitud, estado: "en_proceso" }]);
    const base = vi.mocked(apiFetch).getMockImplementation()!;
    vi.mocked(apiFetch).mockImplementation(async (path: string, options?: RequestInit) => {
      if (path === AVANZAR_URL) throw new Error("No hay FIEL guardada para esta empresa");
      return base(path, options);
    });
    renderCard();

    const alerta = await screen.findByRole("alert");
    expect(alerta).toHaveTextContent("No se pudo avanzar la descarga: No hay FIEL guardada para esta empresa");
    expect(screen.getByRole("button", { name: "Reintentar" })).toBeInTheDocument();
  });

  it("does not call the SAT when no download is in progress", async () => {
    mockApi({ tiene_fiel: true, vencida: false }, [solicitud]);
    renderCard();

    expect(await screen.findByText("Descargado")).toBeInTheDocument();
    expect(vi.mocked(apiFetch).mock.calls.some(([path]) => path === AVANZAR_URL)).toBe(false);
  });
});
