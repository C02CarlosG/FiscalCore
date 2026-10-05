import type { DiotFlujo, DiotTercero } from "@/types/api";

const bases = { "16": 0, "8": 0, "0": 0, exento: 0, otras: 0, no_objeto: 0 };
const iva = { "16": 0, "8": 0, otras: 0, total: 0 };

export const tercero = (parche: Partial<DiotTercero> = {}): DiotTercero => ({
  contraparte_rfc: "PRO010101AAA",
  contraparte: "PROVEEDOR UNO",
  proveedor_id: "p1",
  tipo_tercero: "04",
  tipo_operacion: "85",
  pais: null,
  id_fiscal: null,
  cfdi: 2,
  actos: { ...bases, "16": 1500 },
  iva_pagado: { ...iva, "16": 240, total: 240 },
  devoluciones: { base: 100, iva: 16 },
  iva_acreditable: 224,
  iva_no_acreditable: { proporcion: 0, total: 0, por_motivo: {} },
  retenciones: 0,
  advertencias: [],
  ...parche,
});

export const diotFlujo = (parche: Partial<DiotFlujo> = {}): DiotFlujo => ({
  empresa_id: "e1",
  periodo: "2026-09",
  factor_prorrateo: 1,
  terceros: [tercero()],
  totales: {
    terceros: 1, cfdi: 2, valor_de_actos: 1500, iva_pagado: 240, devoluciones_iva: 16,
    iva_acreditable: 224, iva_no_acreditable: 0, con_advertencias: 0,
  },
  cuadre_con_iva: { iva_acreditable_diot: 224, iva_acreditable_resumen: 224, cuadra: true },
  advertencias: [],
  advertencias_iva: [],
  operaciones_por_cfdi: 0,
  ...parche,
});
