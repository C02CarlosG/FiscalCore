export const PERIODO_RE = /^20\d{2}-(0[1-9]|1[0-2])$/;

const MESES = [
  "Enero", "Febrero", "Marzo", "Abril", "Mayo", "Junio",
  "Julio", "Agosto", "Septiembre", "Octubre", "Noviembre", "Diciembre",
];

const CLAVE = (empresaId: string) => `fiscalcore.periodo.${empresaId}`;

export function esPeriodoValido(valor: string | null | undefined): valor is string {
  return Boolean(valor && PERIODO_RE.test(valor));
}

export function mesActual(hoy: Date = new Date()): string {
  return `${hoy.getFullYear()}-${String(hoy.getMonth() + 1).padStart(2, "0")}`;
}

/** `2026-09` → `2026 - Septiembre`. */
export function etiquetaPeriodo(periodo: string): string {
  if (!esPeriodoValido(periodo)) return periodo;
  const [anio, mes] = periodo.split("-");
  return `${anio} - ${MESES[Number(mes) - 1]}`;
}

/** Periodos con datos más el mes actual y el seleccionado, del más reciente al más antiguo. */
export function opcionesPeriodo(conDatos: string[], seleccionado: string): string[] {
  const todos = new Set([...conDatos, mesActual()]);
  if (esPeriodoValido(seleccionado)) todos.add(seleccionado);
  return Array.from(todos).filter(esPeriodoValido).sort().reverse();
}

export function leerPeriodoGuardado(empresaId: string): string | null {
  try {
    const valor = window.localStorage.getItem(CLAVE(empresaId));
    return esPeriodoValido(valor) ? valor : null;
  } catch {
    return null;
  }
}

export function guardarPeriodo(empresaId: string, periodo: string): void {
  try {
    window.localStorage.setItem(CLAVE(empresaId), periodo);
  } catch {
    // localStorage no disponible: el periodo solo vive en la URL.
  }
}
