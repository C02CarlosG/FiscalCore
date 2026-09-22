import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { ResumenRiesgos } from "./ResumenRiesgos";
import type { ResumenRiesgos as ResumenRiesgosType } from "@/types/api";

const resumen: ResumenRiesgosType = {
  critico: 2,
  alto: 3,
  medio: 1,
  bajo: 6,
  monto_total_en_riesgo: 284320,
};

describe("ResumenRiesgos", () => {
  it("renders one stat card per severidad with its conteo", () => {
    render(<ResumenRiesgos resumen={resumen} />);
    expect(screen.getByText("Críticos")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
    expect(screen.getByText("Altos")).toBeInTheDocument();
    expect(screen.getByText("3")).toBeInTheDocument();
    expect(screen.getByText("Medios")).toBeInTheDocument();
    expect(screen.getByText("Bajos")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
  });
});
