"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type {
  EmitidosResponse,
  RecibidosResponse,
  VisorSatResponse,
  NominaResponse,
} from "@/types/api";

export function useEmitidos(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["cfdi-emitidos", empresaId, periodo],
    queryFn: () =>
      apiFetch<EmitidosResponse>(
        `/api/v1/empresas/${empresaId}/emitidos?periodo=${periodo}`,
      ),
    enabled: Boolean(empresaId) && Boolean(periodo),
  });
}

export function useRecibidos(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["cfdi-recibidos", empresaId, periodo],
    queryFn: () =>
      apiFetch<RecibidosResponse>(
        `/api/v1/empresas/${empresaId}/recibidos?periodo=${periodo}`,
      ),
    enabled: Boolean(empresaId) && Boolean(periodo),
  });
}

export function useVisorSat(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["cfdi-visor-sat", empresaId, periodo],
    queryFn: () =>
      apiFetch<VisorSatResponse>(
        `/api/v1/empresas/${empresaId}/cfdi/visor?periodo=${periodo}`,
      ),
    enabled: Boolean(empresaId) && Boolean(periodo),
  });
}

export function useNominaCfdi(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["cfdi-nomina", empresaId, periodo],
    queryFn: () =>
      apiFetch<NominaResponse>(
        `/api/v1/empresas/${empresaId}/cfdi/nomina?periodo=${periodo}`,
      ),
    enabled: Boolean(empresaId) && Boolean(periodo),
  });
}
