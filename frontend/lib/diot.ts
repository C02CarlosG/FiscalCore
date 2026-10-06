/** Catálogos y textos de la DIOT por flujo. Las claves se confirman contra el instructivo oficial del SAT (ver la spec de F6). */
export const TIPOS_TERCERO = ["04", "05", "15"] as const;
export const TIPOS_OPERACION = ["02", "03", "06", "07", "08", "85", "87"] as const;

export const ETIQUETA_TERCERO: Record<string, string> = {
  "04": "04 · Nacional",
  "05": "05 · Extranjero",
  "15": "15 · Global",
};

export const ETIQUETA_ADVERTENCIA: Record<string, string> = {
  sin_catalogo: "No está en el catálogo de proveedores",
  sin_tipo_tercero: "Falta el tipo de tercero",
  sin_tipo_operacion: "Falta el tipo de operación",
  extranjero_pendiente: "Extranjero: faltan país e ID fiscal",
  rfc_invalido: "RFC con formato inválido",
  operacion_incompatible: "La operación no corresponde al tipo de tercero",
};

export const ETIQUETA_MOTIVO_NO_ACREDITABLE: Record<string, string> = {
  efectivo: "Efectivo mayor a $2,000",
  uso_no_deducible: "Uso sin efectos fiscales",
  manual: "Excluido por el contador",
  aplicado_en_rep: "Aplicado en el REP",
  original_no_acreditable: "El original no se acreditó",
  sin_equivalencia: "Sin equivalencia",
  equivalencia_sospechosa: "Equivalencia invertida",
  sin_tipo_cambio: "Sin tipo de cambio",
  sin_proporcion: "Total en cero",
  pago_v1: "REP versión 1.0",
};

/** Renglón único de un tercero: un mismo proveedor con dos operaciones sale en dos renglones. */
export const llaveDeTercero = (t: { contraparte_rfc: string; contraparte: string; tipo_operacion: string | null }) =>
  `${t.contraparte_rfc}|${t.contraparte}|${t.tipo_operacion ?? ""}`;
