import { describe, expect, it } from "vitest";
import { render, screen, within } from "@testing-library/react";
import { CfdiTotales } from "./CfdiTotales";
import type { CfdiCifra, CfdiTotalesBloque } from "@/types/api";

const vacio: CfdiTotalesBloque = {
  conteo: 0, retencion_iva: null, retencion_ieps: null, retencion_isr: null, traslado_iva: null,
  traslado_ieps: null, traslado_isr: null, total_retenciones: null, subtotal: null, descuento: null,
  neto: null, total: null,
};

const con: CfdiTotalesBloque = {
  conteo: 507, retencion_iva: 0, retencion_ieps: 0, retencion_isr: 125.5, traslado_iva: 1600,
  traslado_ieps: 0, traslado_isr: 0, total_retenciones: 125.5, subtotal: 10000, descuento: 500,
  neto: 9500, total: 11100,
};

const cifrasComprobante: CfdiCifra[] = [
  ["conteo", "CFDI", "entero"], ["retencion_iva", "Ret. IVA", "moneda"], ["retencion_ieps", "Ret. IEPS", "moneda"],
  ["retencion_isr", "Ret. ISR", "moneda"], ["traslado_iva", "Tras. IVA", "moneda"], ["traslado_ieps", "Tras. IEPS", "moneda"],
  ["traslado_isr", "Tras. ISR", "moneda"], ["total_retenciones", "Total ret.", "moneda"], ["subtotal", "Subtotal", "moneda"],
  ["descuento", "Descuento", "moneda"], ["neto", "Neto", "moneda"], ["total", "Total", "moneda"],
].map(([clave, etiqueta, formato]) => ({ clave, etiqueta, formato }) as CfdiCifra);

const cifrasNomina: CfdiCifra[] = [
  ["conteo", "CFDI", "entero"], ["empleados", "Empleados", "entero"], ["sueldos", "Sueldos", "moneda"],
  ["gravado", "Gravado", "moneda"], ["subsidio_causado", "Subsidio causado", "moneda"],
].map(([clave, etiqueta, formato]) => ({ clave, etiqueta, formato }) as CfdiCifra);

const fila = (nombre: string) => screen.getByRole("row", { name: new RegExp(`^${nombre}`) });

describe("CfdiTotales", () => {
  it("muestra los renglones Periodo y Acumulado", () => {
    render(<CfdiTotales cifras={cifrasComprobante} totales={{ periodo: con, acumulado: { ...con, conteo: 4200 } }} />);

    expect(within(fila("Periodo")).getByText("507")).toBeInTheDocument();
    expect(within(fila("Acumulado")).getByText("4,200")).toBeInTheDocument();
  });

  it("da formato de moneda a los importes", () => {
    render(<CfdiTotales cifras={cifrasComprobante} totales={{ periodo: con, acumulado: con }} />);

    const periodo = fila("Periodo");
    expect(within(periodo).getByText("$9,500.00")).toBeInTheDocument(); // neto
    expect(within(periodo).getByText("$11,100.00")).toBeInTheDocument(); // total
    expect(within(periodo).getByText("$125.50", { selector: "td:nth-child(5)" })).toBeInTheDocument(); // retención ISR
  });

  it("sin CFDI muestra guiones, nunca ceros", () => {
    render(<CfdiTotales cifras={cifrasComprobante} totales={{ periodo: vacio, acumulado: vacio }} />);

    const periodo = fila("Periodo");
    expect(within(periodo).getAllByText("—")).toHaveLength(11);
    expect(within(periodo).queryByText(/\$0\.00/)).not.toBeInTheDocument();
    expect(within(periodo).getByText("0")).toBeInTheDocument(); // el conteo sí es 0
  });

  it("un importe en cero con CFDI sí se muestra como $0.00", () => {
    render(<CfdiTotales cifras={cifrasComprobante} totales={{ periodo: con, acumulado: con }} />);

    expect(within(fila("Periodo")).getAllByText("$0.00").length).toBeGreaterThan(0);
  });

  it("mientras carga muestra un indicador", () => {
    render(<CfdiTotales cifras={undefined} totales={undefined} />);

    expect(screen.getByRole("status", { name: "Cargando totales" })).toBeInTheDocument();
  });

  it("tiene los encabezados de todas las cifras", () => {
    render(<CfdiTotales cifras={cifrasComprobante} totales={{ periodo: con, acumulado: con }} />);

    const encabezados = screen.getAllByRole("columnheader").map((h) => h.textContent);
    expect(encabezados).toEqual([
      "", "CFDI", "Ret. IVA", "Ret. IEPS", "Ret. ISR", "Tras. IVA", "Tras. IEPS", "Tras. ISR",
      "Total ret.", "Subtotal", "Descuento", "Neto", "Total",
    ]);
  });

  it("Nómina muestra sus propias cifras y da formato entero al número de empleados", () => {
    const nomina: CfdiTotalesBloque = { conteo: 33, empleados: 31, sueldos: 250000.5, gravado: 240000, subsidio_causado: null };
    render(<CfdiTotales cifras={cifrasNomina} totales={{ periodo: nomina, acumulado: nomina }} />);

    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(
      ["", "CFDI", "Empleados", "Sueldos", "Gravado", "Subsidio causado"]);
    const periodo = fila("Periodo");
    expect(within(periodo).getByText("31")).toBeInTheDocument();                 // entero, sin signo de pesos
    expect(within(periodo).getByText("$250,000.50")).toBeInTheDocument();
    expect(within(periodo).getByText("—")).toBeInTheDocument();                  // sin dato: guion
  });

  it("respeta el orden y las cifras ocultas de la preferencia, sobre las del tipo activo", () => {
    const nomina: CfdiTotalesBloque = { conteo: 1, empleados: 1, sueldos: 10, gravado: 5, subsidio_causado: 2 };
    render(
      <CfdiTotales
        cifras={cifrasNomina}
        totales={{ periodo: nomina, acumulado: nomina }}
        preferencia={[{ clave: "gravado", visible: true }, { clave: "empleados", visible: false }, { clave: "sueldos", visible: true }]}
      />,
    );

    expect(screen.getAllByRole("columnheader").map((h) => h.textContent)).toEqual(
      ["", "CFDI", "Gravado", "Sueldos", "Subsidio causado"]);
  });
});
