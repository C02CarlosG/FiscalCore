import type { Declaracion, DeclaracionIn, EstadoDeclaracion, EstadoRenglon, ImpuestoDeclarado } from "@/types/api";

export const ETIQUETA_IMPUESTO: Record<ImpuestoDeclarado, string> = { iva: "IVA", isr: "ISR" };

export const ETIQUETA_ESTADO: Record<EstadoDeclaracion, string> = {
  sin_declaracion: "Sin declaración capturada",
  cuadra: "Cuadra",
  con_diferencias: "Con diferencias",
  sin_comparar: "Nada que comparar",
};

export const ETIQUETA_RENGLON: Record<EstadoRenglon, string> = {
  cuadra: "Cuadra",
  diferencia: "Diferencia",
  sin_captura: "Sin captura",
  sin_calculo: "Sin cálculo",
};

type CampoImporte = Exclude<keyof DeclaracionIn, "tipo" | "fecha_presentacion" | "numero_operacion" | "notas">;

/** Importes que se capturan por impuesto, en el orden de la declaración; `signo` = admite negativos (a favor). */
export const CAMPOS_POR_IMPUESTO: Record<ImpuestoDeclarado, { campo: CampoImporte; etiqueta: string; signo?: boolean }[]> = {
  iva: [
    { campo: "impuesto_trasladado", etiqueta: "IVA trasladado cobrado" },
    { campo: "impuesto_acreditable", etiqueta: "IVA acreditable" },
    { campo: "retenciones", etiqueta: "Retenciones de IVA a favor" },
    { campo: "retenciones_a_terceros", etiqueta: "IVA retenido a terceros por enterar" },
    { campo: "saldo_a_favor_aplicado", etiqueta: "Saldo a favor de periodos anteriores aplicado" },
    { campo: "impuesto_a_cargo", etiqueta: "IVA a cargo (+) o a favor (−)", signo: true },
    { campo: "monto_pagado", etiqueta: "Monto pagado" },
  ],
  isr: [
    { campo: "ingresos", etiqueta: "Ingresos acumulables del mes" },
    { campo: "deducciones", etiqueta: "Deducciones autorizadas del mes" },
    { campo: "retenciones", etiqueta: "ISR retenido a favor" },
    { campo: "retenciones_a_terceros", etiqueta: "ISR retenido a terceros por enterar" },
    { campo: "impuesto_a_cargo", etiqueta: "Pago provisional a cargo (+) o a favor (−)", signo: true },
    { campo: "monto_pagado", etiqueta: "Monto pagado" },
  ],
};

const IMPORTE = /^-?\d+(\.\d{1,2})?$/;

/** Texto de un importe capturado: vacío es válido (no capturado); si no, hasta dos decimales y, salvo el a cargo, sin signo. */
export function importeValido(texto: string, conSigno: boolean): boolean {
  const t = texto.trim();
  if (t === "") return true;
  return IMPORTE.test(t) && (conSigno || !t.startsWith("-"));
}

export const aTexto = (n: number | null | undefined): string => (n === null || n === undefined ? "" : String(n));

/** Valores iniciales del formulario a partir de la declaración vigente (o vacíos). */
export function valoresIniciales(impuesto: ImpuestoDeclarado, vigente: Declaracion | null): Record<string, string> {
  const v: Record<string, string> = {
    fecha_presentacion: vigente?.fecha_presentacion ?? "", numero_operacion: vigente?.numero_operacion ?? "", notas: vigente?.notas ?? "",
  };
  for (const { campo } of CAMPOS_POR_IMPUESTO[impuesto]) v[campo] = aTexto(vigente?.[campo]);
  return v;
}
