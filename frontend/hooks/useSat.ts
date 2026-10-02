"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type {
  FielEstado,
  SatAvanzarResponse,
  SatSolicitud,
  SatSyncResponse,
  SatTipoDescarga,
} from "@/types/api";

// Estados en los que la descarga sigue trabajando en el servidor.
const ESTADOS_EN_CURSO = ["pendiente", "solicitado", "en_proceso", "terminado"];
const INTERVALO_SEGUIMIENTO_MS = 10_000;

export function solicitudEnCurso(solicitud: SatSolicitud): boolean {
  return ESTADOS_EN_CURSO.includes(solicitud.estado);
}

export function useFielEstado(empresaId: string) {
  return useQuery({
    queryKey: ["sat-fiel", empresaId],
    queryFn: () =>
      apiFetch<FielEstado>(`/api/v1/sat/empresas/${empresaId}/fiel/estado`),
    enabled: Boolean(empresaId),
  });
}

interface GuardarFielInput {
  cer: File;
  key: File;
  password: string;
}

export function useGuardarFiel(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: GuardarFielInput) => {
      const formData = new FormData();
      formData.append("cer_file", input.cer);
      formData.append("key_file", input.key);
      formData.append("password", input.password);
      return apiFetch<unknown>(`/api/v1/sat/empresas/${empresaId}/fiel/guardar`, {
        method: "POST",
        body: formData,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sat-fiel", empresaId] });
    },
  });
}

export function useEliminarFiel(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () =>
      apiFetch<{ eliminada: boolean }>(`/api/v1/sat/empresas/${empresaId}/fiel`, {
        method: "DELETE",
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sat-fiel", empresaId] });
    },
  });
}

export function useSolicitudesSat(empresaId: string) {
  return useQuery({
    queryKey: ["sat-solicitudes", empresaId],
    queryFn: () =>
      apiFetch<SatSolicitud[]>(`/api/v1/sat/solicitudes?empresa_id=${empresaId}`),
    enabled: Boolean(empresaId),
    // Mientras haya una descarga en curso se consulta de nuevo cada 10 s.
    refetchInterval: (query) =>
      query.state.data?.some(solicitudEnCurso) ? INTERVALO_SEGUIMIENTO_MS : false,
  });
}

const INTERVALO_AVANCE_MS = 15_000;

// Mientras `activo`, pide al backend una pasada a las descargas en curso:
// verificarlas en el SAT e importarlas si ya están listas. Hace falta donde el
// backend no puede seguirlas por su cuenta (serverless). La pasada que importa
// puede tardar minutos; React Query no lanza otra mientras esa siga en vuelo.
// Si una pasada falla, el sondeo se detiene hasta que se reintente a mano.
export function useAvanzarDescargasSat(empresaId: string, activo: boolean) {
  const queryClient = useQueryClient();
  return useQuery({
    queryKey: ["sat-avanzar", empresaId],
    queryFn: async () => {
      const resultado = await apiFetch<SatAvanzarResponse>(
        `/api/v1/sat/empresas/${empresaId}/fiel/sync/avanzar`,
        { method: "POST" },
      );
      queryClient.invalidateQueries({ queryKey: ["sat-solicitudes", empresaId] });
      return resultado;
    },
    enabled: Boolean(empresaId) && activo,
    refetchInterval: (query) => (query.state.status === "error" ? false : INTERVALO_AVANCE_MS),
    retry: false,
    gcTime: 0,
  });
}

interface SincronizarInput {
  periodo: string;
  tipo: SatTipoDescarga;
}

export function useSincronizarSat(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (input: SincronizarInput) => {
      const formData = new FormData();
      formData.append("periodo", input.periodo);
      formData.append("tipo", input.tipo);
      return apiFetch<SatSyncResponse>(`/api/v1/sat/empresas/${empresaId}/fiel/sync`, {
        method: "POST",
        body: formData,
      });
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["sat-solicitudes", empresaId] });
    },
  });
}
