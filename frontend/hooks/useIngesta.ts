"use client";

import { useMutation } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { IngestaResponse } from "@/types/api";

interface SubirCfdiInput {
  archivos: File[];
  periodo: string;
}

export function useSubirCfdi(empresaId: string) {
  return useMutation({
    mutationFn: (input: SubirCfdiInput) => {
      const formData = new FormData();
      for (const archivo of input.archivos) {
        formData.append("archivos", archivo);
      }
      formData.append("periodo", input.periodo);
      return apiFetch<IngestaResponse>(
        `/api/v1/empresas/${empresaId}/cfdi/upload`,
        { method: "POST", body: formData },
      );
    },
  });
}

interface SubirBancoInput {
  archivo: File;
  banco: string;
  periodo: string;
}

export function useSubirBanco(empresaId: string) {
  return useMutation({
    mutationFn: (input: SubirBancoInput) => {
      const formData = new FormData();
      formData.append("archivo", input.archivo);
      formData.append("banco", input.banco);
      formData.append("periodo", input.periodo);
      return apiFetch<IngestaResponse>(
        `/api/v1/empresas/${empresaId}/banco/upload`,
        { method: "POST", body: formData },
      );
    },
  });
}
