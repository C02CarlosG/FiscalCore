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

const MONEDA = new Intl.NumberFormat("es-MX", { style: "currency", currency: "MXN" });

/** Sin dato se muestra un guion: un cero diría que hay CFDI y suman nada. */
export function formatearMoneda(valor: number | null | undefined): string {
  return typeof valor === "number" ? MONEDA.format(valor) : SIN_DATO;
}
