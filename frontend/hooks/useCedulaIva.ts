"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { CedulaIva } from "@/types/api";

export function useCedulaIva(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["cedula-iva", empresaId, periodo],
    queryFn: () =>
      apiFetch<CedulaIva>(`/api/v1/empresas/${empresaId}/cedula-iva/${periodo}`),
    enabled: Boolean(empresaId) && Boolean(periodo),
  });
}
