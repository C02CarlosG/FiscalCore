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
  /** Ausente en respuestas de versiones anteriores del servidor. */
  rol?: "admin" | "contador";
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

export interface IngestaResponse {
  mensaje: string;
  registros_procesados: number;
  errores: string[];
  periodo: string;
}

export interface ConciliacionResumen {
  total: number;
  exacto: number;
  parcial: number;
  sin_cfdi: number;
  sin_movimiento: number;
  pct_conciliado: number;
}

export interface ParConciliacion {
  id: string;
  tipo_match: "sin_cfdi" | "parcial";
  monto_movimiento: number | null;
  monto_cfdi: number | null;
  diferencia: number | null;
  porcentaje_match: number | null;
  periodo: string;
  movimiento_id: string | null;
  mov_fecha: string | null;
  concepto: string | null;
  mov_monto: number | null;
  mov_tipo: string | null;
  rfc_detectado: string | null;
}

export interface ConciliacionesAccionables {
  total: number;
  pares: ParConciliacion[];
}

export interface FielEstado {
  tiene_fiel: boolean;
  rfc_certificado?: string | null;
  vigencia_fin?: string | null;
  dias_restantes?: number | null;
  vencida?: boolean;
  por_vencer?: boolean;
  guardada_el?: string | null;
}

export type SatTipoDescarga = "emitidos" | "recibidos" | "ambos";

export interface SatSolicitud {
  id: string;
  tipo: "emitidos" | "recibidos";
  periodo_inicio: string;
  periodo_fin: string;
  estado: string;
  num_cfdi: number | null;
  cfdi_importados: number | null;
  error_msg: string | null;
  created_at: string;
  updated_at: string;
}

export interface SatAvanzarResponse {
  avanzadas: { id: string; estado: string }[];
}

export interface SatSyncResponse {
  mensaje: string;
  solicitudes: { id: string; tipo: string }[];
  periodo: string;
  tipos: string[];
  // Tipos que el SAT rechazó cuando otro sí se aceptó ("emitidos: …").
  errores?: string[];
}

// ─── Listado unificado de CFDI (F3) ──────────────────────────────────────────

export type CfdiTipoComprobante = "I" | "E" | "T" | "N" | "P";

export interface CfdiColumna {
  clave: string;
  etiqueta: string;
  tipo_dato: "texto" | "fecha" | "fecha_hora" | "moneda" | "numero" | "booleano" | "catalogo" | "lista";
  grupo: "encabezado" | "concepto";
  visible_por_defecto: boolean;
  ordenable: boolean;
  filtrable: boolean;
  opciones: string[];
}

export interface CfdiColumnasResponse {
  encabezado: CfdiColumna[];
  concepto: CfdiColumna[];
}

export type CfdiValor = string | number | boolean | null | string[];

/** Una fila del listado: trae todas las columnas del catálogo, no solo las visibles. */
export type CfdiFila = Record<string, CfdiValor>;

export interface CfdiListadoResponse {
  items: CfdiFila[];
  total: number;
  pagina: number;
  por_pagina: number;
}

/** Cifras en pesos. Sin CFDI en el periodo, `conteo` es 0 y las demás van en null. */
export interface CfdiTotalesBloque {
  conteo: number;
  retencion_iva: number | null;
  retencion_ieps: number | null;
  retencion_isr: number | null;
  traslado_iva: number | null;
  traslado_ieps: number | null;
  traslado_isr: number | null;
  total_retenciones: number | null;
  subtotal: number | null;
  descuento: number | null;
  neto: number | null;
  total: number | null;
}

export interface CfdiAdvertencia {
  tipo: string;
  uuid_factura: string;
  mensaje: string;
}

export interface CfdiResumenResponse {
  conteos: Record<CfdiTipoComprobante, number>;
  totales: { periodo: CfdiTotalesBloque; acumulado: CfdiTotalesBloque };
  advertencias: CfdiAdvertencia[];
}

export interface PeriodosResponse {
  periodos: string[];
}

/** Concepto del detalle: importes como número y los impuestos desplegados por columna. */
export type CfdiConcepto = Record<string, string | number | null>;

export interface CfdiParte {
  rfc: string;
  nombre: string | null;
  regimen: string | null;
  regimen_desc: string | null;
  domicilio_fiscal?: string | null;
}

export interface CfdiImpuestoDetalle {
  ambito: "traslado" | "retencion";
  impuesto: string;
  tipo_factor: string;
  tasa_o_cuota: number | null;
  base: number | null;
  importe: number | null;
}

export interface CfdiPagoDetalle {
  uuid_pago: string;
  fecha_pago: string;
  parcialidad: number | null;
  importe_pagado: number | null;
  saldo_anterior: number | null;
  saldo_restante: number | null;
}

export interface CfdiRelacionado {
  tipo_relacion: string;
  descripcion: string | null;
  uuids: string[];
}

export interface CfdiDetalle {
  encabezado: Record<string, string | number | null>;
  emisor: CfdiParte;
  receptor: CfdiParte;
  impuestos: CfdiImpuestoDetalle[];
  conceptos: CfdiConcepto[];
  total_conceptos: number;
  pagos: CfdiPagoDetalle[];
  relacionados: CfdiRelacionado[];
  tiene_xml: boolean;
}

// ── Inicio (F4) ──────────────────────────────────────────────────────────────

export interface InicioIngresos {
  facturado: number;
  notas_credito: number;
  neto: number;
  cfdi: number;
}

export interface InicioGastos extends InicioIngresos {
  nomina: number;
}

export interface InicioMes {
  periodo: string;
  ingresos: InicioIngresos;
  gastos: { neto: number };
}

export interface InicioResumen {
  empresa_id: string;
  periodo: string;
  ejercicio: number;
  ingresos: { periodo: InicioIngresos; acumulado: InicioIngresos };
  gastos: { periodo: InicioGastos; acumulado: InicioGastos };
  meses: InicioMes[];
}

export interface InicioIvaMes {
  periodo: string;
  trasladado: { pue: number; ppd: number; notas_credito: number; total: number };
  acreditable: {
    pue: number;
    ppd: number;
    notas_credito: number;
    excluido_efectivo: number;
    bruto: number;
    ajustado: number;
  };
  resultado: { iva_retenido: number; iva_por_pagar: number; saldo_a_cargo: number; saldo_a_favor: number };
}

export interface InicioIvaAnual {
  empresa_id: string;
  ejercicio: number;
  factor_prorrateo: number;
  iva_retenido_incluido: boolean;
  meses: InicioIvaMes[];
  totales: { trasladado: number; acreditable: number; iva_retenido: number; iva_por_pagar: number };
}
