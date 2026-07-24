import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { IngestaResultado } from "./IngestaResultado";

describe("IngestaResultado", () => {
  it("shows the message and the processed count", () => {
    render(
      <IngestaResultado
        resultado={{
          mensaje: "3 CFDI procesados correctamente",
          registros_procesados: 3,
          errores: [],
          periodo: "2026-07",
        }}
      />,
    );

    expect(
      screen.getByText("3 CFDI procesados correctamente"),
    ).toBeInTheDocument();
    expect(screen.getByText("3 registros procesados.")).toBeInTheDocument();
  });

  it("does not render an error list when there are no errors", () => {
    render(
      <IngestaResultado
        resultado={{
          mensaje: "ok",
          registros_procesados: 1,
          errores: [],
          periodo: "2026-07",
        }}
      />,
    );

    expect(screen.queryByRole("list")).not.toBeInTheDocument();
  });

  it("renders each partial error as a list item", () => {
    render(
      <IngestaResultado
        resultado={{
          mensaje: "1 CFDI procesado correctamente",
          registros_procesados: 1,
          errores: ["otro.xml: UUID duplicado", "malo.xml: XML inválido"],
          periodo: "2026-07",
        }}
      />,
    );

    expect(
      screen.getByText("otro.xml: UUID duplicado"),
    ).toBeInTheDocument();
    expect(screen.getByText("malo.xml: XML inválido")).toBeInTheDocument();
  });
});
