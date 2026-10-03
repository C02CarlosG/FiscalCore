"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { PeriodosResponse } from "@/types/api";

/** Periodos (YYYY-MM) en los que la empresa tiene CFDI, movimientos o score. */
export function usePeriodos(empresaId: string | undefined) {
  return useQuery({
    queryKey: ["periodos", empresaId],
    queryFn: () => apiFetch<PeriodosResponse>(`/api/v1/empresas/${empresaId}/periodos`),
    enabled: Boolean(empresaId),
    staleTime: 60_000,
  });
}
