import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CfdiLoteBarra, MAX_LOTE } from "./CfdiLoteBarra";

const mutate = vi.fn();
let estado: Record<string, unknown> = {};
vi.mock("@/hooks/useNotasCfdi", () => ({
  useEtiquetas: () => ({ data: [{ id: "t1", nombre: "Revisar", color: "#ef4444", cfdis: 0 }] }),
  useEtiquetarLote: () => ({ mutate, isPending: false, isError: false, isSuccess: false, ...estado }),
  useCrearEtiqueta: () => ({ mutate: vi.fn(), isPending: false, isError: false }),
}));

const uuids = (n: number) => Array.from({ length: n }, (_, i) => `U${i}`);

describe("CfdiLoteBarra", () => {
  beforeEach(() => {
    mutate.mockClear();
    estado = {};
  });

  it("sin selección no se muestra", () => {
    const { container } = render(<CfdiLoteBarra empresaId="e1" uuids={[]} onLimpiar={vi.fn()} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("cuenta lo seleccionado y deshabilita las acciones hasta elegir etiqueta", () => {
    render(<CfdiLoteBarra empresaId="e1" uuids={uuids(3)} onLimpiar={vi.fn()} />);

    expect(screen.getByText("3 CFDI seleccionados")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Agregar etiqueta" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Quitar etiqueta" })).toBeDisabled();
  });

  it("avisa y bloquea cuando la selección pasa del tope de 500", () => {
    render(<CfdiLoteBarra empresaId="e1" uuids={uuids(MAX_LOTE + 2)} onLimpiar={vi.fn()} />);

    expect(screen.getByRole("alert")).toHaveTextContent("desmarca 2");
    expect(screen.getByRole("button", { name: "Agregar etiqueta" })).toBeDisabled();
  });

  it("limpiar la selección avisa al padre", async () => {
    const onLimpiar = vi.fn();
    render(<CfdiLoteBarra empresaId="e1" uuids={uuids(1)} onLimpiar={onLimpiar} />);

    await userEvent.setup().click(screen.getByRole("button", { name: "Limpiar selección" }));
    expect(onLimpiar).toHaveBeenCalled();
  });
});
