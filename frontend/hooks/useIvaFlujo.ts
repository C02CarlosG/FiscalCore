"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { esPeriodoValido } from "@/lib/periodo";
import type { IvaDetalle, IvaDireccion, IvaFlujoResumen, IvaOrigenDetalle } from "@/types/api";

const base = (empresaId: string) => `/api/v1/empresas/${empresaId}/iva-flujo`;
export const POR_PAGINA_IVA = 50;

/** Resumen del IVA del mes por tasa y origen. */
export function useIvaFlujoResumen(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["iva-flujo-resumen", empresaId, periodo],
    queryFn: () => apiFetch<IvaFlujoResumen>(`${base(empresaId)}/${periodo}`),
    enabled: Boolean(empresaId) && esPeriodoValido(periodo),
    placeholderData: keepPreviousData,
  });
}

/** Una página de lo que compone una cifra. Sin dirección (vista "a cargo") no consulta. */
export function useIvaFlujoDetalle(
  empresaId: string,
  periodo: string,
  direccion: IvaDireccion | null,
  origen: IvaOrigenDetalle,
  pagina: number,
) {
  return useQuery({
    queryKey: ["iva-flujo-detalle", empresaId, periodo, direccion, origen, pagina],
    queryFn: () =>
      apiFetch<IvaDetalle>(
        `${base(empresaId)}/${periodo}/detalle?direccion=${direccion}&origen=${origen}&pagina=${pagina}&por_pagina=${POR_PAGINA_IVA}`,
      ),
    enabled: Boolean(empresaId) && esPeriodoValido(periodo) && direccion !== null,
    placeholderData: keepPreviousData,
  });
}

/** Un ajuste cambia las cifras del IVA en cualquier pantalla que las muestre. */
function useRefrescarIva(empresaId: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      ["iva-flujo-resumen", "iva-flujo-detalle", "inicio-iva-anual"].map((clave) =>
        queryClient.invalidateQueries({ queryKey: [clave, empresaId] }),
      ),
    );
}

export type AjusteIn = {
  uuid: string;
  direccion: IvaDireccion;
  accion: "excluir" | "reasignar";
  periodo_destino?: string;
  motivo: string;
};

export function useGuardarAjusteIva(empresaId: string) {
  const refrescar = useRefrescarIva(empresaId);
  return useMutation({
    mutationFn: (ajuste: AjusteIn) =>
      apiFetch<unknown>(`${base(empresaId)}/ajustes`, { method: "PUT", body: JSON.stringify(ajuste) }),
    onSuccess: refrescar,
  });
}

export function useQuitarAjusteIva(empresaId: string) {
  const refrescar = useRefrescarIva(empresaId);
  return useMutation({
    mutationFn: ({ uuid, direccion }: { uuid: string; direccion: IvaDireccion }) =>
      apiFetch<void>(`${base(empresaId)}/ajustes/${direccion}/${encodeURIComponent(uuid)}`, { method: "DELETE" }),
    onSuccess: refrescar,
  });
}
