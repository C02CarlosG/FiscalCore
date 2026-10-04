import type { InicioIvaAnual, InicioMes, InicioResumen } from "@/types/api";

export const MESES_12: string[] = [
  "2025-10", "2025-11", "2025-12", "2026-01", "2026-02", "2026-03",
  "2026-04", "2026-05", "2026-06", "2026-07", "2026-08", "2026-09",
];

/** Serie de 12 meses terminando en 2026-09; el neto de ingresos de cada mes es 1000 × (posición + 1). */
export const meses = (): InicioMes[] =>
  MESES_12.map((periodo, i) => ({
    periodo,
    ingresos: { facturado: 1000 * (i + 1) + 100, notas_credito: 100, neto: 1000 * (i + 1), cfdi: i + 1 },
    gastos: { neto: 500 * (i + 1) },
  }));

export const resumen = (extra: Partial<InicioResumen> = {}): InicioResumen => ({
  empresa_id: "e1",
  periodo: "2026-09",
  ejercicio: 2026,
  ingresos: {
    periodo: { facturado: 21_407_798.4, notas_credito: 0, neto: 21_407_798.4, cfdi: 153 },
    acumulado: { facturado: 216_844_592.64, notas_credito: 0, neto: 216_844_592.64, cfdi: 1500 },
  },
  gastos: {
    periodo: { facturado: 12_803_855.07, notas_credito: 0, neto: 12_803_855.07, cfdi: 90, nomina: 2_195_408.04 },
    acumulado: { facturado: 100_000, notas_credito: 0, neto: 100_000, cfdi: 900, nomina: 0 },
  },
  meses: meses(),
  ...extra,
});

const ceros = { pue: 0, ppd: 0, notas_credito: 0, total: 0 };

export const ivaAnual = (): InicioIvaAnual => ({
  empresa_id: "e1",
  ejercicio: 2026,
  factor_prorrateo: 1,
  iva_retenido_incluido: false,
  meses: Array.from({ length: 12 }, (_, i) => {
    const traslado = 160 * (i + 1);
    const acred = 100 * (i + 1);
    return {
      periodo: `2026-${String(i + 1).padStart(2, "0")}`,
      trasladado: { ...ceros, pue: traslado, total: traslado },
      acreditable: { pue: acred, ppd: 0, notas_credito: 0, excluido_efectivo: 5, bruto: acred, ajustado: acred },
      resultado: {
        iva_retenido: 0,
        iva_por_pagar: traslado - acred,
        saldo_a_cargo: traslado - acred,
        saldo_a_favor: 0,
      },
    };
  }),
  totales: { trasladado: 160 * 78, acreditable: 100 * 78, iva_retenido: 0, iva_por_pagar: 60 * 78 },
});
