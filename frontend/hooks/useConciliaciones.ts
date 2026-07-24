"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { ConciliacionResumen, ConciliacionesAccionables } from "@/types/api";

export function useConciliacionResumen(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["conciliacion-resumen", empresaId, periodo],
    queryFn: () =>
      apiFetch<ConciliacionResumen>(
        `/api/v1/empresas/${empresaId}/conciliaciones${periodo ? `?periodo=${periodo}` : ""}`,
      ),
    enabled: Boolean(empresaId),
  });
}

export function useConciliacionesAccionables(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["conciliacion-accionables", empresaId, periodo],
    queryFn: () =>
      apiFetch<ConciliacionesAccionables>(
        `/api/v1/empresas/${empresaId}/conciliaciones/accionables${periodo ? `?periodo=${periodo}` : ""}`,
      ),
    enabled: Boolean(empresaId),
  });
}
