import { describe, it, expect } from "vitest";
import { resolveActiveView, VALID_VIEWS } from "../src/context/AppContext.jsx";

describe("resolveActiveView", () => {
  it("mantiene una vista válida", () => {
    expect(resolveActiveView("reportes")).toBe("reportes");
  });

  it("cae a 'dash' cuando fc_active guarda una pantalla inválida", () => {
    expect(resolveActiveView("pantalla_inexistente")).toBe("dash");
  });

  it("cae a 'dash' cuando no hay valor guardado (null)", () => {
    expect(resolveActiveView(null)).toBe("dash");
  });

  it("toda VALID_VIEWS se resuelve a sí misma", () => {
    for (const v of VALID_VIEWS) expect(resolveActiveView(v)).toBe(v);
  });
});
