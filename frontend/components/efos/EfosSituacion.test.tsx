import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { EfosSituacion } from "./EfosSituacion";

describe("EfosSituacion", () => {
  it.each([
    ["Presunto", "Presunto", "alto"],
    ["Definitivo", "Definitivo", "critico"],
    ["Desvirtuado", "Desvirtuado", "informativo"],
    ["Sentencia Favorable", "Sentencia Favorable", "informativo"],
  ])("muestra %s con riesgo %s", (situacion, texto, riesgo) => {
    render(<EfosSituacion situacion={situacion} />);
    const el = screen.getByText(texto);
    expect(el).toHaveAttribute("data-riesgo", riesgo);
  });
  it("sin situación muestra un guion", () => {
    render(<EfosSituacion situacion={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });
});
