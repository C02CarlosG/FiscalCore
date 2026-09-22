import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { DataTable, type DataTableColumn } from "./DataTable";

interface Fila {
  id: string;
  nombre: string;
  monto: number;
}

const columns: DataTableColumn<Fila>[] = [
  { key: "nombre", header: "Nombre", cell: (f) => f.nombre, sortValue: (f) => f.nombre, searchable: true },
  { key: "monto", header: "Monto", cell: (f) => `$${f.monto}`, sortValue: (f) => f.monto },
];

function filas(n: number): Fila[] {
  // Orden de inserción intencionalmente inverso al alfabético, para que
  // "sin ordenar" y "ordenado ascendente" sean estados visiblemente distintos.
  return Array.from({ length: n }, (_, i) => {
    const idx = n - 1 - i;
    return {
      id: `f${idx}`,
      nombre: `Fila ${String(idx).padStart(2, "0")}`,
      monto: (idx + 1) * 10,
    };
  });
}

describe("DataTable", () => {
  it("shows the empty message when there is no data", () => {
    render(
      <DataTable data={[]} columns={columns} getRowId={(f) => f.id} emptyMessage="Sin datos." />,
    );
    expect(screen.getByText("Sin datos.")).toBeInTheDocument();
  });

  it("sorts ascending then descending when clicking a sortable header", async () => {
    const user = userEvent.setup();
    render(
      <DataTable data={filas(3)} columns={columns} getRowId={(f) => f.id} emptyMessage="Sin datos." pageSize={10} />,
    );

    const filasVisiblesEnOrden = () =>
      screen.getAllByRole("row").slice(1).map((row) => within(row).getAllByRole("cell")[0].textContent);

    expect(filasVisiblesEnOrden()).toEqual(["Fila 02", "Fila 01", "Fila 00"]);

    await user.click(screen.getByRole("columnheader", { name: /Nombre/ }));
    expect(filasVisiblesEnOrden()).toEqual(["Fila 00", "Fila 01", "Fila 02"]);

    await user.click(screen.getByRole("columnheader", { name: /Nombre/ }));
    expect(filasVisiblesEnOrden()).toEqual(["Fila 02", "Fila 01", "Fila 00"]);
  });

  it("filters rows by the search input using searchable columns", async () => {
    const user = userEvent.setup();
    render(
      <DataTable
        data={filas(3)}
        columns={columns}
        getRowId={(f) => f.id}
        emptyMessage="Sin datos."
        searchPlaceholder="Buscar..."
      />,
    );

    await user.type(screen.getByPlaceholderText("Buscar..."), "Fila 01");
    expect(screen.getAllByRole("row")).toHaveLength(2); // header + 1 match
    expect(screen.getByText("Fila 01")).toBeInTheDocument();
  });

  it("paginates using pageSize", async () => {
    const user = userEvent.setup();
    render(
      <DataTable data={filas(9)} columns={columns} getRowId={(f) => f.id} emptyMessage="Sin datos." pageSize={4} />,
    );

    expect(screen.getAllByRole("row")).toHaveLength(5); // header + 4
    expect(screen.getByText(/1–4 de 9/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: /Siguiente/ }));
    expect(screen.getByText(/5–8 de 9/)).toBeInTheDocument();
  });

  it("tracks selected rows via checkboxes when selectable", async () => {
    const user = userEvent.setup();
    render(
      <DataTable data={filas(2)} columns={columns} getRowId={(f) => f.id} emptyMessage="Sin datos." selectable pageSize={10} />,
    );

    const rowCheckboxes = screen.getAllByRole("checkbox").slice(1); // [0] es "seleccionar todo"
    await user.click(rowCheckboxes[0]);
    expect(screen.getByText(/1 seleccionada/)).toBeInTheDocument();
  });
});
