"use client";

import { StatusBadge } from "@/components/shared/StatusBadge";
import { formatearFecha, formatearFechaHora, formatearMoneda } from "@/lib/formato";
import type { CfdiColumna, CfdiFila } from "@/types/api";

const SIN_DATO = "—";
const ENTERO = new Intl.NumberFormat("es-MX", { maximumFractionDigits: 6 });

export const alineadaALaDerecha = (columna: CfdiColumna) =>
  columna.tipo_dato === "moneda" || columna.tipo_dato === "numero";

/** Valor de una columna del catálogo con su formato (moneda, fecha, catálogo SAT...). */
export function CfdiCelda({ columna, fila }: { columna: CfdiColumna; fila: CfdiFila }) {
  const valor = fila[columna.clave];

  if (valor === null || valor === undefined) return <>{SIN_DATO}</>;

  switch (columna.tipo_dato) {
    case "moneda":
      return <>{formatearMoneda(typeof valor === "number" ? valor : null)}</>;
    case "fecha":
      return <>{formatearFecha(String(valor))}</>;
    case "fecha_hora":
      return <>{formatearFechaHora(String(valor))}</>;
    case "numero":
      return <>{typeof valor === "number" ? ENTERO.format(valor) : String(valor)}</>;
    case "booleano":
      return <>{valor ? "Sí" : "No"}</>;
    case "lista": {
      const texto = Array.isArray(valor) ? valor.join(", ") : String(valor);
      return texto ? (
        <span title={texto} className="block max-w-[18rem] truncate">{texto}</span>
      ) : (
        <>{SIN_DATO}</>
      );
    }
    case "catalogo":
      if (columna.clave === "estado" || columna.clave === "categoria") {
        return <StatusBadge status={String(valor)} />;
      }
      // El código del SAT; su descripción llega en la columna derivada `<clave>_desc`.
      return <span title={String(fila[`${columna.clave}_desc`] ?? "") || undefined}>{String(valor)}</span>;
    default:
      return <>{String(valor) || SIN_DATO}</>;
  }
}

