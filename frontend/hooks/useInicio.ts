"use client";

import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import { esPeriodoValido } from "@/lib/periodo";
import type { InicioIvaAnual, InicioResumen } from "@/types/api";

const base = (empresaId: string) => `/api/v1/empresas/${empresaId}/inicio`;

/** Ingresos y gastos del periodo y del ejercicio, y los últimos 12 meses. */
export function useInicioResumen(empresaId: string, periodo: string) {
  return useQuery({
    queryKey: ["inicio-resumen", empresaId, periodo],
    queryFn: () => apiFetch<InicioResumen>(`${base(empresaId)}/resumen?periodo=${periodo}`),
    enabled: Boolean(empresaId) && esPeriodoValido(periodo),
    placeholderData: keepPreviousData,
  });
}

/**
 * IVA del ejercicio del periodo. Se pide el ejercicio completo (sin periodo): cambiar de
 * mes dentro del mismo año reutiliza la consulta, que es la pesada; la pantalla atenúa los
 * meses posteriores al periodo elegido.
 */
export function useInicioIvaAnual(empresaId: string, periodo: string) {
  const ejercicio = esPeriodoValido(periodo) ? Number(periodo.slice(0, 4)) : null;
  return useQuery({
    queryKey: ["inicio-iva-anual", empresaId, ejercicio],
    queryFn: () => apiFetch<InicioIvaAnual>(`${base(empresaId)}/iva-anual?ejercicio=${ejercicio}`),
    enabled: Boolean(empresaId) && ejercicio !== null,
    placeholderData: keepPreviousData,
    staleTime: 60_000,
  });
}
