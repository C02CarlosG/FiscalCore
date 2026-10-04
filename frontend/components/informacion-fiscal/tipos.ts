export type TipoDocumentoFiscal = "constancia" | "opinion";

export type SentidoOpinion =
  | "positivo"
  | "negativo"
  | "suspension_actividades"
  | "inscrito_sin_obligaciones"
  | "no_inscrito";

/** Por qué una opinión no está vigente (solo la positiva tiene vigencia, regla 2.1.36 RMF). */
export type MotivoNoVigente = "sentido_no_positivo" | "sentido_no_identificado" | "sin_fecha" | "vencida";

export interface DatosConstancia {
  razon_social?: string | null;
  regimenes?: string[];
  obligaciones?: { descripcion: string; periodicidad: string }[];
  cp_fiscal?: string | null;
  curp?: string | null;
  id_cif?: string | null;
  estatus_padron?: string | null;
}

export interface DatosOpinion {
  razon_social?: string | null;
  sentido?: SentidoOpinion | null;
  folio?: string | null;
}

export interface DocumentoFiscal {
  id: string;
  tipo: TipoDocumentoFiscal;
  nombre_archivo: string;
  tamano_bytes: number;
  rfc: string;
  fecha_emision: string | null;
  created_at: string;
  datos: DatosConstancia & DatosOpinion;
  antiguedad_dias: number | null;
  vigente_hasta: string | null;
  vigente: boolean | null;
  motivo: MotivoNoVigente | null;
}

export interface ResumenInformacionFiscal {
  constancia: DocumentoFiscal | null;
  opinion: DocumentoFiscal | null;
}

export const TITULO_DOCUMENTO: Record<TipoDocumentoFiscal, string> = {
  constancia: "Constancia de situación fiscal",
  opinion: "Opinión de cumplimiento",
};

/** Mismo tope que el backend (`informacion_fiscal.MAX_BYTES`). */
export const MAX_BYTES_PDF = 5 * 1024 * 1024;

export function rutaInformacionFiscal(empresaId: string): string {
  return `/api/v1/informacion-fiscal/empresas/${empresaId}`;
}

export function rutaPdf(empresaId: string, documentoId: string, descargar = false): string {
  const base = `${rutaInformacionFiscal(empresaId)}/documentos/${documentoId}/pdf`;
  return descargar ? `${base}?descargar=true` : base;
}
