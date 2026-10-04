// Periodos fiscales ("YYYY-MM") compartidos por las pantallas con periodo.

const PERIODO_RE = /^20[0-9]{2}-(0[1-9]|1[0-2])$/;
const LLAVE = "fiscalcore-periodo-";

const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

export function esPeriodoValido(periodo: string | null | undefined): periodo is string {
  return typeof periodo === "string" && PERIODO_RE.test(periodo);
}

export function periodoActual(hoy: Date = new Date()): string {
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

/** "2026-09" → "2026 - Septiembre". Un texto que no es periodo se devuelve igual. */
export function etiquetaPeriodo(periodo: string): string {
  if (!esPeriodoValido(periodo)) return periodo;
  return `${periodo.slice(0, 4)} - ${MESES[Number(periodo.slice(5)) - 1]}`;
}

/** Último periodo que se usó con esta empresa. Nunca lanza: sin localStorage devuelve null. */
export function periodoRecordado(empresaId: string): string | null {
  try {
    const guardado = window.localStorage.getItem(LLAVE + empresaId);
    return esPeriodoValido(guardado) ? guardado : null;
  } catch {
    return null;
  }
}

export function recordarPeriodo(empresaId: string, periodo: string): void {
  try {
    window.localStorage.setItem(LLAVE + empresaId, periodo);
  } catch {
    // Sin localStorage el periodo simplemente no se recuerda entre sesiones.
  }
}

/** URL válida, si no el último periodo de la empresa, si no el mes actual. */
export function resolverPeriodo({
  url,
  empresaId,
  hoy,
}: {
  url: string | null | undefined;
  empresaId: string;
  hoy?: Date;
}): string {
  if (esPeriodoValido(url)) return url;
  return periodoRecordado(empresaId) ?? periodoActual(hoy);
}
