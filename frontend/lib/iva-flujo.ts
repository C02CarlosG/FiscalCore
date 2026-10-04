// Estado de la pantalla "IVA base flujo" en la URL y textos de sus etiquetas. Como en el listado
// de CFDI, todo lo que el usuario cambia vive en la URL: recargar o compartir el enlace
// reproduce la misma vista, y los valores por defecto no se escriben.
import type { IvaDireccion, IvaOrigenDetalle } from "@/types/api";

export const VISTAS = ["trasladado", "acreditable", "a-cargo"] as const;
export type VistaIva = (typeof VISTAS)[number];

export const ORIGENES_DETALLE: readonly IvaOrigenDetalle[] = [
  "contado", "credito", "notas_credito", "no_considerados", "reasignados",
];

export type EstadoIvaUrl = { vista: VistaIva; origen: IvaOrigenDetalle; pagina: number };

export const POR_DEFECTO_IVA: EstadoIvaUrl = { vista: "trasladado", origen: "contado", pagina: 1 };

export function leerEstadoIva(params: URLSearchParams): EstadoIvaUrl {
  const vista = params.get("vista");
  const origen = params.get("origen");
  const pagina = Number(params.get("pagina"));
  return {
    vista: (VISTAS as readonly string[]).includes(vista ?? "") ? (vista as VistaIva) : POR_DEFECTO_IVA.vista,
    origen: ORIGENES_DETALLE.includes(origen as IvaOrigenDetalle) ? (origen as IvaOrigenDetalle) : POR_DEFECTO_IVA.origen,
    pagina: Number.isInteger(pagina) && pagina >= 1 ? pagina : POR_DEFECTO_IVA.pagina,
  };
}

/** Aplica un cambio a los parámetros. Cambiar de vista u origen regresa a la página 1. */
export function escribirEstadoIva(actual: URLSearchParams, parche: Partial<EstadoIvaUrl>): URLSearchParams {
  const siguiente = { ...leerEstadoIva(actual), ...parche };
  if (parche.pagina === undefined && (parche.vista !== undefined || parche.origen !== undefined)) siguiente.pagina = 1;
  const params = new URLSearchParams(actual);
  for (const clave of ["vista", "origen", "pagina"] as const) {
    params.delete(clave);
    if (siguiente[clave] !== POR_DEFECTO_IVA[clave]) params.set(clave, String(siguiente[clave]));
  }
  return params;
}

export function etiquetaOrigen(origen: IvaOrigenDetalle, direccion: IvaDireccion): string {
  switch (origen) {
    case "contado": return "Facturas de contado";
    case "credito": return direccion === "trasladado" ? "Cobro de facturas de crédito" : "Pago de facturas de crédito";
    case "notas_credito": return "Notas de crédito";
    case "no_considerados": return "No considerados";
    case "reasignados": return "Periodo reasignado";
  }
}

export const ETIQUETA_MARCA: Record<string, string> = {
  aproximado: "IVA aproximado",
  pago_v1: "REP 1.0",
  descuadre: "Descuadre con el encabezado",
  descuadre_retencion: "Retención no cuadra con el encabezado",
  retencion_sin_desglose: "Retención solo en el encabezado",
  descuadre_rep: "No cuadra con el REP",
  equivalencia_sospechosa: "Equivalencia sospechosa",
  forma_pago_rep: "Forma de pago del REP desconocida",
  sin_desglose: "Sin desglose por tasa",
  sin_equivalencia: "Sin equivalencia",
  sin_tipo_cambio: "Sin tipo de cambio",
  sin_proporcion: "Total en cero",
  anticipo: "Anticipo",
  aplicacion_anticipo: "Aplicación de anticipo",
  aplicado_en_rep: "Aplicado en el REP",
  original_no_acreditable: "Original no acreditable",
};

export const ETIQUETA_MOTIVO: Record<string, string> = {
  efectivo: "Efectivo mayor a $2,000",
  uso_no_deducible: "Uso sin efectos fiscales",
  manual: "Excluido por el contador",
  reasignado: "Reasignado a otro periodo",
  aplicado_en_rep: "Aplicado en el REP",
  original_no_acreditable: "El original no se acreditó",
  sin_equivalencia: "Sin equivalencia del documento",
  sin_tipo_cambio: "Sin tipo de cambio",
  sin_proporcion: "Total del documento en cero",
  pago_v1: "REP versión 1.0",
};

export function siguientePeriodo(periodo: string): string {
  const anio = Number(periodo.slice(0, 4));
  const mes = Number(periodo.slice(5, 7));
  return mes === 12 ? `${anio + 1}-01` : `${anio}-${String(mes + 1).padStart(2, "0")}`;
}
