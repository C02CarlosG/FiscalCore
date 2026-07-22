export interface EmpresaResumen {
  empresa_id: string;
  rfc: string;
  razon_social: string;
  regimen_fiscal: string | null;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  user_id: string;
  email: string;
  nombre: string | null;
  empresas: EmpresaResumen[];
}

export interface Empresa {
  id: string;
  rfc: string;
  razon_social: string;
  regimen_fiscal: string | null;
  cp_fiscal: string | null;
  curp: string | null;
  obligaciones: string[] | null;
  representante_legal: string | null;
  rfc_representante: string | null;
  activo: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgregarEmpresaRequest {
  rfc: string;
  razon_social: string;
  regimen_fiscal?: string;
  cp_fiscal?: string;
  curp?: string;
  obligaciones?: string[];
  representante_legal?: string;
  rfc_representante?: string;
}

export interface AgregarEmpresaResponse {
  mensaje: string;
  empresa_id: string;
  rfc: string;
  razon_social: string;
}

export interface RiesgoAbierto {
  id: string;
  codigo: string;
  nombre: string;
  severidad: "critico" | "alto" | "medio" | "bajo";
  monto_afectado: number | null;
  descripcion: string | null;
  cfdi_id: string | null;
  movimiento_id: string | null;
  estado: string;
  periodo: string;
  created_at: string;
}

export interface ResumenRiesgos {
  critico: number;
  alto: number;
  medio: number;
  bajo: number;
  monto_total_en_riesgo: number;
}

export interface Indicadores {
  ingresos_cfdi?: number;
  egresos_cfdi?: number;
  depositos_banco?: number;
  cargos_banco?: number;
  brecha_ingresos?: number;
  brecha_egresos?: number;
  pct_conciliacion?: number;
}

export interface TendenciaScore {
  periodo: string;
  score: number;
}

export interface DashboardData {
  empresa: Empresa;
  score_actual: Record<string, unknown> | null;
  riesgos_abiertos: RiesgoAbierto[];
  resumen_riesgos: ResumenRiesgos;
  tendencia_score: TendenciaScore[];
  indicadores: Indicadores;
}

export interface IvaDesglose {
  base: number;
  iva: number;
}

export interface TrasladadoIva {
  pue: IvaDesglose;
  ppd: { cobrado: number; iva: number };
  notas_credito: IvaDesglose;
  total: number;
}

export interface AcreditableIva {
  pue: IvaDesglose;
  ppd: { pagado: number; iva: number };
  notas_credito: IvaDesglose;
  excluido_efectivo: { iva: number };
  bruto: number;
  factor_prorrateo: number;
  ajustado: number;
}

export interface ResultadoIva {
  iva_por_pagar: number;
  saldo_a_cargo: number;
  saldo_a_favor: number;
}

export interface ComparativoSat {
  diot_iva_pagado: number;
  diferencia: number;
}

export interface CedulaIva {
  empresa_id: string;
  periodo: string;
  trasladado: TrasladadoIva;
  acreditable: AcreditableIva;
  iva_retenido: number;
  resultado: ResultadoIva;
  comparativo_sat: ComparativoSat;
}
