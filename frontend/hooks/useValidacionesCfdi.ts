"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import {
  rutaValidaciones,
  type AlcanceValidacion,
  type ClaveValidacion,
  type ConfiguracionValidaciones,
  type DireccionValidacion,
  type ListaCfdiValidacion,
  type ResumenValidaciones,
} from "@/components/validaciones/tipos";

const clave = (empresaId: string) => ["validaciones-cfdi", empresaId];

export function useResumenValidaciones(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: [...clave(empresaId), "resumen", periodo],
    queryFn: () =>
      apiFetch<ResumenValidaciones>(`${rutaValidaciones(empresaId)}?periodo=${encodeURIComponent(periodo)}`),
    enabled: Boolean(empresaId && periodo),
  });
}

export interface ConsultaCfdisValidacion {
  periodo: string;
  direccion: DireccionValidacion;
  validacion: ClaveValidacion;
  alcance: AlcanceValidacion;
}

export function useCfdisValidacion(empresaId: string, consulta: ConsultaCfdisValidacion | null) {
  return useQuery({
    queryKey: [...clave(empresaId), "cfdis", consulta],
    queryFn: () => {
      const params = new URLSearchParams({ ...(consulta as ConsultaCfdisValidacion) });
      return apiFetch<ListaCfdiValidacion>(`${rutaValidaciones(empresaId)}/cfdis?${params.toString()}`);
    },
    enabled: Boolean(empresaId && consulta),
  });
}

export function useGuardarConfiguracionValidaciones(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (config: ConfiguracionValidaciones) =>
      apiFetch<ConfiguracionValidaciones>(`${rutaValidaciones(empresaId)}/configuracion`, {
        method: "PUT",
        body: JSON.stringify(config),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: clave(empresaId) }),
  });
}
