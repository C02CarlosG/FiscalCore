"use client";

import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { DashboardData } from "@/types/api";

export function useDashboard(empresaId: string | undefined, periodo: string) {
  return useQuery({
    queryKey: ["dashboard", empresaId, periodo],
    queryFn: () =>
      apiFetch<DashboardData>(
        `/api/v1/dashboard/${empresaId}${periodo ? `?periodo=${periodo}` : ""}`,
      ),
    enabled: Boolean(empresaId),
  });
}
