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

/** Lo que el motor dejó fuera de la cifra (efectivo, uso sin efectos, ajustes) o movió a otro periodo. */
export interface IvaFueraDeCifra {
  cfdi: number;
  iva: number;
  por_motivo?: Record<string, { cfdi: number; iva: number }>;
}

export interface TrasladadoIva {
  pue: IvaDesglose;
  ppd: { cobrado: number; iva: number };
  notas_credito: IvaDesglose;
  total: number;
  no_considerados: IvaFueraDeCifra;
  reasignados: IvaFueraDeCifra;
}

export interface AcreditableIva {
  pue: IvaDesglose;
  ppd: { pagado: number; iva: number };
  notas_credito: IvaDesglose;
  excluido_efectivo: { iva: number };
  no_considerados: IvaFueraDeCifra;
  reasignados: IvaFueraDeCifra;
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
  /** Retenciones de IVA que la empresa hizo a terceros y debe enterar. */
  retenciones_a_enterar: number;
  resultado: ResultadoIva;
  comparativo_sat: ComparativoSat;
  advertencias: InicioAdvertencia[];
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

export interface EtiquetaCfdi {
  id: string;
  nombre: string;
  color: string;
}

export interface Etiqueta extends EtiquetaCfdi {
  cfdis: number;
}

export interface ComentarioCfdi {
  id: string;
  texto: string;
  creado: string;
  autor: string | null;
  puede_borrar: boolean;
}

export interface EvidenciaCfdi {
  id: string;
  nombre: string;
  tipo: string;
  tamano: number;
  creado: string;
  autor: string | null;
  puede_borrar: boolean;
}

export interface EtiquetadoLoteResponse {
  cfdis: number;
  agregados: number;
  quitados: number;
}

export type CfdiValor = string | number | boolean | null | string[] | EtiquetaCfdi[];

/** Una fila del listado: trae todas las columnas del catálogo, no solo las visibles. */
export type CfdiFila = Record<string, CfdiValor>;

export interface CfdiListadoResponse {
  items: CfdiFila[];
  total: number;
  pagina: number;
  por_pagina: number;
}

/** Una cifra de la tabla de totales: cada tipo de comprobante trae las suyas. */
export interface CfdiCifra {
  clave: string;
  etiqueta: string;
  formato: "entero" | "moneda";
}

/** Cifras en pesos del periodo o del acumulado, por clave. Sin CFDI, `conteo` es 0 y las demás van en null. */
export type CfdiTotalesBloque = { conteo: number } & Record<string, number | null>;

export interface CfdiAdvertencia {
  tipo: string;
  uuid_factura: string;
  mensaje: string;
}

export interface CfdiResumenResponse {
  conteos: Record<CfdiTipoComprobante, number>;
  /** Cifras del tipo activo, en el orden en que se muestran (la primera es el conteo). */
  cifras: CfdiCifra[];
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
  totales: { trasladado: number; acreditable: number; iva_retenido: number; total_a_cargo: number; total_a_favor: number };
  advertencias: InicioAdvertencia[];
}

/** Limitación del cálculo; `cfdi` es null cuando no depende de los datos del ejercicio. */
export interface InicioAdvertencia {
  codigo: string;
  mensaje: string;
  cfdi: number | null;
}

// ── IVA base flujo (F5.2) ────────────────────────────────────────────────────

export type IvaDireccion = "trasladado" | "acreditable";
export type IvaOrigen = "contado" | "credito" | "notas_credito";
export type IvaOrigenDetalle = IvaOrigen | "no_considerados" | "reasignados";

export interface IvaBases {
  "16": number;
  "8": number;
  "0": number;
  exento: number;
  otras: number;
  no_objeto: number;
}

export interface IvaMontos {
  "16": number;
  "8": number;
  otras: number;
  total: number;
}

export interface IvaBloque {
  cfdi: number;
  pagos: number;
  bases: IvaBases;
  iva: IvaMontos;
  retenciones: number;
  total: number;
}

export interface IvaDireccionResumen {
  origenes: Record<IvaOrigen, IvaBloque>;
  total: IvaBloque;
  no_considerados: { cfdi: number; iva: number };
  reasignados: { cfdi: number; iva: number };
  /** Solo en acreditable: el IVA multiplicado por el factor de prorrateo. */
  ajustado?: number;
  retenciones_no_acreditables?: number;
}

export interface IvaFlujoResumen {
  empresa_id: string;
  periodo: string;
  factor_prorrateo: number;
  trasladado: IvaDireccionResumen;
  acreditable: IvaDireccionResumen;
  retenciones_a_enterar: number;
  resultado: {
    trasladado: number;
    acreditable: number;
    retenciones_a_favor: number;
    iva_por_pagar: number;
    saldo_a_cargo: number;
    saldo_a_favor: number;
  };
  advertencias: InicioAdvertencia[];
}

export interface IvaAjuste {
  accion: "excluir" | "reasignar";
  periodo_destino: string | null;
  motivo: string;
}

export interface IvaRenglon {
  uuid: string;
  tipo_comprobante: string;
  fecha_emision: string | null;
  fecha_efecto: string | null;
  fecha_pago: string | null;
  uuid_pago: string | null;
  parcialidad: number | null;
  origen: IvaOrigen;
  contraparte_rfc: string | null;
  contraparte: string | null;
  bases: IvaBases;
  iva: IvaMontos;
  retencion: number;
  iva_total: number;
  total_documento: number;
  marcas: string[];
  motivo: string | null;
  ajuste: IvaAjuste | null;
}

export interface IvaDetalle {
  items: IvaRenglon[];
  total: number;
  pagina: number;
  por_pagina: number;
}

// ── DIOT por flujo (F6.2) ─────────────────────────────────────────────────────

export interface DiotTercero {
  contraparte_rfc: string;
  contraparte: string;
  proveedor_id: string | null;
  tipo_tercero: string | null;
  tipo_operacion: string | null;
  pais: string | null;
  id_fiscal: string | null;
  cfdi: number;
  /** Valor de actos pagados por tasa; incluye «exento» y «no_objeto». */
  actos: IvaBases;
  iva_pagado: IvaMontos;
  devoluciones: { base: number; iva: number };
  iva_acreditable: number;
  iva_no_acreditable: {
    proporcion: number;
    total: number;
    por_motivo: Record<string, { cfdi: number; iva: number; base: number }>;
  };
  retenciones: number;
  advertencias: string[];
}

export interface DiotTotales {
  terceros: number;
  cfdi: number;
  valor_de_actos: number;
  iva_pagado: number;
  devoluciones_iva: number;
  iva_acreditable: number;
  iva_no_acreditable: number;
  con_advertencias: number;
}

export interface DiotFlujo {
  empresa_id: string;
  periodo: string;
  factor_prorrateo: number;
  terceros: DiotTercero[];
  totales: DiotTotales;
  cuadre_con_iva: { iva_acreditable_diot: number; iva_acreditable_resumen: number; cuadra: boolean };
  /** Avisos del periodo (p. ej. actos a 8 % sin región). */
  advertencias: { codigo: string; mensaje: string }[];
  advertencias_iva: InicioAdvertencia[];
  operaciones_por_cfdi: number;
}

// ── ISR base flujo (F7.2) ────────────────────────────────────────────────────

export type IsrLado = "ingreso" | "deduccion";
export type IsrBloque = "contado" | "credito" | "devoluciones" | "nomina" | "inversiones" | "no_considerados";

export interface IsrFuera {
  cfdi: number;
  base: number;
  por_motivo: Record<string, { cfdi: number; base: number }>;
}

export interface IsrIngresos {
  contado: number;
  credito: number;
  devoluciones: number;
  total: number;
  cfdi: number;
  retenciones_a_favor: number;
  no_considerados: IsrFuera;
}

export interface IsrNomina {
  gravado: number;
  exento: number;
  porcentaje_exento: number;
  exento_deducible: number;
  deducible: number;
  excluido_ptu: number;
  excluido_viaticos: number;
}

export interface IsrDeducciones {
  contado: number;
  credito: number;
  devoluciones_recibidas: number;
  compras_y_gastos: number;
  nomina: IsrNomina;
  total: number;
  inversiones: { cfdi: number; base: number };
  cfdi: number;
  no_considerados: IsrFuera;
}

export interface IsrBloqueResumen {
  ingresos: IsrIngresos;
  deducciones: IsrDeducciones;
  retenciones_a_cargo: { trabajadores: number; proveedores: number; total: number };
  utilidad_fiscal_estimada: number;
}

export interface IsrFlujoResumen {
  empresa_id: string;
  periodo: string;
  regimen: { codigo: string | null; modulo: "flujo" | "coeficiente" | "no_soportado"; avisos: string[] };
  porcentaje_nomina_exenta: number;
  mes: IsrBloqueResumen;
  acumulado: IsrBloqueResumen;
  advertencias: InicioAdvertencia[];
}

export interface IsrRenglon {
  uuid: string;
  tipo_comprobante: string;
  fecha_emision: string | null;
  fecha_efecto: string | null;
  uuid_pago: string | null;
  origen: string;
  contraparte_rfc: string | null;
  contraparte: string | null;
  base: number;
  retencion: number;
  marcas: string[];
  motivo: string | null;
  nomina: { gravado: number; exento: number; ptu: number; viaticos: number } | null;
}

export interface IsrDetalle {
  items: IsrRenglon[];
  total: number;
  pagina: number;
  por_pagina: number;
}
