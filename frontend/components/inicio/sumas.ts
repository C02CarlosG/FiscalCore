/** Suma de importes en pesos sin arrastrar error de coma flotante: se suma en centavos enteros. */
export function sumarPesos(valores: number[]): number {
  return valores.reduce((acumulado, v) => acumulado + Math.round(v * 100), 0) / 100;
}
