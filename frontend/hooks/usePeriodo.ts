"use client";

import { useCallback, useEffect } from "react";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import {
  esPeriodoValido,
  guardarPeriodo,
  leerPeriodoGuardado,
  mesActual,
} from "@/lib/periodo";

/**
 * Periodo global de la empresa. Vive en `?periodo=` para que recargar, compartir el
 * enlace y atrás/adelante reproduzcan la vista. Sin periodo en la URL se usa el
 * recordado de la empresa y, si no hay, el mes actual; hasta resolverlo devuelve "".
 */
export function usePeriodo(empresaId: string | null): [string, (periodo: string) => void] {
  const router = useRouter();
  const pathname = usePathname();
  const searchParams = useSearchParams();
  const enUrl = searchParams.get("periodo");
  const periodo = esPeriodoValido(enUrl) ? enUrl : "";

  const aplicar = useCallback(
    (nuevo: string, reemplazar: boolean) => {
      const params = new URLSearchParams(searchParams.toString());
      params.set("periodo", nuevo);
      params.delete("pagina");
      const destino = `${pathname}?${params.toString()}`;
      if (reemplazar) router.replace(destino);
      else router.push(destino);
    },
    [pathname, router, searchParams],
  );

  useEffect(() => {
    if (!empresaId || periodo) return;
    aplicar((empresaId && leerPeriodoGuardado(empresaId)) || mesActual(), true);
  }, [empresaId, periodo, aplicar]);

  useEffect(() => {
    if (empresaId && periodo) guardarPeriodo(empresaId, periodo);
  }, [empresaId, periodo]);

  const cambiar = useCallback((nuevo: string) => aplicar(nuevo, false), [aplicar]);
  return [periodo, cambiar];
}

export function usePeriodosConDatos(empresaId: string) {
  return useQuery({
    queryKey: ["periodos", empresaId],
    queryFn: () => apiFetch<{ periodos: string[] }>(`/api/v1/empresas/${empresaId}/periodos`),
    enabled: Boolean(empresaId),
    select: (data) => data.periodos,
  });
}

/** Periodo vigente solo para lectura (enlaces del menú): el de la URL o el recordado. */
export function usePeriodoParaEnlaces(empresaId: string | null): string {
  const searchParams = useSearchParams();
  const enUrl = searchParams.get("periodo");
  if (esPeriodoValido(enUrl)) return enUrl;
  return (empresaId && typeof window !== "undefined" && leerPeriodoGuardado(empresaId)) || "";
}
