import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ProveedoresPantalla } from "./ProveedoresPantalla";
import { useCrearProveedor, useEditarProveedor, useProveedores } from "@/hooks/useProveedores";
import { ApiError } from "@/lib/api-client";
import type { Proveedor } from "@/types/api";

vi.mock("next/navigation", () => ({ useParams: () => ({ empresaId: "e1" }) }));
vi.mock("@/hooks/useProveedores", () => ({ useProveedores: vi.fn(), useCrearProveedor: vi.fn(), useEditarProveedor: vi.fn() }));

const prov = (extra: Partial<Proveedor> = {}): Proveedor => ({
  id: "p1", rfc: "PRO010101AAA", nombre: "PROVEEDOR UNO", nombre_editado: false, tipo_tercero: "04", tipo_operacion: "85",
  pais: null, jurisdiccion_detalle: null, id_fiscal: null, efectos_fiscales: null, origen: "cfdi", pendiente: false,
  created_at: "2026-09-01T00:00:00", updated_at: "2026-09-01T00:00:00", ...extra,
});
const lista = (items: Proveedor[], extra = {}) =>
  ({ data: { total: items.length, agregados: 0, omitidos: 0, items, ...extra }, isError: false, refetch: vi.fn() }) as never;

let crear: ReturnType<typeof vi.fn>;
let editar: ReturnType<typeof vi.fn>;

beforeEach(() => {
  vi.clearAllMocks();
  crear = vi.fn().mockResolvedValue({});
  editar = vi.fn().mockResolvedValue({});
  vi.mocked(useProveedores).mockReturnValue(lista([prov(), prov({ id: "p2", rfc: "XEXX010101000", nombre: "ACME", tipo_tercero: "05", pendiente: true, origen: "manual" })]));
  vi.mocked(useCrearProveedor).mockReturnValue({ mutateAsync: crear, isPending: false } as never);
  vi.mocked(useEditarProveedor).mockReturnValue({ mutateAsync: editar, isPending: false } as never);
});

describe("ProveedoresPantalla", () => {
  it("lista los proveedores con su clasificación, el aviso de datos faltantes y el lugar de la 69-B", () => {
    render(<ProveedoresPantalla />);

    expect(screen.getByText("PROVEEDOR UNO")).toBeInTheDocument();
    expect(screen.getByText("04 · Nacional")).toBeInTheDocument();
    expect(screen.getByText("Faltan datos")).toBeInTheDocument();
    expect(screen.getByRole("columnheader", { name: "Lista 69-B" })).toBeInTheDocument();
    expect(screen.getByText("Alta manual")).toBeInTheDocument();
  });

  it("busca con el texto escrito", async () => {
    render(<ProveedoresPantalla />);

    await userEvent.type(screen.getByLabelText("Buscar proveedor"), "acme");
    await userEvent.click(screen.getByRole("button", { name: "Buscar" }));

    expect(vi.mocked(useProveedores).mock.calls.at(-1)).toEqual(["e1", "acme"]);
  });

  it("da de alta un proveedor con RFC obligatorio", async () => {
    render(<ProveedoresPantalla />);

    await userEvent.click(screen.getByRole("button", { name: "Agregar proveedor" }));
    expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
    await userEvent.type(screen.getByLabelText("RFC"), "nue010101aaa");
    await userEvent.selectOptions(screen.getByLabelText("Tipo de tercero"), "04");
    await userEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(crear).toHaveBeenCalledWith(expect.objectContaining({ rfc: "NUE010101AAA", tipo_tercero: "04", tipo_operacion: null })));
  });

  it("edita el tipo de tercero y la operación sin mandar el RFC", async () => {
    render(<ProveedoresPantalla />);

    await userEvent.click(screen.getByRole("button", { name: "Editar PROVEEDOR UNO" }));
    expect(screen.getByLabelText("RFC")).toBeDisabled();
    await userEvent.selectOptions(screen.getByLabelText("Operación por omisión"), "06");
    await userEvent.click(screen.getByRole("button", { name: "Guardar" }));

    await waitFor(() => expect(editar).toHaveBeenCalledWith({ id: "p1", cambios: expect.objectContaining({ tipo_operacion: "06", tipo_tercero: "04" }) }));
    expect(editar.mock.calls[0][0].cambios).not.toHaveProperty("rfc");
  });

  it("muestra el error del servidor y deja el diálogo abierto", async () => {
    crear.mockRejectedValue(new ApiError(409, "El proveedor ya existe"));
    render(<ProveedoresPantalla />);

    await userEvent.click(screen.getByRole("button", { name: "Agregar proveedor" }));
    await userEvent.type(screen.getByLabelText("RFC"), "PRO010101AAA");
    await userEvent.click(screen.getByRole("button", { name: "Guardar" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("El proveedor ya existe");
  });

  it("muestra el estado vacío y el error de carga", () => {
    vi.mocked(useProveedores).mockReturnValue(lista([]));
    const { unmount } = render(<ProveedoresPantalla />);
    expect(screen.getByText(/Todavía no hay proveedores/)).toBeInTheDocument();
    unmount();

    vi.mocked(useProveedores).mockReturnValue({ data: undefined, isError: true, refetch: vi.fn() } as never);
    render(<ProveedoresPantalla />);
    expect(screen.getByText("No se pudo cargar el catálogo de proveedores.")).toBeInTheDocument();
  });
});
