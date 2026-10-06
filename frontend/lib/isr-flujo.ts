// Etiquetas de la pantalla "ISR base flujo". Las marcas y motivos comunes con el IVA se reutilizan.
import type { IsrBloque, IsrLado } from "@/types/api";
import { ETIQUETA_MARCA, ETIQUETA_MOTIVO } from "./iva-flujo";

export const ETIQUETA_MARCA_ISR: Record<string, string> = {
  ...ETIQUETA_MARCA,
  efectivo_hasta_umbral: "Efectivo (revisar combustibles)",
  inversion_sin_depreciacion: "Inversión sin depreciación",
};

export const ETIQUETA_MOTIVO_ISR: Record<string, string> = {
  ...ETIQUETA_MOTIVO,
  original_no_deducible: "El original no se dedujo",
};

export type Vista = { lado: IsrLado; bloque: IsrBloque; etiqueta: string };

/** Las cifras cuyo detalle se puede abrir, en el orden en que se muestran. */
export const VISTAS_ISR: readonly Vista[] = [
  { lado: "ingreso", bloque: "contado", etiqueta: "Ingresos de contado" },
  { lado: "ingreso", bloque: "credito", etiqueta: "Ingresos cobrados a crédito" },
  { lado: "ingreso", bloque: "devoluciones", etiqueta: "Devoluciones" },
  { lado: "ingreso", bloque: "no_considerados", etiqueta: "Ingresos no considerados" },
  { lado: "deduccion", bloque: "contado", etiqueta: "Compras y gastos de contado" },
  { lado: "deduccion", bloque: "credito", etiqueta: "Compras y gastos pagados a crédito" },
  { lado: "deduccion", bloque: "devoluciones", etiqueta: "Devoluciones recibidas" },
  { lado: "deduccion", bloque: "nomina", etiqueta: "Nómina" },
  { lado: "deduccion", bloque: "inversiones", etiqueta: "Inversiones" },
  { lado: "deduccion", bloque: "no_considerados", etiqueta: "Deducciones no consideradas" },
];
