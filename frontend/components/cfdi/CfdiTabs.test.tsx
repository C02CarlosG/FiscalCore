import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CfdiTabs } from "./CfdiTabs";

const conteos = { I: 507, E: 12, T: 0, N: 33, P: 80 };

describe("CfdiTabs", () => {
  it("muestra las cinco pestañas con su conteo", () => {
    render(<CfdiTabs activo="I" conteos={conteos} onChange={() => {}} />);

    const pestañas = screen.getAllByRole("tab");
    expect(pestañas.map((p) => p.textContent)).toEqual([
      "Ingreso507", "Egreso12", "Traslado0", "Nómina33", "Pago80",
    ]);
  });

  it("marca la pestaña activa", () => {
    render(<CfdiTabs activo="N" conteos={conteos} onChange={() => {}} />);

    expect(screen.getByRole("tab", { name: /Nómina/ })).toHaveAttribute("aria-selected", "true");
    expect(screen.getByRole("tab", { name: /Ingreso/ })).toHaveAttribute("aria-selected", "false");
  });

  it("al hacer clic avisa el tipo elegido", async () => {
    const onChange = vi.fn();
    const user = userEvent.setup();
    render(<CfdiTabs activo="I" conteos={conteos} onChange={onChange} />);

    await user.click(screen.getByRole("tab", { name: /Egreso/ }));

    expect(onChange).toHaveBeenCalledWith("E");
  });

  it("separa los miles del conteo", () => {
    render(<CfdiTabs activo="I" conteos={{ ...conteos, I: 12345 }} onChange={() => {}} />);

    expect(screen.getByRole("tab", { name: /Ingreso/ })).toHaveTextContent("12,345");
  });

  it("sin conteos todavía no muestra números", () => {
    render(<CfdiTabs activo="I" conteos={undefined} onChange={() => {}} />);

    expect(screen.getByRole("tab", { name: "Ingreso" })).toBeInTheDocument();
  });
});
