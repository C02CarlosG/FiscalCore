"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { apiDescargar, apiFetch } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";

export interface Validacion {
  nombre: string;
  pasó: boolean;
  bloquea: boolean;
  mensaje: string;
}

export interface EstadoCierre {
  cerrado: boolean;
  cerrado_por?: string;
  fecha_cierre?: string;
  reabierto?: boolean;
  reabierto_por?: string;
  fecha_reapertura?: string;
}

export interface ListaValidaciones {
  validaciones: Validacion[];
  puede_cerrar: boolean;
}

export function useCierre(empresaId: string, periodo: string) {
  const base = `/api/v1/empresas/${empresaId}/periodos/${periodo}`;

  const validacionesQuery = useQuery({
    queryKey: ["cierre", empresaId, periodo, "validaciones"],
    queryFn: () => apiFetch<ListaValidaciones>(`${base}/validaciones`),
  });

  const estadoQuery = useQuery({
    queryKey: ["cierre", empresaId, periodo, "estado"],
    queryFn: () => apiFetch<EstadoCierre>(`${base}/estado-cierre`),
  });

  const cerrarMutation = useMutation({
    mutationFn: () =>
      apiFetch<{ mensaje: string }>(`${base}/cerrar`, { method: "POST", body: JSON.stringify({}) }),
    onSuccess: () => {
      // Refrescar estado del cierre
      estadoQuery.refetch();
    },
  });

  const reabrirMutation = useMutation({
    mutationFn: () => apiFetch<{ mensaje: string }>(`${base}/cierre`, { method: "DELETE" }),
    onSuccess: () => {
      estadoQuery.refetch();
    },
  });

  const descargarPapelTrabajo = async () => {
    const archivo = await apiDescargar(`${base}/papel-trabajo`);
    guardarArchivo(archivo, `papel-trabajo-${periodo}.xlsx`);
  };

  return {
    validaciones: validacionesQuery.data,
    isLoadingValidaciones: validacionesQuery.isLoading,
    isErrorValidaciones: validacionesQuery.isError,
    estado: estadoQuery.data,
    isLoadingEstado: estadoQuery.isLoading,
    isErrorEstado: estadoQuery.isError,
    cerrar: cerrarMutation.mutateAsync,
    isClosing: cerrarMutation.isPending,
    reabrirError: reabrirMutation.error,
    reabrir: reabrirMutation.mutateAsync,
    isReopening: reabrirMutation.isPending,
    descargarPapelTrabajo,
    refetchValidaciones: validacionesQuery.refetch,
    refetchEstado: estadoQuery.refetch,
  };
}
