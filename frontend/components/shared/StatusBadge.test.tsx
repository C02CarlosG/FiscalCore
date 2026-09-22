import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { StatusBadge } from "./StatusBadge";

describe("StatusBadge", () => {
  it.each([
    ["critico", "Crítico"],
    ["alto", "Alto"],
    ["medio", "Medio"],
    ["bajo", "Bajo"],
    ["abierto", "Pendiente"],
    ["resuelto", "Resuelto"],
    ["exacto", "Exacto"],
    ["parcial", "Match parcial"],
    ["sin_cfdi", "Sin CFDI"],
    ["sin_movimiento", "Sin movimiento"],
  ])("renders the label for status %s", (status, label) => {
    render(<StatusBadge status={status} />);
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  it("falls back to a capitalized neutral badge for an unknown status", () => {
    render(<StatusBadge status="desconocido" />);
    expect(screen.getByText("Desconocido")).toBeInTheDocument();
  });
});
