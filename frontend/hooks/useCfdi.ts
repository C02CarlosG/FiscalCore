"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { EmitidosResponse, RecibidosResponse } from "@/types/api";

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
