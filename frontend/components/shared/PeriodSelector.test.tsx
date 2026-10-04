import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { PeriodSelector, opcionesDePeriodo } from "./PeriodSelector";

const HOY = new Date(2026, 9, 3); // octubre de 2026

describe("opcionesDePeriodo", () => {
  it("une los periodos con datos y el mes actual, del más reciente al más antiguo", () => {
    expect(opcionesDePeriodo(["2026-07", "2026-09"], "2026-09", HOY)).toEqual([
      "2026-10", "2026-09", "2026-07",
    ]);
  });

  it("no repite el mes actual si ya viene en la lista", () => {
    expect(opcionesDePeriodo(["2026-10", "2026-09"], "2026-10", HOY)).toEqual(["2026-10", "2026-09"]);
  });

  it("incluye el periodo elegido aunque no tenga datos", () => {
    expect(opcionesDePeriodo([], "2026-03", HOY)).toEqual(["2026-10", "2026-03"]);
  });

  it("ignora valores que no son periodo", () => {
    expect(opcionesDePeriodo(["basura", "2026-09"], "2026-09", HOY)).toEqual(["2026-10", "2026-09"]);
  });
});

describe("PeriodSelector", () => {
  it("muestra el periodo elegido con su etiqueta larga", () => {
    render(<PeriodSelector value="2026-09" onChange={() => {}} periodosConDatos={["2026-09"]} hoy={HOY} />);

    expect(screen.getByRole("combobox", { name: "Periodo" })).toHaveTextContent("2026 - Septiembre");
  });

  it("ofrece los periodos con datos y llama a onChange con YYYY-MM", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<PeriodSelector value="2026-09" onChange={onChange} periodosConDatos={["2026-09", "2026-08"]} hoy={HOY} />);

    await user.click(screen.getByRole("combobox", { name: "Periodo" }));
    const lista = await screen.findByRole("listbox");
    expect(within(lista).getAllByRole("option").map((o) => o.textContent)).toEqual([
      "2026 - Octubre", // el mes actual siempre se ofrece
      "2026 - Septiembre",
      "2026 - Agosto",
    ]);

    await user.click(within(lista).getByRole("option", { name: "2026 - Agosto" }));

    expect(onChange).toHaveBeenCalledWith("2026-08");
  });
});
