import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { CfdiCelda } from "./CfdiCelda";
import type { CfdiColumna } from "@/types/api";

const columna: CfdiColumna = {
  clave: "situacion_69b", etiqueta: "Situación 69-B", tipo_dato: "catalogo", grupo: "encabezado",
  visible_por_defecto: true, ordenable: true, filtrable: true, opciones: ["Presunto", "Desvirtuado", "Definitivo", "Sentencia Favorable"],
};

describe("CfdiCelda · situación 69-B", () => {
  it("pinta la insignia de riesgo de la situación", () => {
    render(<CfdiCelda columna={columna} fila={{ uuid: "U1", situacion_69b: "Definitivo" }} />);
    expect(screen.getByText("Definitivo")).toHaveAttribute("data-riesgo", "critico");
  });

  it("sin situación (proveedor fuera de la lista) muestra un guion", () => {
    render(<CfdiCelda columna={columna} fila={{ uuid: "U1", situacion_69b: null }} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
