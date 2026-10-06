"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { esPeriodoValido } from "@/lib/periodo";
import type { DiotFlujo } from "@/types/api";

const base = (empresaId: string) => `/api/v1/empresas/${empresaId}/diot-flujo`;

/** DIOT del mes por flujo: por tercero y tipo de operación. */
export function useDiotFlujo(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["diot-flujo", empresaId, periodo],
    queryFn: () => apiFetch<DiotFlujo>(`${base(empresaId)}/${periodo}`),
    enabled: Boolean(empresaId) && esPeriodoValido(periodo),
    placeholderData: keepPreviousData,
  });
}

export type ClasificacionIn = { tipo_tercero?: string | null; tipo_operacion?: string | null };

/** Cambiar la clasificación de un tercero en el periodo cambia la DIOT (y el catálogo de proveedores, que la lee). */
export function useClasificarTerceroDiot(empresaId: string, periodo: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ proveedorId, datos }: { proveedorId: string; datos: ClasificacionIn }) =>
      apiFetch<unknown>(`${base(empresaId)}/${periodo}/terceros/${proveedorId}`, { method: "PUT", body: JSON.stringify(datos) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["diot-flujo", empresaId] }),
  });
}

export function useQuitarClasificacionDiot(empresaId: string, periodo: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (proveedorId: string) =>
      apiFetch<void>(`${base(empresaId)}/${periodo}/terceros/${proveedorId}`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["diot-flujo", empresaId] }),
  });
}
