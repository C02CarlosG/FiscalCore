import { describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { CfdiTabla } from "./CfdiTabla";
import { useCfdiDetalle } from "@/hooks/useCfdis";
import type { CfdiColumna, CfdiFila, CfdiListadoResponse } from "@/types/api";

vi.mock("@/hooks/useCfdis", () => ({ useCfdiDetalle: vi.fn() }));

const col = (clave: string, etiqueta: string, tipo_dato: CfdiColumna["tipo_dato"], extra: Partial<CfdiColumna> = {}): CfdiColumna => ({
  clave, etiqueta, tipo_dato, grupo: "encabezado", visible_por_defecto: true, ordenable: true, filtrable: true, opciones: [], ...extra,
});

const columnas: CfdiColumna[] = [
  col("fecha_emision", "Fecha de expedición", "fecha"),
  col("rfc_contraparte", "RFC", "texto"),
  col("total", "Total", "moneda"),
  col("pagos_relacionados", "CFDIs de pago relacionados", "lista", { ordenable: false }),
  col("metodo_pago", "Método de pago", "catalogo"),
  col("estado", "Estado", "catalogo"),
  col("uuid", "UUID", "texto", { visible_por_defecto: false }),
];

const columnasConcepto: CfdiColumna[] = [
  col("descripcion", "Descripción", "texto", { grupo: "concepto", ordenable: false }),
];

const fila = (extra: Partial<CfdiFila> = {}): CfdiFila => ({
  uuid: "U1",
  fecha_emision: "2026-09-05T13:07:09",
  rfc_contraparte: "XAXX010101000",
  total: 1160.5,
  pagos_relacionados: ["P1", "P2"],
  metodo_pago: "PUE",
  metodo_pago_desc: "Pago en una sola exhibición",
  estado: "vigente",
  ...extra,
});

const datos = (items: CfdiFila[], total = items.length, pagina = 1, por_pagina = 30): CfdiListadoResponse => ({
  items, total, pagina, por_pagina,
});

function renderTabla(props: Partial<React.ComponentProps<typeof CfdiTabla>> = {}) {
  const acciones = {
    onOrdenar: vi.fn(), onPagina: vi.fn(), onPorPagina: vi.fn(), onReintentar: vi.fn(), onLimpiar: vi.fn(),
    onVer: vi.fn(),
  };
  vi.mocked(useCfdiDetalle).mockReturnValue({
    data: { conceptos: [{ linea: 1, descripcion: "Servicio de consultoría" }], total_conceptos: 1 },
    isError: false, refetch: vi.fn(),
  } as never);
  render(
    <CfdiTabla
      empresaId="e1"
      columnas={columnas}
      columnasConcepto={columnasConcepto}
      datos={datos([fila()])}
      cargando={false}
      error={false}
      orden="fecha_emision"
      dir="asc"
      pagina={1}
      porPagina={30}
      {...acciones}
      {...props}
    />,
  );
  return acciones;
}

describe("CfdiTabla", () => {
  it("muestra solo las columnas visibles por defecto del catálogo", () => {
    renderTabla();

    const encabezados = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(encabezados).toEqual([
      "Acciones", "Fecha de expedición", "RFC", "Total", "CFDIs de pago relacionados", "Método de pago", "Estado",
    ]);
  });

  it("da formato a fecha, importe, lista y estado", () => {
    renderTabla();

    const renglon = screen.getAllByRole("row")[1];
    expect(within(renglon).getByText("05/09/2026")).toBeInTheDocument();
    expect(within(renglon).getByText("$1,160.50")).toBeInTheDocument();
    expect(within(renglon).getByText("P1, P2")).toBeInTheDocument();
    expect(within(renglon).getByText("Vigente")).toBeInTheDocument();
  });

  it("una columna de catálogo muestra el código y su descripción al pasar el cursor", () => {
    renderTabla();

    expect(screen.getByText("PUE")).toHaveAttribute("title", "Pago en una sola exhibición");
  });

  it("los datos faltantes se muestran como guion", () => {
    renderTabla({ datos: datos([fila({ rfc_contraparte: null, total: null, pagos_relacionados: [] })]) });

    const renglon = screen.getAllByRole("row")[1];
    expect(within(renglon).getAllByText("—")).toHaveLength(3);
  });

  describe("orden", () => {
    it("un encabezado ordenable es un botón y marca el orden actual", () => {
      renderTabla({ orden: "total", dir: "desc" });

      expect(screen.getByRole("columnheader", { name: "Total" })).toHaveAttribute("aria-sort", "descending");
      expect(screen.getByRole("columnheader", { name: "RFC" })).toHaveAttribute("aria-sort", "none");
      expect(screen.getByRole("button", { name: "RFC" })).toBeInTheDocument();
    });

    it("una columna que no se puede ordenar no es botón", () => {
      renderTabla();

      expect(screen.queryByRole("button", { name: "CFDIs de pago relacionados" })).not.toBeInTheDocument();
      expect(screen.getByRole("columnheader", { name: "CFDIs de pago relacionados" })).not.toHaveAttribute("aria-sort");
    });

    it("al elegir otra columna ordena ascendente", async () => {
      const user = userEvent.setup();
      const { onOrdenar } = renderTabla({ orden: "fecha_emision", dir: "desc" });

      await user.click(screen.getByRole("button", { name: "Total" }));

      expect(onOrdenar).toHaveBeenCalledWith("total", "asc");
    });

    it("al volver a elegir la columna activa invierte el sentido", async () => {
      const user = userEvent.setup();
      const { onOrdenar } = renderTabla({ orden: "total", dir: "asc" });

      await user.click(screen.getByRole("button", { name: "Total" }));

      expect(onOrdenar).toHaveBeenCalledWith("total", "desc");
    });
  });

  describe("paginación", () => {
    it("indica el rango y el total", () => {
      renderTabla({ datos: datos([fila()], 507, 2, 30), pagina: 2, porPagina: 30 });

      expect(screen.getByText("31–60 de 507")).toBeInTheDocument();
      expect(screen.getByText("Página 2 de 17")).toBeInTheDocument();
    });

    it("separa los miles del total", () => {
      renderTabla({ datos: datos([fila()], 12345), porPagina: 100 });

      expect(screen.getByText("1–100 de 12,345")).toBeInTheDocument();
    });

    it("la última página termina en el total", () => {
      renderTabla({ datos: datos([fila()], 507, 17, 30), pagina: 17 });

      expect(screen.getByText("481–507 de 507")).toBeInTheDocument();
    });

    it("avanza y retrocede de página", async () => {
      const user = userEvent.setup();
      const { onPagina } = renderTabla({ datos: datos([fila()], 507, 2, 30), pagina: 2 });

      await user.click(screen.getByRole("button", { name: "Siguiente" }));
      await user.click(screen.getByRole("button", { name: "Anterior" }));

      expect(onPagina).toHaveBeenNthCalledWith(1, 3);
      expect(onPagina).toHaveBeenNthCalledWith(2, 1);
    });

    it("en la primera y en la última página se deshabilita el botón que no aplica", () => {
      renderTabla({ datos: datos([fila()], 40, 1, 30), pagina: 1 });
      expect(screen.getByRole("button", { name: "Anterior" })).toBeDisabled();
      expect(screen.getByRole("button", { name: "Siguiente" })).toBeEnabled();
    });

    it("la última página no deja avanzar", () => {
      renderTabla({ datos: datos([fila()], 40, 2, 30), pagina: 2 });

      expect(screen.getByRole("button", { name: "Siguiente" })).toBeDisabled();
    });

    it("cambia el tamaño de página", async () => {
      const user = userEvent.setup();
      const { onPorPagina } = renderTabla();

      await user.click(screen.getByRole("combobox", { name: "Filas por página" }));
      await user.click(await screen.findByRole("option", { name: "50" }));

      expect(onPorPagina).toHaveBeenCalledWith(50);
    });
  });

  describe("estados", () => {
    it("cargando sin datos muestra un esqueleto", () => {
      renderTabla({ datos: undefined, cargando: true });

      expect(screen.getByRole("status", { name: "Cargando CFDI" })).toBeInTheDocument();
    });

    it("cargando con la página anterior a la vista la conserva y se marca ocupada", () => {
      renderTabla({ cargando: true });

      expect(screen.getByText("05/09/2026")).toBeInTheDocument();
      expect(screen.getByRole("table")).toHaveAttribute("aria-busy", "true");
    });

    it("el error ofrece reintentar", async () => {
      const user = userEvent.setup();
      const { onReintentar } = renderTabla({ datos: undefined, error: true });

      expect(screen.getByRole("alert")).toHaveTextContent("No se pudieron cargar los CFDI.");
      await user.click(screen.getByRole("button", { name: "Reintentar" }));

      expect(onReintentar).toHaveBeenCalledTimes(1);
    });

    it("sin resultados explica y ofrece limpiar los filtros", async () => {
      const user = userEvent.setup();
      const { onLimpiar } = renderTabla({ datos: datos([], 0) });

      expect(screen.getByText("No hay CFDI con estos filtros")).toBeInTheDocument();
      expect(screen.queryByRole("table")).not.toBeInTheDocument();
      await user.click(screen.getByRole("button", { name: "Limpiar filtros" }));

      expect(onLimpiar).toHaveBeenCalledTimes(1);
    });
  });

  describe("acciones de la fila", () => {
    it("desplegar muestra los conceptos del CFDI y volver a pulsar los oculta", async () => {
      const user = userEvent.setup();
      renderTabla();
      expect(screen.queryByText("Servicio de consultoría")).not.toBeInTheDocument();

      await user.click(screen.getByRole("button", { name: "Ver conceptos" }));

      expect(useCfdiDetalle).toHaveBeenCalledWith("e1", "U1");
      expect(screen.getByText("Servicio de consultoría")).toBeInTheDocument();
      expect(screen.getByRole("button", { name: "Ocultar conceptos" })).toHaveAttribute("aria-expanded", "true");

      await user.click(screen.getByRole("button", { name: "Ocultar conceptos" }));
      expect(screen.queryByText("Servicio de consultoría")).not.toBeInTheDocument();
    });

    it("cada fila se despliega por separado", async () => {
      const user = userEvent.setup();
      renderTabla({ datos: datos([fila(), fila({ uuid: "U2" })]) });

      await user.click(screen.getAllByRole("button", { name: "Ver conceptos" })[1]);

      expect(useCfdiDetalle).toHaveBeenCalledWith("e1", "U2");
      expect(screen.getAllByRole("button", { name: "Ver conceptos" })).toHaveLength(1);
      expect(screen.getAllByRole("button", { name: "Ocultar conceptos" })).toHaveLength(1);
    });

    it("el botón del visor avisa con el uuid de su fila", async () => {
      const user = userEvent.setup();
      const { onVer } = renderTabla({ datos: datos([fila({ uuid: "U9" })]) });

      await user.click(screen.getByRole("button", { name: "Abrir visor del CFDI" }));

      expect(onVer).toHaveBeenCalledWith("U9");
    });
  });
});
