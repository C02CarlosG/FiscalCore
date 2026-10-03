"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { consultaApi, type CfdiEstadoUrl, type Tipo } from "@/lib/cfdi-url";
import type {
  CfdiColumnasResponse,
  CfdiListadoResponse,
  CfdiResumenResponse,
} from "@/types/api";

type Direccion = "emitidos" | "recibidos";

const base = (empresaId: string) => `/api/v1/empresas/${empresaId}/cfdis`;

/** Catálogo de columnas: casi no cambia, así que se reutiliza entre pantallas y visitas. */
export function useCfdiColumnas(empresaId: string, direccion: Direccion, tipo: Tipo) {
  return useQuery({
    queryKey: ["cfdi-columnas", empresaId, direccion, tipo],
    queryFn: () =>
      apiFetch<CfdiColumnasResponse>(`${base(empresaId)}/columnas?direccion=${direccion}&tipo=${tipo}`),
    enabled: Boolean(empresaId),
    staleTime: 5 * 60_000,
  });
}

/** Una página del listado. Mientras llega la siguiente se conserva la anterior, sin parpadeo. */
export function useCfdiListado(empresaId: string, direccion: Direccion, estado: CfdiEstadoUrl) {
  const consulta = consultaApi(estado, direccion).toString();
  return useQuery({
    queryKey: ["cfdi-listado", empresaId, consulta],
    queryFn: () => apiFetch<CfdiListadoResponse>(`${base(empresaId)}?${consulta}`),
    enabled: Boolean(empresaId) && Boolean(estado.periodo),
    placeholderData: keepPreviousData,
  });
}

/** Conteos y totales. No dependen del orden ni de la página: paginar no los vuelve a pedir. */
export function useCfdiResumen(empresaId: string, direccion: Direccion, estado: CfdiEstadoUrl) {
  const consulta = consultaApi(estado, direccion);
  for (const clave of ["orden", "dir", "pagina", "por_pagina"]) consulta.delete(clave);
  const texto = consulta.toString();
  return useQuery({
    queryKey: ["cfdi-resumen", empresaId, texto],
    queryFn: () => apiFetch<CfdiResumenResponse>(`${base(empresaId)}/resumen?${texto}`),
    enabled: Boolean(empresaId) && Boolean(estado.periodo),
    placeholderData: keepPreviousData,
  });
}
