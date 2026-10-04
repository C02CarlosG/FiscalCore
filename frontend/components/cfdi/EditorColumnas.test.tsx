import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { EditorColumnas, type ColumnaEditable } from "./EditorColumnas";

const columnas: ColumnaEditable[] = [
  { clave: "a", etiqueta: "Alfa", visible: true },
  { clave: "b", etiqueta: "Beta", visible: true },
  { clave: "c", etiqueta: "Gamma", visible: false },
];

function abrir(props: Partial<React.ComponentProps<typeof EditorColumnas>> = {}) {
  const acciones = { onGuardar: vi.fn(), onRestablecer: vi.fn(), onAbiertoChange: vi.fn() };
  const vista = (abierto: boolean) => (
    <EditorColumnas abierto={abierto} titulo="Columnas" columnas={columnas} ocupado={false} error={false}
      {...acciones} {...props} />
  );
  const r = render(vista(true));
  return { ...acciones, rerender: (abierto: boolean) => r.rerender(vista(abierto)) };
}

const orden = () => screen.getAllByRole("checkbox").map((c) => c.nextElementSibling?.textContent);

describe("EditorColumnas", () => {
  it("lista las columnas en su orden y con su visibilidad", () => {
    abrir();
    expect(orden()).toEqual(["Alfa", "Beta", "Gamma"]);
    expect(screen.getByLabelText("Alfa")).toBeChecked();
    expect(screen.getByLabelText("Gamma")).not.toBeChecked();
  });

  it("sube y baja con botones y no deja mover los extremos", async () => {
    const user = userEvent.setup();
    abrir();

    expect(screen.getByRole("button", { name: "Subir Alfa" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Bajar Gamma" })).toBeDisabled();
    await user.click(screen.getByRole("button", { name: "Bajar Alfa" }));
    expect(orden()).toEqual(["Beta", "Alfa", "Gamma"]);
    await user.click(screen.getByRole("button", { name: "Subir Gamma" }));
    expect(orden()).toEqual(["Beta", "Gamma", "Alfa"]);
  });

  it("guarda el orden y la visibilidad editados", async () => {
    const user = userEvent.setup();
    const { onGuardar } = abrir();

    await user.click(screen.getByRole("button", { name: "Bajar Alfa" }));
    await user.click(screen.getByLabelText("Gamma"));
    await user.click(screen.getByRole("button", { name: "Guardar" }));

    expect(onGuardar).toHaveBeenCalledWith([
      { clave: "b", visible: true }, { clave: "a", visible: true }, { clave: "c", visible: true },
    ]);
  });

  it("no deja guardar sin ninguna columna visible", async () => {
    const user = userEvent.setup();
    abrir();
    await user.click(screen.getByLabelText("Alfa"));
    await user.click(screen.getByLabelText("Beta"));
    expect(screen.getByRole("button", { name: "Guardar" })).toBeDisabled();
  });

  it("descartar y volver a abrir parte de lo guardado, no de lo editado", async () => {
    const user = userEvent.setup();
    const { rerender } = abrir();

    await user.click(screen.getByRole("button", { name: "Bajar Alfa" }));
    rerender(false);
    rerender(true);

    expect(orden()).toEqual(["Alfa", "Beta", "Gamma"]);
  });

  it("restablecer avisa y un error de guardado se muestra", async () => {
    const user = userEvent.setup();
    const { onRestablecer } = abrir({ error: true });

    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo guardar");
    await user.click(screen.getByRole("button", { name: "Restablecer" }));
    expect(onRestablecer).toHaveBeenCalled();
  });
});
