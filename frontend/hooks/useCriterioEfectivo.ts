"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";

export type CriterioEfectivoValor = "legal" | "estricto";

export interface CriterioEfectivoRespuesta {
  criterio_efectivo: CriterioEfectivoValor;
  umbral_efectivo: number;
}

const ruta = (empresaId: string) => `/api/v1/empresas/${empresaId}/criterio-efectivo`;

/** Todo lo que cambia con el criterio: IVA, ISR, DIOT, inicio y declaraciones de la empresa. */
const CONSULTAS_DEPENDIENTES = [
  "iva-flujo-resumen",
  "iva-flujo-detalle",
  "isr-flujo-resumen",
  "isr-flujo-detalle",
  "diot-flujo",
  "inicio-resumen",
  "inicio-iva-anual",
  "declaraciones",
];

/** Criterio de efectivo vigente de la empresa y el umbral que implica. */
export function useCriterioEfectivo(empresaId: string) {
  return useQuery({
    queryKey: ["criterio-efectivo", empresaId],
    queryFn: () => apiFetch<CriterioEfectivoRespuesta>(ruta(empresaId)),
    enabled: Boolean(empresaId),
  });
}

/** Cambia el criterio y refresca todo lo que depende de él. Solo administradores: el servidor responde 403 si no. */
export function useCambiarCriterioEfectivo(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (criterio: CriterioEfectivoValor) =>
      apiFetch<CriterioEfectivoRespuesta>(ruta(empresaId), { method: "PUT", body: JSON.stringify({ criterio }) }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["criterio-efectivo", empresaId] });
      for (const clave of CONSULTAS_DEPENDIENTES) queryClient.invalidateQueries({ queryKey: [clave, empresaId] });
    },
  });
}
