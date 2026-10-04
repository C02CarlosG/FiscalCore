import type { IvaBases, IvaBloque, IvaDireccionResumen, IvaFlujoResumen, IvaMontos, IvaRenglon } from "@/types/api";

const bases = (extra: Partial<IvaBases> = {}): IvaBases => ({ "16": 0, "8": 0, "0": 0, exento: 0, otras: 0, no_objeto: 0, ...extra });
const montos = (extra: Partial<IvaMontos> = {}): IvaMontos => ({ "16": 0, "8": 0, otras: 0, total: 0, ...extra });

export const bloque = (extra: Partial<IvaBloque> = {}): IvaBloque => ({
  cfdi: 0, pagos: 0, bases: bases(), iva: montos(), retenciones: 0, total: 0, ...extra,
});

export const direccionResumen = (extra: Partial<IvaDireccionResumen> = {}): IvaDireccionResumen => ({
  origenes: {
    contado: bloque({ cfdi: 153, pagos: 153, bases: bases({ "16": 14_220_000, "8": 500, "0": 300, exento: 200 }), iva: montos({ "16": 2_275_262.33, "8": 40, total: 2_275_302.33 }), total: 2_275_302.33 }),
    credito: bloque({ cfdi: 80, pagos: 95, bases: bases({ "16": 5_719_000 }), iva: montos({ "16": 915_100.15, total: 915_100.15 }), total: 915_100.15 }),
    notas_credito: bloque({ cfdi: 3, pagos: 3, iva: montos({ "16": 368, total: 368 }), total: 368 }),
  },
  total: bloque({
    cfdi: 233, pagos: 251,
    bases: bases({ "16": 19_939_000, "8": 500, "0": 300, exento: 200, no_objeto: 700, otras: 10 }),
    iva: montos({ "16": 3_190_000, "8": 40, otras: 1.6, total: 3_190_362.48 }),
    retenciones: 3_786.75, total: 3_190_362.48,
  }),
  no_considerados: { cfdi: 134, iva: 816 },
  reasignados: { cfdi: 2, iva: 800 },
  ...extra,
});

export const resumenIva = (extra: Partial<IvaFlujoResumen> = {}): IvaFlujoResumen => ({
  empresa_id: "e1",
  periodo: "2026-09",
  factor_prorrateo: 1,
  trasladado: direccionResumen(),
  acreditable: direccionResumen({
    total: bloque({ cfdi: 40, pagos: 40, iva: montos({ total: 2_162_403.41 }), total: 2_162_403.41, retenciones: 26.67 }),
    ajustado: 2_162_403.41,
    retenciones_no_acreditables: 26.67,
  }),
  retenciones_a_enterar: 53.34,
  resultado: {
    trasladado: 3_190_362.48, acreditable: 2_162_403.41, retenciones_a_favor: 3_786.75,
    iva_por_pagar: 1_024_172.32, saldo_a_cargo: 1_024_172.32, saldo_a_favor: 0,
  },
  advertencias: [
    { codigo: "pago_v1", mensaje: "Hay cobros o pagos con complemento de pago versión 1.0: su IVA se aproxima.", cfdi: 2 },
  ],
  ...extra,
});

export const renglon = (extra: Partial<IvaRenglon> = {}): IvaRenglon => ({
  uuid: "1F3A0001-0000-4000-8000-000000000000",
  tipo_comprobante: "I",
  fecha_emision: "2026-09-10T10:00:00",
  fecha_efecto: "2026-09-10T10:00:00",
  fecha_pago: null,
  uuid_pago: null,
  parcialidad: null,
  origen: "contado",
  contraparte_rfc: "XAXX010101000",
  contraparte: "CLIENTE SA",
  bases: bases({ "16": 1000, "8": 500, exento: 200 }),
  iva: montos({ "16": 160, "8": 40, total: 200 }),
  retencion: 0,
  iva_total: 200,
  total_documento: 1900,
  marcas: [],
  motivo: null,
  ajuste: null,
  ...extra,
});
