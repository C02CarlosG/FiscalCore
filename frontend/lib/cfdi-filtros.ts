// Filtro avanzado del listado. En la URL y en la API es un JSON con una lista de
// {campo, op, valor}; en el editor cada renglón guarda el valor como texto y se
// convierte al tipo de la columna solo al aplicar.
import type { CfdiColumna } from "@/types/api";

export type Operador = "contiene" | "igual" | "empieza" | "mayor" | "menor" | "entre" | "en";

export const MAX_FILTROS = 10;

const NUMERICOS: Operador[] = ["igual", "mayor", "menor", "entre"];

// Mismos operadores que acepta el servidor para cada tipo de dato.
const OPERADORES: Record<CfdiColumna["tipo_dato"], Operador[]> = {
  texto: ["contiene", "igual", "empieza"],
  numero: NUMERICOS,
  moneda: NUMERICOS,
  fecha: NUMERICOS,
  fecha_hora: NUMERICOS,
  booleano: ["igual"],
  catalogo: ["igual", "en"],
  lista: [],
};

export const ETIQUETA_OPERADOR: Record<Operador, string> = {
  contiene: "contiene",
  igual: "es igual a",
  empieza: "empieza con",
  mayor: "mayor que",
  menor: "menor que",
  entre: "entre",
  en: "es uno de",
};

export const operadoresDe = (columna: CfdiColumna): Operador[] => OPERADORES[columna.tipo_dato];

export type RenglonFiltro = {
  campo: string;
  op: Operador;
  /** Texto del control; en `entre` y `en`, los valores separados por "|". */
  valor: string;
};

export const SEPARADOR = "|";

export function renglonNuevo(columna: CfdiColumna): RenglonFiltro {
  const op = operadoresDe(columna)[0];
  return { campo: columna.clave, op, valor: columna.tipo_dato === "booleano" ? "true" : "" };
}

/** Cambiar de campo o de operador descarta el valor: ya no significa lo mismo. */
export function renglonConOperador(r: RenglonFiltro, op: Operador): RenglonFiltro {
  return { ...r, op, valor: "" };
}

function convertir(columna: CfdiColumna, texto: string): string | number | boolean | null {
  if (columna.tipo_dato === "booleano") return texto === "true";
  if (columna.tipo_dato === "numero" || columna.tipo_dato === "moneda") {
    if (texto.trim() === "") return null;
    const n = Number(texto);
    return Number.isFinite(n) ? n : null;
  }
  const limpio = texto.trim();
  return limpio === "" ? null : limpio;
}

/** Un renglón está completo si todos sus valores son válidos para el tipo de la columna. */
export function renglonCompleto(r: RenglonFiltro, columna: CfdiColumna | undefined): boolean {
  if (!columna || !operadoresDe(columna).includes(r.op)) return false;
  const partes = r.op === "entre" || r.op === "en" ? r.valor.split(SEPARADOR) : [r.valor];
  if (r.op === "entre" && partes.length !== 2) return false;
  if (r.op === "en" && partes.every((p) => p === "")) return false;
  return partes.filter((p) => r.op !== "en" || p !== "").every((p) => convertir(columna, p) !== null);
}

/** JSON para la URL. Vacío si no hay renglones. Solo se llama con renglones completos. */
export function serializarFiltros(renglones: RenglonFiltro[], catalogo: CfdiColumna[]): string {
  const porClave = new Map(catalogo.map((c) => [c.clave, c]));
  const filtros = renglones.map((r) => {
    const columna = porClave.get(r.campo)!;
    let valor: unknown;
    if (r.op === "entre") valor = r.valor.split(SEPARADOR).map((p) => convertir(columna, p));
    else if (r.op === "en") valor = r.valor.split(SEPARADOR).filter((p) => p !== "");
    else valor = convertir(columna, r.valor);
    return { campo: r.campo, op: r.op, valor };
  });
  return filtros.length ? JSON.stringify(filtros) : "";
}

/** Lee el JSON de la URL de vuelta a renglones. Lo que no se entienda se descarta. */
export function leerFiltros(json: string): RenglonFiltro[] {
  if (!json) return [];
  let crudo: unknown;
  try {
    crudo = JSON.parse(json);
  } catch {
    return [];
  }
  if (!Array.isArray(crudo)) return [];
  return crudo.flatMap((f): RenglonFiltro[] => {
    if (!f || typeof f !== "object" || typeof f.campo !== "string" || typeof f.op !== "string") return [];
    const { campo, op, valor } = f as { campo: string; op: Operador; valor: unknown };
    const texto = Array.isArray(valor) ? valor.map(String).join(SEPARADOR) : String(valor ?? "");
    return [{ campo, op, valor: texto }];
  });
}

/** Cuántos filtros de la URL siguen siendo válidos para el catálogo actual. */
export function contarActivos(json: string, catalogo: CfdiColumna[] | undefined): number {
  const claves = new Set((catalogo ?? []).filter((c) => c.filtrable).map((c) => c.clave));
  return leerFiltros(json).filter((r) => claves.has(r.campo)).length;
}
