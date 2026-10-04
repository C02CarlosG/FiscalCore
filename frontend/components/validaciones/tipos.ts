export type DireccionValidacion = "emitidos" | "recibidos";
export type AlcanceValidacion = "periodo" | "acumulado";
export type ClaveValidacion = "pue_forma_99" | "pue_con_rep" | "egreso_sin_relacion" | "no_bancarizado";

export interface TarjetaValidacion {
  clave: ClaveValidacion;
  titulo: string;
  descripcion: string;
  activa: boolean;
  periodo: number | null;
  acumulado: number | null;
}

export interface ConfiguracionValidaciones {
  inactivas: ClaveValidacion[];
  umbral_efectivo: string;
}

export interface ResumenValidaciones {
  periodo: string;
  configuracion: ConfiguracionValidaciones;
  emitidos: TarjetaValidacion[];
  recibidos: TarjetaValidacion[];
}

export interface CfdiValidacion {
  uuid: string;
  fecha_emision: string;
  serie: string | null;
  folio: string | null;
  rfc: string;
  nombre: string | null;
  total: number;
  moneda: string;
  forma_pago: string | null;
  metodo_pago: string | null;
  tipo_comprobante: string;
}

export interface ListaCfdiValidacion {
  cfdis: CfdiValidacion[];
  total_filas: number;
}

export const TITULO_DIRECCION: Record<DireccionValidacion, string> = {
  emitidos: "Emitidos",
  recibidos: "Recibidos",
};

export function rutaValidaciones(empresaId: string): string {
  return `/api/v1/validaciones-cfdi/empresas/${empresaId}`;
}
