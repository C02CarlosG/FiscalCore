import { describe, it, expect, vi, beforeEach } from "vitest";
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { CierrePeriodo } from "./CierrePeriodo";
import { useCierre } from "@/hooks/useCierre";
import { usePeriodoGlobal } from "@/hooks/usePeriodoGlobal";
import { usePeriodos } from "@/hooks/usePeriodos";

vi.mock("@/hooks/useCierre");
vi.mock("@/hooks/usePeriodoGlobal");
vi.mock("@/hooks/usePeriodos");
vi.mock("next/navigation", () => ({
  useParams: () => ({ empresaId: "test-empresa" }),
}));

describe("CierrePeriodo", () => {
  beforeEach(() => {
    vi.mocked(usePeriodoGlobal).mockReturnValue([
      "2026-01",
      vi.fn(),
    ]);

    vi.mocked(usePeriodos).mockReturnValue({
      data: {
        periodos: [{ periodo: "2026-01", tiene_datos: true }],
      },
      isLoading: false,
      isError: false,
      refetch: vi.fn(),
    } as any);

    vi.mocked(useCierre).mockReturnValue({
      validaciones: {
        validaciones: [
          { nombre: "Al menos 1 ingreso", pasó: true, bloquea: true, mensaje: "OK" },
          { nombre: "Ingresos > 0", pasó: true, bloquea: true, mensaje: "OK" },
          { nombre: "Sin CFDI cancelados", pasó: true, bloquea: true, mensaje: "OK" },
        ],
        puede_cerrar: true,
      },
      isLoadingValidaciones: false,
      isErrorValidaciones: false,
      estado: { cerrado: false },
      isLoadingEstado: false,
      isErrorEstado: false,
      cerrar: vi.fn().mockResolvedValue({}),
      isClosing: false,
      reabrirError: null,
      reabrir: vi.fn().mockResolvedValue({}),
      isReopening: false,
      descargarPapelTrabajo: vi.fn().mockResolvedValue({}),
      refetchValidaciones: vi.fn(),
      refetchEstado: vi.fn(),
    } as any);
  });

  it("renderiza el título y descripción", () => {
    render(<CierrePeriodo />);
    expect(screen.getByText("Cierre de período")).toBeInTheDocument();
    expect(screen.getByText(/Descarga el papel de trabajo/)).toBeInTheDocument();
  });

  it("muestra validaciones cuando se cargan", () => {
    render(<CierrePeriodo />);
    expect(screen.getByText("Al menos 1 ingreso")).toBeInTheDocument();
    expect(screen.getByText("Ingresos > 0")).toBeInTheDocument();
  });

  it("habilita cierre cuando pode_cerrar es true", () => {
    render(<CierrePeriodo />);
    const button = screen.getByText("Cerrar período");
    expect(button).not.toBeDisabled();
  });

  it("abre modal de confirmación al hacer clic en Cerrar período", async () => {
    render(<CierrePeriodo />);
    const button = screen.getByText("Cerrar período");
    fireEvent.click(button);
    await waitFor(() => {
      expect(screen.getByText(/Confirmar cierre del período/)).toBeInTheDocument();
    });
  });

  it("llama a cerrar cuando se confirma el cierre", async () => {
    const mockCerrar = vi.fn().mockResolvedValue({});
    vi.mocked(useCierre).mockReturnValue({
      ...vi.mocked(useCierre).getMockImplementation()?.(),
      cerrar: mockCerrar,
      refetchEstado: vi.fn(),
    } as any);

    render(<CierrePeriodo />);
    fireEvent.click(screen.getByText("Cerrar período"));
    await waitFor(() => {
      fireEvent.click(screen.getByText(/Cerrar período/)[1]);
    });
  });
});
