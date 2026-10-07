export interface VistaPreviaReinicio {
  conteos: Record<string, number>;
  total_cfdi: number;
  /** Texto que hay que teclear: «REINICIAR <RFC>». */
  frase: string;
  /** Un solo uso, vale 10 minutos. */
  token: string;
  expira_en: string;
}

export interface ConfirmacionReinicio {
  token: string;
  frase: string;
  contrasena: string;
}

export interface ResultadoReinicio {
  borrados: Record<string, number>;
  sincronizacion_pausada: boolean;
}

/** Nombre legible de cada tabla que se borra (el orden es el de la spec). */
export const ETIQUETA_TABLA: Record<string, string> = {
  cfdi: "CFDI (con conceptos, impuestos, nómina y totales de pago)",
  pagos_cfdi: "Complementos de pago y sus relaciones",
  movimientos_bancarios: "Movimientos bancarios",
  conciliaciones: "Conciliaciones",
  detecciones: "Detecciones de riesgo",
  recomendaciones: "Recomendaciones",
  scoring_fiscal: "Scoring fiscal",
  periodos_procesados: "Periodos procesados",
  iva_ajustes: "Ajustes de IVA",
  isr_ajustes: "Ajustes de ISR",
  diot_operaciones_cfdi: "Clasificación DIOT por CFDI",
  diot_terceros_periodo: "DIOT por tercero y periodo",
  sat_solicitudes: "Solicitudes SAT terminadas",
};
