"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type {
  AgregarEmpresaRequest,
  AgregarEmpresaResponse,
  Empresa,
} from "@/types/api";

export function useEmpresas() {
  return useQuery({
    queryKey: ["empresas"],
    queryFn: () => apiFetch<Empresa[]>("/api/v1/empresas"),
  });
}

export function useCrearEmpresa() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: AgregarEmpresaRequest) =>
      apiFetch<AgregarEmpresaResponse>("/api/v1/mis-empresas", {
        method: "POST",
        body: JSON.stringify(input),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["empresas"] });
    },
  });
}
