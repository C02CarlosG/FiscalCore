import type { IsrBloqueResumen, IsrFlujoResumen, IsrRenglon } from "@/types/api";

const fuera = { cfdi: 0, base: 0, por_motivo: {} };

export function bloqueIsr(extra: Partial<IsrBloqueResumen> = {}): IsrBloqueResumen {
  return {
    ingresos: { contado: 1000, credito: 500, devoluciones: 100, total: 1400, cfdi: 3, retenciones_a_favor: 40, no_considerados: fuera },
    deducciones: {
      contado: 300, credito: 0, devoluciones_recibidas: 0, compras_y_gastos: 300,
      nomina: { gravado: 800, exento: 200, porcentaje_exento: 0.47, exento_deducible: 94, deducible: 894, excluido_ptu: 0, excluido_viaticos: 0 },
      total: 1194, inversiones: { cfdi: 0, base: 0 }, cfdi: 2, no_considerados: fuera,
    },
    retenciones_a_cargo: { trabajadores: 100, proveedores: 0, total: 100 },
    utilidad_fiscal_estimada: 206,
    ...extra,
  };
}

export function resumenIsr(extra: Partial<IsrFlujoResumen> = {}): IsrFlujoResumen {
  return {
    empresa_id: "e1", periodo: "2026-09",
    regimen: { codigo: "612", modulo: "flujo", avisos: [] },
    porcentaje_nomina_exenta: 0.47,
    mes: bloqueIsr(),
    acumulado: bloqueIsr({ utilidad_fiscal_estimada: 999 }),
    advertencias: [],
    ...extra,
  };
}

export function renglonIsr(extra: Partial<IsrRenglon> = {}): IsrRenglon {
  return {
    uuid: "AAAAAAAA-1111-2222-3333-444444444444", tipo_comprobante: "I", fecha_emision: "2026-09-10", fecha_efecto: "2026-09-10",
    uuid_pago: null, origen: "contado", contraparte_rfc: "XAXX010101000", contraparte: "CLIENTE", base: 1000, retencion: 0,
    marcas: [], motivo: null, nomina: null, ...extra,
  };
}
