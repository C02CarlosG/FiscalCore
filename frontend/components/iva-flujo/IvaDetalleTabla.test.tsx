import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { IvaDetalleTabla } from "./IvaDetalleTabla";
import { renglon } from "./fixtures";
import type { IvaDetalle } from "@/types/api";

const datos = (items = [renglon()], total = items.length): IvaDetalle => ({ items, total, pagina: 1, por_pagina: 50 });

function renderizar(props: Partial<React.ComponentProps<typeof IvaDetalleTabla>> = {}) {
  const acciones = {
    onVer: vi.fn(), onExcluir: vi.fn(), onReasignar: vi.fn(), onDeshacer: vi.fn(), onPagina: vi.fn(), onReintentar: vi.fn(),
  };
  render(
    <IvaDetalleTabla datos={datos()} cargando={false} error={false} origen="contado" pagina={1} porPagina={50} {...acciones} {...props} />,
  );
  return acciones;
}

describe("IvaDetalleTabla", () => {
  it("muestra fechas dd/mm/aaaa, contraparte, bases e IVA por tasa", () => {
    renderizar();

    const fila = screen.getAllByRole("row")[1];
    expect(fila).toHaveTextContent("10/09/2026");
    expect(fila).toHaveTextContent("CLIENTE SA");
    expect(fila).toHaveTextContent("XAXX010101000");
    expect(fila).toHaveTextContent("$1,000.00");        // base 16
    expect(fila).toHaveTextContent("$160.00");          // IVA 16
    expect(fila).toHaveTextContent("$500.00");          // base 8
    expect(fila).toHaveTextContent("$200.00");          // exento / IVA total
  });

  it("el origen de crédito agrega la fecha de pago y el REP", () => {
    renderizar({
      origen: "credito",
      datos: datos([renglon({ origen: "credito", fecha_pago: "2026-09-25T12:00:00", uuid_pago: "REP-0001", parcialidad: 2 })]),
    });

    expect(screen.getByRole("columnheader", { name: "Fecha de pago" })).toBeInTheDocument();
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("25/09/2026");
    expect(screen.getAllByRole("row")[1]).toHaveTextContent("REP-0001");
  });

  it("sin crédito no hay columna de fecha de pago", () => {
    renderizar();

    expect(screen.queryByRole("columnheader", { name: "Fecha de pago" })).not.toBeInTheDocument();
  });

  it("muestra marcas y motivo con texto en español", () => {
    renderizar({
      origen: "no_considerados",
      datos: datos([renglon({ marcas: ["aproximado", "pago_v1"], motivo: "efectivo" })]),
    });

    const fila = screen.getAllByRole("row")[1];
    expect(fila).toHaveTextContent("IVA aproximado");
    expect(fila).toHaveTextContent("REP 1.0");
    expect(fila).toHaveTextContent("Efectivo mayor a $2,000");
  });

  it("el UUID abre el visor del CFDI", async () => {
    const user = userEvent.setup();
    const { onVer } = { onVer: renderizar().onVer };

    await user.click(screen.getByRole("button", { name: /Ver CFDI 1F3A0001/ }));

    expect(onVer).toHaveBeenCalledWith("1F3A0001-0000-4000-8000-000000000000");
  });

  it("un renglón sin ajuste ofrece no considerar y reasignar", async () => {
    const user = userEvent.setup();
    const acciones = renderizar();
    const r = renglon();

    await user.click(screen.getByRole("button", { name: /No considerar 1F3A0001/ }));
    await user.click(screen.getByRole("button", { name: /Reasignar periodo 1F3A0001/ }));

    expect(acciones.onExcluir).toHaveBeenCalledWith(expect.objectContaining({ uuid: r.uuid }));
    expect(acciones.onReasignar).toHaveBeenCalledWith(expect.objectContaining({ uuid: r.uuid }));
  });

  it("un renglón con ajuste ofrece deshacerlo y muestra su motivo", async () => {
    const user = userEvent.setup();
    const ajuste = { accion: "excluir" as const, periodo_destino: null, motivo: "factura duplicada" };
    const acciones = renderizar({ origen: "no_considerados", datos: datos([renglon({ motivo: "manual", ajuste })]) });

    expect(screen.getAllByRole("row")[1]).toHaveTextContent("factura duplicada");
    expect(screen.queryByRole("button", { name: /No considerar/ })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Deshacer ajuste 1F3A0001/ }));

    expect(acciones.onDeshacer).toHaveBeenCalledWith(expect.objectContaining({ ajuste }));
  });

  it("un reasignado muestra el periodo destino", () => {
    const ajuste = { accion: "reasignar" as const, periodo_destino: "2026-10", motivo: "se cobró en octubre" };
    renderizar({ origen: "reasignados", datos: datos([renglon({ motivo: "reasignado", ajuste })]) });

    expect(screen.getAllByRole("row")[1]).toHaveTextContent("2026 - Octubre");
  });

  it("en no considerados por regla automática solo se puede reasignar", () => {
    renderizar({ origen: "no_considerados", datos: datos([renglon({ motivo: "efectivo" })]) });

    expect(screen.queryByRole("button", { name: /No considerar/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Reasignar periodo/ })).toBeInTheDocument();
  });

  it("pagina: rango, página y botones", async () => {
    const user = userEvent.setup();
    const acciones = renderizar({
      datos: { ...datos(Array.from({ length: 3 }, (_, i) => renglon({ uuid: `U-${i}` })), 120), pagina: 2 },
      pagina: 2,
    });

    expect(screen.getByText("51–100 de 120")).toBeInTheDocument();
    expect(screen.getByText("Página 2 de 3")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Siguiente" }));
    await user.click(screen.getByRole("button", { name: "Anterior" }));
    expect(acciones.onPagina).toHaveBeenNthCalledWith(1, 3);
    expect(acciones.onPagina).toHaveBeenNthCalledWith(2, 1);
  });

  it("vacío, carga y error", async () => {
    const { unmount } = render(
      <IvaDetalleTabla datos={datos([], 0)} cargando={false} error={false} origen="contado" pagina={1} porPagina={50}
        onVer={vi.fn()} onExcluir={vi.fn()} onReasignar={vi.fn()} onDeshacer={vi.fn()} onPagina={vi.fn()} onReintentar={vi.fn()} />,
    );
    expect(screen.getByText("No hay CFDI en esta tarjeta")).toBeInTheDocument();
    unmount();

    const { unmount: u2 } = render(
      <IvaDetalleTabla datos={undefined} cargando error={false} origen="contado" pagina={1} porPagina={50}
        onVer={vi.fn()} onExcluir={vi.fn()} onReasignar={vi.fn()} onDeshacer={vi.fn()} onPagina={vi.fn()} onReintentar={vi.fn()} />,
    );
    expect(screen.getByRole("status", { name: "Cargando detalle" })).toBeInTheDocument();
    u2();

    const onReintentar = vi.fn();
    render(
      <IvaDetalleTabla datos={undefined} cargando={false} error origen="contado" pagina={1} porPagina={50}
        onVer={vi.fn()} onExcluir={vi.fn()} onReasignar={vi.fn()} onDeshacer={vi.fn()} onPagina={vi.fn()} onReintentar={onReintentar} />,
    );
    expect(screen.getByRole("alert")).toHaveTextContent("No se pudo cargar el detalle.");
    await userEvent.setup().click(within(screen.getByRole("alert")).getByRole("button", { name: "Reintentar" }));
    expect(onReintentar).toHaveBeenCalled();
  });
});
