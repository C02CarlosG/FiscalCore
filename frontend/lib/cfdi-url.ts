// Estado del listado de CFDI en la URL. Todo lo que el usuario puede cambiar vive
// aquí, así que recargar, compartir el enlace o usar atrás y adelante reproduce la
// misma vista. Los valores por defecto no se escriben, para que la URL sea corta.

export const TIPOS = ["I", "E", "T", "N", "P"] as const;
export const ESTADOS = ["vigente", "cancelado", "todos"] as const;
export const METODOS = ["PUE", "PPD", "todos"] as const;
export const PAGOS = ["pendientes", "pagadas", "todos"] as const;
export const POR_PAGINA = [30, 50, 100] as const;

export type Tipo = (typeof TIPOS)[number];
export type EstadoCfdi = (typeof ESTADOS)[number];
export type MetodoPago = (typeof METODOS)[number];
export type PagoPpd = (typeof PAGOS)[number];

export type CfdiEstadoUrl = {
  periodo: string;
  tipo: Tipo;
  estado: EstadoCfdi;
  metodo: MetodoPago;
  pago: PagoPpd;
  q: string;
  etiqueta: string;
  filtros: string;
  orden: string;
  dir: "asc" | "desc";
  pagina: number;
  porPagina: (typeof POR_PAGINA)[number];
};

export const POR_DEFECTO: Omit<CfdiEstadoUrl, "periodo"> = {
  tipo: "I",
  estado: "vigente",
  metodo: "todos",
  pago: "todos",
  q: "",
  etiqueta: "",
  filtros: "",
  orden: "fecha_emision",
  dir: "asc",
  pagina: 1,
  porPagina: 30,
};

// Nombre del parámetro en la URL y en la API (casi todos coinciden con la clave).
const NOMBRE: Record<keyof CfdiEstadoUrl, string> = {
  periodo: "periodo",
  tipo: "tipo",
  estado: "estado",
  metodo: "metodo",
  pago: "pago",
  q: "q",
  etiqueta: "etiqueta",
  filtros: "filtros",
  orden: "orden",
  dir: "dir",
  pagina: "pagina",
  porPagina: "por_pagina",
};

const MAX_PAGINA = 100_000;
const UUID_RE = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const CLAVE_RE = /^[a-z][a-z0-9_]*$/;

function unoDe<T extends string>(opciones: readonly T[], valor: string | null, defecto: T): T {
  return opciones.includes(valor as T) ? (valor as T) : defecto;
}

function entero(valor: string | null, defecto: number): number {
  if (valor === null || !/^[1-9][0-9]*$/.test(valor)) return defecto;
  return Math.min(Number(valor), MAX_PAGINA);
}

export function leerEstado(params: URLSearchParams, periodo: string): CfdiEstadoUrl {
  const orden = params.get(NOMBRE.orden);
  const porPagina = Number(params.get(NOMBRE.porPagina));
  return {
    periodo,
    tipo: unoDe(TIPOS, params.get(NOMBRE.tipo), POR_DEFECTO.tipo),
    estado: unoDe(ESTADOS, params.get(NOMBRE.estado), POR_DEFECTO.estado),
    metodo: unoDe(METODOS, params.get(NOMBRE.metodo), POR_DEFECTO.metodo),
    pago: unoDe(PAGOS, params.get(NOMBRE.pago), POR_DEFECTO.pago),
    q: params.get(NOMBRE.q) ?? POR_DEFECTO.q,
    etiqueta: UUID_RE.test(params.get(NOMBRE.etiqueta) ?? "") ? params.get(NOMBRE.etiqueta)! : POR_DEFECTO.etiqueta,
    filtros: params.get(NOMBRE.filtros) ?? POR_DEFECTO.filtros,
    // El catálogo del servidor decide qué columnas se pueden ordenar; aquí solo se
    // descarta lo que ni siquiera tiene forma de clave de columna.
    orden: orden !== null && CLAVE_RE.test(orden) ? orden : POR_DEFECTO.orden,
    dir: unoDe(["asc", "desc"] as const, params.get(NOMBRE.dir), POR_DEFECTO.dir),
    pagina: entero(params.get(NOMBRE.pagina), POR_DEFECTO.pagina),
    porPagina: (POR_PAGINA as readonly number[]).includes(porPagina)
      ? (porPagina as CfdiEstadoUrl["porPagina"])
      : POR_DEFECTO.porPagina,
  };
}

/**
 * Aplica un parche a los parámetros actuales. Reglas:
 * - los valores por defecto se quitan de la URL;
 * - cualquier cambio que no sea solo de página regresa a la página 1;
 * - el sub-filtro de pago solo existe con método PPD;
 * - los parámetros ajenos al listado se conservan.
 */
export function escribirEstado(actual: URLSearchParams, parche: Partial<CfdiEstadoUrl>): URLSearchParams {
  const siguiente = new URLSearchParams(actual);
  const claves = Object.keys(parche) as (keyof CfdiEstadoUrl)[];

  for (const clave of claves) {
    const valor = parche[clave];
    const defecto = clave === "periodo" ? undefined : POR_DEFECTO[clave];
    if (valor === undefined || valor === defecto) siguiente.delete(NOMBRE[clave]);
    else siguiente.set(NOMBRE[clave], String(valor));
  }

  if (claves.some((c) => c !== "pagina") && parche.pagina === undefined) {
    siguiente.delete(NOMBRE.pagina);
  }

  const metodo = parche.metodo ?? unoDe(METODOS, actual.get(NOMBRE.metodo), POR_DEFECTO.metodo);
  if (metodo !== "PPD") siguiente.delete(NOMBRE.pago);

  return siguiente;
}

/** Parámetros de `GET /cfdis` y `/cfdis/resumen` (la API los ignora si no los necesita). */
export function consultaApi(estado: CfdiEstadoUrl, direccion: "emitidos" | "recibidos"): URLSearchParams {
  const consulta = new URLSearchParams({
    direccion,
    periodo: estado.periodo,
    tipo: estado.tipo,
    estado: estado.estado,
    metodo: estado.metodo,
    // El sub-filtro de pago solo aplica a PPD: con otro método la API recibe "todos".
    pago: estado.metodo === "PPD" ? estado.pago : "todos",
    orden: estado.orden,
    dir: estado.dir,
    pagina: String(estado.pagina),
    por_pagina: String(estado.porPagina),
  });
  if (estado.q) consulta.set("q", estado.q);
  if (estado.etiqueta) consulta.set("etiqueta", estado.etiqueta);
  if (estado.filtros) consulta.set("filtros", estado.filtros);
  return consulta;
}
