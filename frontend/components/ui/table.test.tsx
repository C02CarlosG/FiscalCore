import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { Table, TableHead, TableHeader, TableRow } from "./table";

describe("TableHead", () => {
  it("todos los encabezados comparten estilo: mayúsculas, negrita y 11px", () => {
    render(
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Fecha</TableHead>
          </TableRow>
        </TableHeader>
      </Table>,
    );
    const th = screen.getByRole("columnheader", { name: "Fecha" });
    expect(th).toHaveClass("uppercase", "font-bold", "text-[11px]");
  });
});
