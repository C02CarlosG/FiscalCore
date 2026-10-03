import type { ColumnaCfdi } from "@/types/api";

const FECHA_ISO = /^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?/;

export function formatMoney(value: number): string {
  return value.toLocaleString("es-MX", { style: "currency", currency: "MXN" });
}

/** `2026-09-03` o `2026-09-03T10:15:00` → `03/09/2026`. Sin conversión de zona. */
export function formatFecha(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = FECHA_ISO.exec(iso);
  return m ? `${m[3]}/${m[2]}/${m[1]}` : iso;
}

/** `2026-09-03T10:15:00` → `03/09/2026 10:15`. */
export function formatFechaHora(iso: string | null | undefined): string {
  if (!iso) return "—";
  const m = FECHA_ISO.exec(iso);
  if (!m) return iso;
  return m[4] ? `${m[3]}/${m[2]}/${m[1]} ${m[4]}:${m[5]}` : `${m[3]}/${m[2]}/${m[1]}`;
}

/** Texto de una celda del listado según el tipo de dato de su columna. */
export function textoCelda(columna: Pick<ColumnaCfdi, "tipo_dato">, valor: unknown): string {
  if (valor === null || valor === undefined || valor === "") return "—";
  switch (columna.tipo_dato) {
    case "moneda":
      return formatMoney(Number(valor));
    case "fecha":
      return formatFecha(String(valor));
    case "fecha_hora":
      return formatFechaHora(String(valor));
    case "booleano":
      return valor ? "Sí" : "No";
    case "lista":
      return Array.isArray(valor) ? (valor.length ? valor.join(", ") : "—") : String(valor);
    default:
      return String(valor);
  }
}
