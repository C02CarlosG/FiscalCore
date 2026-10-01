import { describe, expect, it, vi, beforeEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { FielCard } from "./FielCard";
import type { FielEstado } from "@/types/api";

vi.mock("@/lib/api-client", async () => {
  const actual = await vi.importActual<typeof import("@/lib/api-client")>(
    "@/lib/api-client",
  );
  return { ...actual, apiFetch: vi.fn() };
});

import { apiFetch, ApiError } from "@/lib/api-client";

const ESTADO_URL = "/api/v1/sat/empresas/e1/fiel/estado";
const GUARDAR_URL = "/api/v1/sat/empresas/e1/fiel/guardar";

const conFiel: FielEstado = {
  tiene_fiel: true,
  rfc_certificado: "AAA010101AAA",
  vigencia_fin: "2028-05-10",
  dias_restantes: 580,
  vencida: false,
  por_vencer: false,
  guardada_el: "2026-10-01 10:00:00",
};

function mockApi(estado: FielEstado, guardar?: () => Promise<unknown>) {
  vi.mocked(apiFetch).mockImplementation(async (path: string, options?: RequestInit) => {
    if (path === ESTADO_URL) return estado;
    if (path === GUARDAR_URL && options?.method === "POST") {
      return guardar ? guardar() : { rfc_certificado: "AAA010101AAA", vigencia_fin: "2028-05-10" };
    }
    if (options?.method === "DELETE") return { eliminada: true };
    throw new Error(`llamada inesperada: ${path}`);
  });
}

function renderCard() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <FielCard empresaId="e1" />
    </QueryClientProvider>,
  );
}

const cer = new File(["cer"], "empresa.cer", { type: "application/x-x509-ca-cert" });
const key = new File(["key"], "empresa.key", { type: "application/octet-stream" });

describe("FielCard", () => {
  beforeEach(() => {
    vi.mocked(apiFetch).mockReset();
  });

  it("explains that there is no e.firma yet and shows the upload form", async () => {
    mockApi({ tiene_fiel: false });
    renderCard();

    expect(await screen.findByText("Sin e.firma guardada")).toBeInTheDocument();
    expect(screen.getByLabelText("Certificado (.cer)")).toBeInTheDocument();
    expect(screen.getByLabelText("Llave privada (.key)")).toBeInTheDocument();
    expect(screen.getByLabelText("Contraseña de la llave privada")).toHaveAttribute("type", "password");
  });

  it("requires both files and the password before calling the API", async () => {
    mockApi({ tiene_fiel: false });
    const user = userEvent.setup();
    renderCard();
    await screen.findByText("Sin e.firma guardada");

    await user.click(screen.getByRole("button", { name: "Guardar e.firma" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Selecciona el certificado (.cer)");

    await user.upload(screen.getByLabelText("Certificado (.cer)"), cer);
    await user.click(screen.getByRole("button", { name: "Guardar e.firma" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Selecciona la llave privada (.key)");

    await user.upload(screen.getByLabelText("Llave privada (.key)"), key);
    await user.click(screen.getByRole("button", { name: "Guardar e.firma" }));
    expect(screen.getByRole("alert")).toHaveTextContent("Escribe la contraseña de la llave privada");

    expect(vi.mocked(apiFetch).mock.calls.every(([path]) => path === ESTADO_URL)).toBe(true);
  });

  it("sends the certificate, key and password as FormData and clears the password", async () => {
    mockApi({ tiene_fiel: false });
    const user = userEvent.setup();
    renderCard();
    await screen.findByText("Sin e.firma guardada");

    await user.upload(screen.getByLabelText("Certificado (.cer)"), cer);
    await user.upload(screen.getByLabelText("Llave privada (.key)"), key);
    await user.type(screen.getByLabelText("Contraseña de la llave privada"), "secreta");
    await user.click(screen.getByRole("button", { name: "Guardar e.firma" }));

    await waitFor(() => {
      expect(vi.mocked(apiFetch).mock.calls.some(([path]) => path === GUARDAR_URL)).toBe(true);
    });
    const [, options] = vi.mocked(apiFetch).mock.calls.find(([path]) => path === GUARDAR_URL)!;
    const body = options!.body as FormData;
    expect(options!.method).toBe("POST");
    expect((body.get("cer_file") as File).name).toBe("empresa.cer");
    expect((body.get("key_file") as File).name).toBe("empresa.key");
    expect(body.get("password")).toBe("secreta");
    await waitFor(() => {
      expect(screen.getByLabelText("Contraseña de la llave privada")).toHaveValue("");
    });
  });

  it("shows the API error when the SAT credentials are rejected", async () => {
    mockApi({ tiene_fiel: false }, () =>
      Promise.reject(new ApiError(422, "La contraseña de la llave privada es incorrecta")),
    );
    const user = userEvent.setup();
    renderCard();
    await screen.findByText("Sin e.firma guardada");

    await user.upload(screen.getByLabelText("Certificado (.cer)"), cer);
    await user.upload(screen.getByLabelText("Llave privada (.key)"), key);
    await user.type(screen.getByLabelText("Contraseña de la llave privada"), "mala");
    await user.click(screen.getByRole("button", { name: "Guardar e.firma" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(
      "La contraseña de la llave privada es incorrecta",
    );
  });

  it("shows the certificate RFC and validity when an e.firma is stored", async () => {
    mockApi(conFiel);
    renderCard();

    expect(await screen.findByText("e.firma vigente")).toBeInTheDocument();
    expect(screen.getByText("AAA010101AAA")).toBeInTheDocument();
    expect(screen.getByText(/10\/05\/2028/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reemplazar e.firma" })).toBeInTheDocument();
  });

  it("warns when the stored e.firma has expired", async () => {
    mockApi({ ...conFiel, vencida: true, dias_restantes: -3 });
    renderCard();

    expect(await screen.findByText("e.firma vencida")).toBeInTheDocument();
  });

  it("asks for confirmation before deleting the stored e.firma", async () => {
    mockApi(conFiel);
    const user = userEvent.setup();
    renderCard();
    await screen.findByText("e.firma vigente");

    await user.click(screen.getByRole("button", { name: "Eliminar e.firma" }));
    expect(vi.mocked(apiFetch).mock.calls.some(([, o]) => o?.method === "DELETE")).toBe(false);

    await user.click(screen.getByRole("button", { name: "Sí, eliminar" }));
    await waitFor(() => {
      const llamada = vi.mocked(apiFetch).mock.calls.find(([, o]) => o?.method === "DELETE");
      expect(llamada?.[0]).toBe("/api/v1/sat/empresas/e1/fiel");
    });
  });
});
