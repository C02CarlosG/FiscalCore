// Formato de fechas e importes para las tablas.
//
// Las fechas del API son ISO 8601 sin zona: son la hora local del comprobante. Se
// formatean cortando el texto, nunca con `new Date()`, porque el navegador las
// interpretaría como UTC y podría mostrar el día anterior o siguiente.

const SIN_DATO = "—";
const FECHA_RE = /^(\d{4})-(\d{2})-(\d{2})(?:T(\d{2}):(\d{2}))?/;

export function formatearFecha(iso: string | null | undefined): string {
  const m = typeof iso === "string" ? FECHA_RE.exec(iso) : null;
  return m ? `${m[3]}/${m[2]}/${m[1]}` : SIN_DATO;
}

export function formatearFechaHora(iso: string | null | undefined): string {
  const m = typeof iso === "string" ? FECHA_RE.exec(iso) : null;
  if (!m) return SIN_DATO;
  const fecha = `${m[3]}/${m[2]}/${m[1]}`;
  return m[4] === undefined ? fecha : `${fecha} ${m[4]}:${m[5]}`;
}

const dos = (n: number) => String(n).padStart(2, "0");

/**
 * Marca de tiempo del sistema (p. ej. `created_at`). Con zona (`Z` o `±hh:mm`) es un instante
 * y se muestra en la hora local del navegador; sin zona se trata como hora local del comprobante.
 */
export function formatearInstante(iso: string | null | undefined): string {
  if (typeof iso !== "string" || !FECHA_RE.test(iso)) return SIN_DATO;
  if (!/(Z|[+-]\d{2}:?\d{2})$/.test(iso)) return formatearFechaHora(iso);
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return SIN_DATO;
  return `${dos(d.getDate())}/${dos(d.getMonth() + 1)}/${d.getFullYear()} ${dos(d.getHours())}:${dos(d.getMinutes())}`;
}

const MONEDA = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" });

/** Sin dato se muestra un guion: un cero diría que hay CFDI y suman nada. */
export function formatearMoneda(valor: number | null | undefined): string {
  return typeof valor === "number" ? MONEDA.format(valor) : SIN_DATO;
}
