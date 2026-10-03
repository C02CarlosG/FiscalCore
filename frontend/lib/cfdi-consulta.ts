import type { DireccionCfdi, EstadoCfdi, MetodoCfdi, PagoCfdi, TipoCfdi } from "@/types/api";

export const TIPOS: { clave: TipoCfdi; etiqueta: string }[] = [
  { clave: "I", etiqueta: "Ingreso" },
  { clave: "E", etiqueta: "Egreso" },
  { clave: "T", etiqueta: "Traslado" },
  { clave: "N", etiqueta: "Nómina" },
  { clave: "P", etiqueta: "Pago" },
];
export const POR_PAGINA = [30, 50, 100] as const;

/** Estado de la pantalla de listado; todo viaja en la URL. */
export interface ConsultaCfdi {
  tipo: TipoCfdi;
  estado: EstadoCfdi;
  metodo: MetodoCfdi;
  pago: PagoCfdi;
  q: string;
  filtros: string;
  orden: string;
  dir: "asc" | "desc";
  pagina: number;
  por_pagina: number;
}

export const CONSULTA_INICIAL: ConsultaCfdi = {
  tipo: "I",
  estado: "vigente",
  metodo: "todos",
  pago: "todos",
  q: "",
  filtros: "",
  orden: "fecha_emision",
  dir: "asc",
  pagina: 1,
  por_pagina: 30,
};

function opcion<T extends string>(valor: string | null, validos: readonly T[], porDefecto: T): T {
  return validos.includes(valor as T) ? (valor as T) : porDefecto;
}

function entero(valor: string | null, porDefecto: number): number {
  const n = Number(valor);
  return Number.isInteger(n) && n >= 1 ? n : porDefecto;
}

export function leerConsulta(params: URLSearchParams): ConsultaCfdi {
  const d = CONSULTA_INICIAL;
  const metodo = opcion(params.get("metodo"), ["PUE", "PPD", "todos"] as const, d.metodo);
  const porPagina = entero(params.get("por_pagina"), d.por_pagina);
  return {
    tipo: opcion(params.get("tipo"), ["I", "E", "T", "N", "P"] as const, d.tipo),
    estado: opcion(params.get("estado"), ["vigente", "cancelado", "todos"] as const, d.estado),
    metodo,
    pago: metodo === "PPD" ? opcion(params.get("pago"), ["pendientes", "pagadas", "todos"] as const, d.pago) : "todos",
    q: params.get("q") ?? "",
    filtros: params.get("filtros") ?? "",
    orden: params.get("orden") ?? d.orden,
    dir: opcion(params.get("dir"), ["asc", "desc"] as const, d.dir),
    pagina: entero(params.get("pagina"), 1),
    por_pagina: (POR_PAGINA as readonly number[]).includes(porPagina) ? porPagina : d.por_pagina,
  };
}

/**
 * Aplica un cambio a la URL actual. Lo que no sea el periodo ni un cambio de
 * paginación vuelve a la página 1; los valores por defecto no ensucian la URL.
 */
export function actualizarParams(
  actuales: URLSearchParams,
  cambios: Partial<ConsultaCfdi>,
): URLSearchParams {
  const siguiente = { ...leerConsulta(actuales), ...cambios };
  if (!("pagina" in cambios)) siguiente.pagina = 1;
  if (siguiente.metodo !== "PPD") siguiente.pago = "todos";

  const params = new URLSearchParams(actuales.toString());
  for (const clave of Object.keys(CONSULTA_INICIAL) as (keyof ConsultaCfdi)[]) {
    const valor = siguiente[clave];
    if (valor === CONSULTA_INICIAL[clave] || valor === "") params.delete(clave);
    else params.set(clave, String(valor));
  }
  return params;
}

/** Querystring que espera `GET /cfdis` y `/cfdis/resumen`. */
export function queryDeApi(
  direccion: DireccionCfdi,
  periodo: string,
  c: ConsultaCfdi,
  conPaginacion: boolean,
): string {
  const p = new URLSearchParams({
    direccion,
    periodo,
    tipo: c.tipo,
    estado: c.estado,
    metodo: c.metodo,
    pago: c.pago,
  });
  if (c.q.trim()) p.set("q", c.q.trim());
  if (c.filtros) p.set("filtros", c.filtros);
  if (conPaginacion) {
    p.set("orden", c.orden);
    p.set("dir", c.dir);
    p.set("pagina", String(c.pagina));
    p.set("por_pagina", String(c.por_pagina));
  }
  return p.toString();
}
