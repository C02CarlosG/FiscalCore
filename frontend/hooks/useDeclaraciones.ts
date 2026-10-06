"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { esPeriodoValido } from "@/lib/periodo";
import type { ComparativoDeclarado, Declaracion, DeclaracionIn, ImpuestoDeclarado } from "@/types/api";

const base = (empresaId: string) => `/api/v1/empresas/${empresaId}/declaraciones`;

/** Lo declarado contra lo calculado de IVA e ISR del periodo. */
export function useComparativoDeclarado(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["declaraciones", empresaId, periodo],
    queryFn: () => apiFetch<ComparativoDeclarado>(`${base(empresaId)}/${periodo}`),
    enabled: Boolean(empresaId) && esPeriodoValido(periodo),
    placeholderData: keepPreviousData,
  });
}

function useRefrescar(empresaId: string) {
  const queryClient = useQueryClient();
  // el pago provisional del ISR usa lo realmente pagado de las declaraciones
  return () => queryClient.invalidateQueries({ queryKey: ["declaraciones", empresaId] });
}

export function useGuardarDeclaracion(empresaId: string, periodo: string) {
  const refrescar = useRefrescar(empresaId);
  return useMutation({
    mutationFn: ({ impuesto, datos }: { impuesto: ImpuestoDeclarado; datos: DeclaracionIn }) =>
      apiFetch<Declaracion>(`${base(empresaId)}/${periodo}/${impuesto}`, { method: "PUT", body: JSON.stringify(datos) }),
    onSuccess: refrescar,
  });
}

/** Borra la vigente (la última del historial); la anterior vuelve a ser la vigente. */
export function useEliminarDeclaracion(empresaId: string, periodo: string) {
  const refrescar = useRefrescar(empresaId);
  return useMutation({
    mutationFn: (impuesto: ImpuestoDeclarado) =>
      apiFetch<void>(`${base(empresaId)}/${periodo}/${impuesto}`, { method: "DELETE" }),
    onSuccess: refrescar,
  });
}
