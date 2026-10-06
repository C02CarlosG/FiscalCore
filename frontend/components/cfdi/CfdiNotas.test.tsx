import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CfdiNotas } from "./CfdiNotas";

const acciones = {
  lote: vi.fn(), comentar: vi.fn(), borrarComentario: vi.fn(), subir: vi.fn(), borrarEvidencia: vi.fn(), descargar: vi.fn(),
};
let errorSubida: Error | null = null;

const mut = (mutate: unknown, extra: Record<string, unknown> = {}) => ({ mutate, isPending: false, isError: false, ...extra });

vi.mock("@/hooks/useNotasCfdi", () => ({
  useEtiquetas: () => ({ data: [{ id: "t1", nombre: "Revisar", color: "#ef4444", cfdis: 1 }, { id: "t2", nombre: "Listo", color: "#10b981", cfdis: 0 }] }),
  useEtiquetasDeCfdi: () => ({ data: [{ id: "t1", nombre: "Revisar", color: "#ef4444" }] }),
  useEtiquetarLote: () => mut(acciones.lote),
  useCrearEtiqueta: () => mut(vi.fn()),
  useComentarios: () => ({ data: [
    { id: "c1", texto: "Falta el comprobante", creado: "2026-09-05T10:00:00", autor: "ana@x.mx", puede_borrar: true },
    { id: "c2", texto: "De otra persona", creado: "2026-09-05T11:00:00", autor: "luis@x.mx", puede_borrar: false },
  ] }),
  useCrearComentario: () => mut(acciones.comentar),
  useBorrarComentario: () => mut(acciones.borrarComentario),
  useEvidencias: () => ({ data: [
    { id: "v1", nombre: "factura.pdf", tipo: "application/pdf", tamano: 2048, creado: "2026-09-05T10:00:00", autor: "ana@x.mx", puede_borrar: true },
  ] }),
  useSubirEvidencia: () => mut(acciones.subir, { isError: errorSubida !== null, error: errorSubida }),
  useBorrarEvidencia: () => mut(acciones.borrarEvidencia),
  useDescargarEvidencia: () => mut(acciones.descargar),
}));

describe("CfdiNotas", () => {
  beforeEach(() => {
    Object.values(acciones).forEach((f) => f.mockClear());
    errorSubida = null;
  });

  it("alterna las etiquetas del CFDI: quita la puesta y agrega la que falta", async () => {
    const user = userEvent.setup();
    render(<CfdiNotas empresaId="e1" uuid="U1" />);

    expect(screen.getByRole("button", { name: "Quitar etiqueta Revisar" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Quitar etiqueta Revisar" }));
    expect(acciones.lote).toHaveBeenCalledWith({ uuids: ["U1"], quitar: ["t1"] });
    await user.click(screen.getByRole("button", { name: "Agregar etiqueta Listo" }));
    expect(acciones.lote).toHaveBeenCalledWith({ uuids: ["U1"], agregar: ["t2"] });
  });

  it("comenta con el texto recortado y solo ofrece borrar los propios", async () => {
    const user = userEvent.setup();
    render(<CfdiNotas empresaId="e1" uuid="U1" />);

    expect(screen.getAllByRole("button", { name: "Borrar comentario" })).toHaveLength(1);
    await user.click(screen.getByRole("button", { name: "Comentar" }));
    expect(acciones.comentar).not.toHaveBeenCalled();           // vacío no se envía

    await user.type(screen.getByLabelText("Nuevo comentario"), "  revisar IVA  ");
    await user.click(screen.getByRole("button", { name: "Comentar" }));
    expect(acciones.comentar.mock.calls[0][0]).toBe("revisar IVA");
  });

  it("lista, descarga y borra evidencias", async () => {
    const user = userEvent.setup();
    render(<CfdiNotas empresaId="e1" uuid="U1" />);

    expect(screen.getByText(/factura\.pdf/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Descargar factura.pdf" }));
    expect(acciones.descargar.mock.calls[0][0]).toMatchObject({ id: "v1" });
    await user.click(screen.getByRole("button", { name: "Borrar factura.pdf" }));
    expect(acciones.borrarEvidencia.mock.calls[0][0]).toBe("v1");
  });

  it("sube un archivo permitido y rechaza en el navegador el que pasa de 5 MB", async () => {
    const user = userEvent.setup({ applyAccept: false });
    render(<CfdiNotas empresaId="e1" uuid="U1" />);
    const campo = screen.getByLabelText("Adjuntar evidencia");

    await user.upload(campo, new File(["%PDF-1.4"], "ok.pdf", { type: "application/pdf" }));
    expect(acciones.subir).toHaveBeenCalledTimes(1);

    const grande = new File([new Uint8Array(5 * 1024 * 1024 + 1)], "grande.pdf", { type: "application/pdf" });
    await user.upload(campo, grande);
    expect(acciones.subir).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("alert")).toHaveTextContent("excede el máximo de 5 MB");
  });

  it("muestra el error que devuelve el servidor al subir", () => {
    errorSubida = new Error("El contenido del archivo no corresponde a su extensión");
    render(<CfdiNotas empresaId="e1" uuid="U1" />);

    expect(screen.getByRole("alert")).toHaveTextContent("no corresponde a su extensión");
  });
});
