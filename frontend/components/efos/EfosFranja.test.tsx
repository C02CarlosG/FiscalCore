import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EfosFranja } from "./EfosFranja";
import { useEfosEstado, useImportarEfos, useSubirEfos } from "@/hooks/useEfos";
import { loadSession } from "@/lib/auth";

vi.mock("@/hooks/useEfos", () => ({ useEfosEstado: vi.fn(), useImportarEfos: vi.fn(), useSubirEfos: vi.fn() }));
vi.mock("@/lib/auth", () => ({ loadSession: vi.fn() }));

const estado = (extra = {}) => ({
  hay_lista: true, fecha_archivo: "2026-09-30", importada_en: "2026-10-12T10:00:00Z", filas: 14234, rfc_unicos: 14055,
  dias_de_antiguedad: 13, desactualizada: false, ultimo_intento: null, ...extra,
});
let importar: ReturnType<typeof vi.fn>;

function preparar(data: unknown, rol: string | undefined = "contador") {
  vi.mocked(useEfosEstado).mockReturnValue({ data, isLoading: false } as never);
  importar = vi.fn().mockResolvedValue({});
  vi.mocked(useImportarEfos).mockReturnValue({ mutateAsync: importar, isPending: false } as never);
  vi.mocked(useSubirEfos).mockReturnValue({ mutateAsync: vi.fn(), isPending: false } as never);
  vi.mocked(loadSession).mockReturnValue({ rol } as never);
}

describe("EfosFranja", () => {
  beforeEach(() => vi.clearAllMocks());

  it("muestra la fecha de la lista del SAT", () => {
    preparar(estado());
    render(<EfosFranja />);
    expect(screen.getByText(/actualizada al 30\/09\/2026/i)).toBeInTheDocument();
    expect(screen.queryByRole("alert")).not.toBeInTheDocument();
  });

  it("avisa cuando la lista está desactualizada", () => {
    preparar(estado({ fecha_archivo: "2025-12-31", dias_de_antiguedad: 286, desactualizada: true }));
    render(<EfosFranja />);
    expect(screen.getByRole("alert")).toHaveTextContent(/desactualizada/i);
  });

  it("sin lista importada explica que todavía no hay datos", () => {
    preparar({ hay_lista: false, fecha_archivo: null, importada_en: null, filas: 0, rfc_unicos: 0, dias_de_antiguedad: null, desactualizada: true, ultimo_intento: null });
    render(<EfosFranja />);
    expect(screen.getByRole("alert")).toHaveTextContent(/todavía no hay una lista/i);
  });

  it("los botones de administración solo salen para el administrador de la plataforma", () => {
    preparar(estado(), "contador");
    const { unmount } = render(<EfosFranja />);
    expect(screen.queryByRole("button", { name: /actualizar ahora/i })).not.toBeInTheDocument();
    unmount();
    preparar(estado(), "admin");
    render(<EfosFranja />);
    expect(screen.getByRole("button", { name: /actualizar ahora/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/subir csv/i)).toBeInTheDocument();
  });

  it("actualizar ahora llama a la importación y muestra el error del servidor", async () => {
    preparar(estado(), "admin");
    importar.mockRejectedValue(new Error("No se pudo descargar la lista del SAT: timed out"));
    render(<EfosFranja />);
    await userEvent.click(screen.getByRole("button", { name: /actualizar ahora/i }));
    expect(importar).toHaveBeenCalled();
    expect(await screen.findByText(/timed out/)).toBeInTheDocument();
  });
});
