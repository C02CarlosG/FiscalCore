import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { DocumentoFiscalCard } from "./DocumentoFiscalCard";
import type { DocumentoFiscal, TipoDocumentoFiscal } from "./tipos";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>("@/lib/api-client");
  return { ...actual, apiFetch: vi.fn(), apiDescargar: vi.fn() };
});
vi.mock("@/lib/descarga", () => ({ guardarArchivo: vi.fn() }));

import { apiDescargar, apiFetch, ApiError } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";

const BASE = "/api/v1/informacion-fiscal/empresas/e1";

function documento(cambios: Partial<DocumentoFiscal> = {}): DocumentoFiscal {
  return {
    id: "d1",
    tipo: "opinion",
    nombre_archivo: "32D.pdf",
    tamano_bytes: 1000,
    rfc: "ACM010101AA1",
    fecha_emision: "2026-10-03",
    created_at: "2026-10-04T10:00:00+00:00",
    datos: { sentido: "positivo", folio: "26NA1234567" },
    antiguedad_dias: 1,
    vigente_hasta: "2026-11-01",
    vigente: true,
    ...cambios,
  };
}

function renderCard(tipo: TipoDocumentoFiscal, doc: DocumentoFiscal | null) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <DocumentoFiscalCard empresaId="e1" tipo={tipo} documento={doc} />
    </QueryClientProvider>,
  );
}

const pdf = (nombre = "csf.pdf", bytes = 10) =>
  new File([new Uint8Array(bytes)], nombre, { type: "application/pdf" });

describe("DocumentoFiscalCard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
    vi.mocked(apiDescargar).mockReset();
    vi.mocked(guardarArchivo).mockReset();
    URL.createObjectURL = vi.fn(() => "blob:visor");
    URL.revokeObjectURL = vi.fn();
  });

  it("sin documento invita a subir el primero", () => {
    renderCard("constancia", null);
    expect(screen.getByText("Constancia de situación fiscal")).toBeInTheDocument();
    expect(screen.getByText("Aún no se ha subido ninguna constancia.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Ver" })).not.toBeInTheDocument();
    expect(screen.getByLabelText("Archivo PDF de la constancia")).toBeInTheDocument();
  });

  it("muestra el sentido y la vigencia de la opinión", () => {
    renderCard("opinion", documento());
    expect(screen.getByText("Positiva")).toBeInTheDocument();
    expect(screen.getByText("Vigente hasta 01/11/2026")).toBeInTheDocument();
    expect(screen.getByText("26NA1234567")).toBeInTheDocument();
  });

  it("avisa cuando la opinión ya venció o es negativa", () => {
    renderCard("opinion", documento({ vigente: false, datos: { sentido: "negativo" } }));
    expect(screen.getByText("Negativa")).toBeInTheDocument();
    expect(screen.getByText("Vencida: valía hasta 01/11/2026")).toBeInTheDocument();
  });

  it("sentido no identificado no se presenta como positivo", () => {
    renderCard("opinion", documento({ datos: { sentido: null } }));
    expect(screen.getByText("Sentido no identificado")).toBeInTheDocument();
  });

  it("muestra regímenes, CP y antigüedad de la constancia", () => {
    renderCard(
      "constancia",
      documento({
        tipo: "constancia",
        antiguedad_dias: 45,
        vigente: null,
        vigente_hasta: null,
        datos: { regimenes: ["Régimen General de Ley Personas Morales"], cp_fiscal: "68000", estatus_padron: "ACTIVO" },
      }),
    );
    expect(screen.getByText("Régimen General de Ley Personas Morales")).toBeInTheDocument();
    expect(screen.getByText("68000")).toBeInTheDocument();
    expect(screen.getByText("ACTIVO")).toBeInTheDocument();
    expect(screen.getByText(/hace 45 días/)).toBeInTheDocument();
    expect(screen.getByText(/más de 30 días/)).toBeInTheDocument();
  });

  it("valida extensión y tamaño antes de llamar a la API", async () => {
    const user = userEvent.setup({ applyAccept: false });
    renderCard("constancia", null);

    await user.upload(screen.getByLabelText("Archivo PDF de la constancia"), pdf("csf.docx"));
    await user.click(screen.getByRole("button", { name: "Subir" }));
    expect(await screen.findByText("El archivo debe ser un PDF")).toBeInTheDocument();

    await user.upload(screen.getByLabelText("Archivo PDF de la constancia"), pdf("csf.pdf", 5 * 1024 * 1024 + 1));
    await user.click(screen.getByRole("button", { name: "Subir" }));
    expect(await screen.findByText("El PDF no puede pesar más de 5 MB")).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();
  });

  it("sube el PDF a la ruta del tipo y avisa", async () => {
    vi.mocked(apiFetch).mockResolvedValue(documento({ tipo: "constancia" }));
    const user = userEvent.setup();
    renderCard("constancia", null);

    await user.upload(screen.getByLabelText("Archivo PDF de la constancia"), pdf());
    await user.click(screen.getByRole("button", { name: "Subir" }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    const [ruta, opciones] = vi.mocked(apiFetch).mock.calls[0];
    expect(ruta).toBe(`${BASE}/documentos/constancia`);
    expect(opciones?.method).toBe("POST");
    expect((opciones?.body as FormData).get("archivo")).toBeInstanceOf(File);
    expect(await screen.findByText("Documento guardado")).toBeInTheDocument();
  });

  it("muestra el motivo del rechazo del backend", async () => {
    vi.mocked(apiFetch).mockRejectedValue(
      new ApiError(422, "El documento es del RFC XYZ990101AB2, pero la empresa es ACM010101AA1."),
    );
    const user = userEvent.setup();
    renderCard("constancia", null);

    await user.upload(screen.getByLabelText("Archivo PDF de la constancia"), pdf());
    await user.click(screen.getByRole("button", { name: "Subir" }));

    expect(
      await screen.findByText("El documento es del RFC XYZ990101AB2, pero la empresa es ACM010101AA1."),
    ).toBeInTheDocument();
  });

  it("abre el visor con el PDF pedido con la sesión", async () => {
    vi.mocked(apiDescargar).mockResolvedValue(new Blob(["%PDF-"]));
    const user = userEvent.setup();
    renderCard("opinion", documento());

    await user.click(screen.getByRole("button", { name: "Ver" }));

    const visor = await screen.findByTitle("Visor de 32D.pdf");
    expect(visor).toHaveAttribute("src", "blob:visor");
    expect(apiDescargar).toHaveBeenCalledWith(`${BASE}/documentos/d1/pdf`);

    await user.click(within(screen.getByRole("dialog")).getByRole("button", { name: "Cerrar" }));
    await waitFor(() => expect(URL.revokeObjectURL).toHaveBeenCalledWith("blob:visor"));
  });

  it("descarga el PDF con su nombre original", async () => {
    const blob = new Blob(["%PDF-"]);
    vi.mocked(apiDescargar).mockResolvedValue(blob);
    const user = userEvent.setup();
    renderCard("opinion", documento());

    await user.click(screen.getByRole("button", { name: "Descargar" }));

    expect(apiDescargar).toHaveBeenCalledWith(`${BASE}/documentos/d1/pdf?descargar=true`);
    await waitFor(() => expect(guardarArchivo).toHaveBeenCalledWith(blob, "32D.pdf"));
  });
});
