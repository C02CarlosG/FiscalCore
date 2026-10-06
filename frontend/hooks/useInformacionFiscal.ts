"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import {
  rutaInformacionFiscal,
  type DocumentoFiscal,
  type RegimenEmpresa,
  type ResumenInformacionFiscal,
  type TipoDocumentoFiscal,
} from "@/components/informacion-fiscal/tipos";

const clave = (empresaId: string) => ["informacion-fiscal", empresaId];

export function useResumenInformacionFiscal(empresaId: string) {
  return useQuery({
    queryKey: [...clave(empresaId), "resumen"],
    queryFn: () => apiFetch<ResumenInformacionFiscal>(rutaInformacionFiscal(empresaId)),
    enabled: Boolean(empresaId),
  });
}

export function useHistorialDocumentos(empresaId: string) {
  return useQuery({
    queryKey: [...clave(empresaId), "historial"],
    queryFn: () => apiFetch<DocumentoFiscal[]>(`${rutaInformacionFiscal(empresaId)}/documentos`),
    enabled: Boolean(empresaId),
  });
}

export function useSubirDocumentoFiscal(empresaId: string, tipo: TipoDocumentoFiscal) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (archivo: File) => {
      const formData = new FormData();
      formData.append("archivo", archivo);
      return apiFetch<DocumentoFiscal>(`${rutaInformacionFiscal(empresaId)}/documentos/${tipo}`, {
        method: "POST",
        body: formData,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: clave(empresaId) });
      // Una constancia puede guardar el régimen de la empresa: ISR deja de avisar.
      if (tipo === "constancia") invalidarRegimen(queryClient, empresaId);
    },
  });
}

export function useEliminarDocumentoFiscal(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (documentoId: string) =>
      apiFetch<void>(`${rutaInformacionFiscal(empresaId)}/documentos/${documentoId}`, {
        method: "DELETE",
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: clave(empresaId) }),
  });
}

function invalidarRegimen(queryClient: ReturnType<typeof useQueryClient>, empresaId: string) {
  queryClient.invalidateQueries({ queryKey: ["isr-flujo-resumen", empresaId] });
  queryClient.invalidateQueries({ queryKey: ["empresas"] });
}

export function useRegimenEmpresa(empresaId: string) {
  return useQuery({
    queryKey: [...clave(empresaId), "regimen"],
    queryFn: () => apiFetch<RegimenEmpresa>(`${rutaInformacionFiscal(empresaId)}/regimen`),
    enabled: Boolean(empresaId),
  });
}

export function useGuardarRegimen(empresaId: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (codigo: string) =>
      apiFetch<{ actual: RegimenEmpresa["actual"] }>(`${rutaInformacionFiscal(empresaId)}/regimen`, {
        method: "PUT",
        body: JSON.stringify({ codigo }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: [...clave(empresaId), "regimen"] });
      invalidarRegimen(queryClient, empresaId);
    },
  });
}
