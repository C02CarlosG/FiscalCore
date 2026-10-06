"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { esPeriodoValido } from "@/lib/periodo";
import type { IsrBloque, IsrDetalle, IsrFlujoResumen, IsrLado } from "@/types/api";

const base = (empresaId: string) => `/api/v1/empresas/${empresaId}/isr-flujo`;
export const POR_PAGINA_ISR = 50;

/** Flujo de ISR del mes y acumulado del ejercicio. */
export function useIsrFlujoResumen(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["isr-flujo-resumen", empresaId, periodo],
    queryFn: () => apiFetch<IsrFlujoResumen>(`${base(empresaId)}/${periodo}`),
    enabled: Boolean(empresaId) && esPeriodoValido(periodo),
    placeholderData: keepPreviousData,
  });
}

/** Una página de lo que compone una cifra del mes o del acumulado. */
export function useIsrFlujoDetalle(
  empresaId: string,
  periodo: string,
  lado: IsrLado,
  bloque: IsrBloque,
  acumulado: boolean,
  pagina: number,
) {
  return useQuery({
    queryKey: ["isr-flujo-detalle", empresaId, periodo, lado, bloque, acumulado, pagina],
    queryFn: () =>
      apiFetch<IsrDetalle>(
        `${base(empresaId)}/${periodo}/detalle?lado=${lado}&bloque=${bloque}&acumulado=${acumulado}&pagina=${pagina}&por_pagina=${POR_PAGINA_ISR}`,
      ),
    enabled: Boolean(empresaId) && esPeriodoValido(periodo),
    placeholderData: keepPreviousData,
  });
}

function useRefrescarIsr(empresaId: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      ["isr-flujo-resumen", "isr-flujo-detalle"].map((clave) =>
        queryClient.invalidateQueries({ queryKey: [clave, empresaId] }),
      ),
    );
}

export function useGuardarAjusteIsr(empresaId: string) {
  const refrescar = useRefrescarIsr(empresaId);
  return useMutation({
    mutationFn: (ajuste: { uuid: string; lado: IsrLado; motivo: string }) =>
      apiFetch<unknown>(`${base(empresaId)}/ajustes`, { method: "PUT", body: JSON.stringify(ajuste) }),
    onSuccess: refrescar,
  });
}

export function useQuitarAjusteIsr(empresaId: string) {
  const refrescar = useRefrescarIsr(empresaId);
  return useMutation({
    mutationFn: ({ uuid, lado }: { uuid: string; lado: IsrLado }) =>
      apiFetch<void>(`${base(empresaId)}/ajustes/${lado}/${encodeURIComponent(uuid)}`, { method: "DELETE" }),
    onSuccess: refrescar,
  });
}

/** Porcentaje deducible de la nómina exenta (47 % o 53 %) del ejercicio. */
export function useGuardarPorcentajeNomina(empresaId: string, ejercicio: number) {
  const refrescar = useRefrescarIsr(empresaId);
  return useMutation({
    mutationFn: (pct: 0.47 | 0.53) =>
      apiFetch<unknown>(`${base(empresaId)}/config/${ejercicio}`, {
        method: "PUT",
        body: JSON.stringify({ pct_nomina_exenta: pct }),
      }),
    onSuccess: refrescar,
  });
}
