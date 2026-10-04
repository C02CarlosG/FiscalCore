import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IvaTarjetasVista } from "./IvaTarjetasVista";
import { resumenIva } from "./fixtures";

describe("IvaTarjetasVista", () => {
  it("muestra las tres tarjetas con su importe", () => {
    render(<IvaTarjetasVista resumen={resumenIva()} vista="trasladado" onCambio={vi.fn()} />);

    expect(screen.getByRole("tab", { name: /Trasladado/ })).toHaveTextContent("$3,190,362.48");
    expect(screen.getByRole("tab", { name: /Acreditable/ })).toHaveTextContent("$2,162,403.41");
    expect(screen.getByRole("tab", { name: /A cargo/ })).toHaveTextContent("$1,024,172.32");
  });

  it("marca la vista elegida", () => {
    render(<IvaTarjetasVista resumen={resumenIva()} vista="acreditable" onCambio={vi.fn()} />);

    expect(screen.getByRole("tab", { name: /Acreditable/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Trasladado/ })).toHaveAttribute("aria-selected", "false");
  });

  it("elegir una tarjeta avisa con su vista", async () => {
    const onCambio = vi.fn();
    const user = userEvent.setup();
    render(<IvaTarjetasVista resumen={resumenIva()} vista="trasladado" onCambio={onCambio} />);

    await user.click(screen.getByRole("tab", { name: /A cargo/ }));

    expect(onCambio).toHaveBeenCalledWith("a-cargo");
  });

  it("con saldo a favor la tercera tarjeta se llama A favor", () => {
    const r = resumenIva();
    r.resultado = { ...r.resultado, iva_por_pagar: -320, saldo_a_cargo: 0, saldo_a_favor: 320 };

    render(<IvaTarjetasVista resumen={r} vista="a-cargo" onCambio={vi.fn()} />);

    expect(screen.getByRole("tab", { name: /A favor/ })).toHaveTextContent("$320.00");
  });

  it("sin resumen todavía muestra guiones", () => {
    render(<IvaTarjetasVista resumen={undefined} vista="trasladado" onCambio={vi.fn()} />);

    expect(screen.getByRole("tab", { name: /Trasladado/ })).toHaveTextContent("—");
  });
});
