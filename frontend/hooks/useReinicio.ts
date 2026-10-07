"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { ConfirmacionReinicio, ResultadoReinicio, VistaPreviaReinicio } from "@/components/reinicio/tipos";

const ruta = (empresaId: string) => `/api/v1/reinicio/empresas/${empresaId}`;

export function usePrevisualizarReinicio(empresaId: string) {
  return useMutation({
    mutationFn: () =>
      apiFetch<VistaPreviaReinicio>(`${ruta(empresaId)}/previsualizar`, {
        method: "POST",
        body: JSON.stringify({ alcance: "todo" }),
      }),
  });
}

export function useConfirmarReinicio(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    // La contraseña viaja en las variables de la mutación: no se conserva en caché.
    gcTime: 0,
    mutationFn: (datos: ConfirmacionReinicio) =>
      apiFetch<ResultadoReinicio>(`${ruta(empresaId)}/confirmar`, { method: "POST", body: JSON.stringify(datos) }),
    // Todo lo de la empresa cambió: se descartan las consultas en caché.
    onSuccess: () => queryClient.invalidateQueries(),
  });
}
