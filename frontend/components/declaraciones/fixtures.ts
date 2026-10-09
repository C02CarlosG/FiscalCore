import type { ComparativoDeclarado, Declaracion, ImpuestoComparado } from "@/types/api";

export const declaracion = (extra: Partial<Declaracion> = {}): Declaracion => ({
  periodo: "2026-09", impuesto: "iva", secuencia: 1, tipo: "normal", fecha_presentacion: "2026-10-17", numero_operacion: "OP-1",
  ingresos: null, deducciones: null, impuesto_trasladado: 160, impuesto_acreditable: null, retenciones: null,
  retenciones_a_terceros: null, saldo_a_favor_aplicado: null, impuesto_a_cargo: 150, monto_pagado: 100, notas: "", updated_at: "2026-10-17T10:00:00", ...extra,
});

export const impuestoComparado = (extra: Partial<ImpuestoComparado> = {}): ImpuestoComparado => ({
  impuesto: "iva", estado: "con_diferencias", declaracion: declaracion(), declaraciones: 1, pendiente_de_pago: 50,
  renglones: [
    { clave: "impuesto_trasladado", etiqueta: "IVA trasladado cobrado", declarado: 160, calculado: 160, diferencia: 0, estado: "cuadra" },
    { clave: "impuesto_a_cargo", etiqueta: "IVA a cargo (+) o a favor (−), después del saldo a favor aplicado", declarado: 150, calculado: 160, diferencia: -10, estado: "diferencia" },
    { clave: "retenciones", etiqueta: "Retenciones de IVA a favor", declarado: null, calculado: 0, diferencia: null, estado: "sin_captura" },
  ],
  ...extra,
});

export const comparativo = (extra: Partial<ComparativoDeclarado> = {}): ComparativoDeclarado => ({
  empresa_id: "e1", periodo: "2026-09", factor_prorrateo: 1,
  iva: impuestoComparado(),
  isr: impuestoComparado({
    impuesto: "isr", estado: "sin_declaracion", declaracion: null, declaraciones: 0, pendiente_de_pago: null,
    renglones: [{ clave: "ingresos", etiqueta: "Ingresos acumulables", declarado: null, calculado: 1000, diferencia: null, estado: "sin_captura" }],
  }),
  aviso: "El pago provisional del ISR no se calcula: se muestra solo lo declarado.", ...extra,
});
