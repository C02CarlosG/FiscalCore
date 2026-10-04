"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { ColumnaPreferida } from "@/lib/columnas-preferidas";

type Respuesta = { columnas: ColumnaPreferida[] | null };

const url = (vista: string) => `/api/v1/preferencias/tablas/${vista}`;
const clave = (vista: string) => ["preferencia-tabla", vista];

/** Orden y visibilidad guardados por el usuario para una tabla; `null` si no hay. */
export function usePreferenciaTabla(vista: string) {
  return useQuery({
    queryKey: clave(vista),
    queryFn: () => apiFetch<Respuesta>(url(vista)),
    select: (r) => r.columnas,
    staleTime: 5 * 60_000,
  });
}

export function useGuardarPreferenciaTabla(vista: string) {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: (columnas: ColumnaPreferida[]) =>
      apiFetch<Respuesta>(url(vista), { method: "PUT", body: JSON.stringify({ columnas }) }),
    onSuccess: (r) => cliente.setQueryData(clave(vista), r),
  });
}

export function useRestablecerPreferenciaTabla(vista: string) {
  const cliente = useQueryClient();
  return useMutation({
    mutationFn: () => apiFetch<void>(url(vista), { method: "DELETE" }),
    onSuccess: () => cliente.setQueryData(clave(vista), { columnas: null } as Respuesta),
  });
}
