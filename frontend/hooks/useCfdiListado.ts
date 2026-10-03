"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { queryDeApi, type ConsultaCfdi } from "@/lib/cfdi-consulta";
import type {
  ColumnasCfdiResponse,
  DireccionCfdi,
  ListadoCfdiResponse,
  ResumenCfdiResponse,
  TipoCfdi,
} from "@/types/api";

const base = (empresaId: string) => `/api/v1/empresas/${empresaId}/cfdis`;

export function useCfdiListado(
  empresaId: string,
  direccion: DireccionCfdi,
  periodo: string,
  consulta: ConsultaCfdi,
) {
  const query = queryDeApi(direccion, periodo, consulta, true);
  return useQuery({
    queryKey: ["cfdis", empresaId, "listado", query],
    queryFn: () => apiFetch<ListadoCfdiResponse>(`${base(empresaId)}?${query}`),
    enabled: Boolean(empresaId) && Boolean(periodo),
    placeholderData: keepPreviousData,
  });
}

export function useCfdiResumen(
  empresaId: string,
  direccion: DireccionCfdi,
  periodo: string,
  consulta: ConsultaCfdi,
) {
  const query = queryDeApi(direccion, periodo, consulta, false);
  return useQuery({
    queryKey: ["cfdis", empresaId, "resumen", query],
    queryFn: () => apiFetch<ResumenCfdiResponse>(`${base(empresaId)}/resumen?${query}`),
    enabled: Boolean(empresaId) && Boolean(periodo),
    placeholderData: keepPreviousData,
  });
}

export function useCfdiColumnas(empresaId: string, direccion: DireccionCfdi, tipo: TipoCfdi) {
  return useQuery({
    queryKey: ["cfdis", empresaId, "columnas", direccion, tipo],
    queryFn: () =>
      apiFetch<ColumnasCfdiResponse>(`${base(empresaId)}/columnas?direccion=${direccion}&tipo=${tipo}`),
    enabled: Boolean(empresaId),
    staleTime: 5 * 60 * 1000,
  });
}
