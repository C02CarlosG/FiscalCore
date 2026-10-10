"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { ApiError, apiClient } from "@/lib/api-client";
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
  const queryClient = (window as any).__tanstackQueryClient;

  const validacionesQuery = useQuery({
    queryKey: ["cierre", empresaId, periodo, "validaciones"],
    queryFn: async () => {
      const res = await apiClient.get<ListaValidaciones>(
        `/api/v1/empresas/${empresaId}/periodos/${periodo}/validaciones`
      );
      return res;
    },
  });

  const estadoQuery = useQuery({
    queryKey: ["cierre", empresaId, periodo, "estado"],
    queryFn: async () => {
      const res = await apiClient.get<EstadoCierre>(
        `/api/v1/empresas/${empresaId}/periodos/${periodo}/estado-cierre`
      );
      return res;
    },
  });

  const cerrarMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.post<{ mensaje: string }>(
        `/api/v1/empresas/${empresaId}/periodos/${periodo}/cerrar`,
        {}
      );
      return res;
    },
    onSuccess: () => {
      // Refrescar estado del cierre
      estadoQuery.refetch();
    },
  });

  const reabrirMutation = useMutation({
    mutationFn: async () => {
      const res = await apiClient.delete<{ mensaje: string }>(
        `/api/v1/empresas/${empresaId}/periodos/${periodo}/cierre`
      );
      return res;
    },
    onSuccess: () => {
      estadoQuery.refetch();
    },
  });

  const descargarPapelTrabajo = async () => {
    try {
      const archivo = await fetch(
        `/api/v1/empresas/${empresaId}/periodos/${periodo}/papel-trabajo`,
        {
          headers: {
            Authorization: `Bearer ${localStorage.getItem("token")}`,
          },
        }
      ).then((r) => r.blob());
      guardarArchivo(archivo, `papel-trabajo-${periodo}.xlsx`);
    } catch (e) {
      throw new ApiError(
        "No se pudo descargar el papel de trabajo",
        500,
        new Error("Descarga fallida")
      );
    }
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
