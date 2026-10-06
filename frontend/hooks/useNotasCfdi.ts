"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiDescargar, apiFetch } from "@/lib/api-client";
import { guardarArchivo } from "@/lib/descarga";
import type {
  ComentarioCfdi,
  Etiqueta,
  EtiquetaCfdi,
  EtiquetadoLoteResponse,
  EvidenciaCfdi,
} from "@/types/api";

const raiz = (empresaId: string) => `/api/v1/empresas/${empresaId}`;
const cfdi = (empresaId: string, uuid: string) => `${raiz(empresaId)}/cfdis/${encodeURIComponent(uuid)}`;

/** Catálogo de etiquetas de la empresa. */
export function useEtiquetas(empresaId: string) {
  return useQuery({
    queryKey: ["etiquetas", empresaId],
    queryFn: () => apiFetch<{ items: Etiqueta[] }>(`${raiz(empresaId)}/etiquetas`).then((r) => r.items),
    enabled: Boolean(empresaId),
  });
}

/** Lo que cambia al etiquetar o comentar se ve en el listado, el catálogo y el visor. */
function useRefrescar(empresaId: string) {
  const cliente = useQueryClient();
  return () =>
    Promise.all([
      cliente.invalidateQueries({ queryKey: ["cfdi-listado", empresaId] }),
      cliente.invalidateQueries({ queryKey: ["etiquetas", empresaId] }),
      cliente.invalidateQueries({ queryKey: ["cfdi-notas", empresaId] }),
    ]);
}

export function useCrearEtiqueta(empresaId: string) {
  const refrescar = useRefrescar(empresaId);
  return useMutation({
    mutationFn: (datos: { nombre: string; color: string }) =>
      apiFetch<Etiqueta>(`${raiz(empresaId)}/etiquetas`, { method: "POST", body: JSON.stringify(datos) }),
    onSuccess: refrescar,
  });
}

export function useEtiquetarLote(empresaId: string) {
  const refrescar = useRefrescar(empresaId);
  return useMutation({
    mutationFn: (datos: { uuids: string[]; agregar?: string[]; quitar?: string[] }) =>
      apiFetch<EtiquetadoLoteResponse>(`${raiz(empresaId)}/cfdis/etiquetas/lote`, {
        method: "POST",
        body: JSON.stringify(datos),
      }),
    onSuccess: refrescar,
  });
}

export function useEtiquetasDeCfdi(empresaId: string, uuid: string) {
  return useQuery({
    queryKey: ["cfdi-notas", empresaId, uuid, "etiquetas"],
    queryFn: () => apiFetch<{ items: EtiquetaCfdi[] }>(`${cfdi(empresaId, uuid)}/etiquetas`).then((r) => r.items),
  });
}

export function useComentarios(empresaId: string, uuid: string) {
  return useQuery({
    queryKey: ["cfdi-notas", empresaId, uuid, "comentarios"],
    queryFn: () => apiFetch<{ items: ComentarioCfdi[] }>(`${cfdi(empresaId, uuid)}/comentarios`).then((r) => r.items),
  });
}

export function useCrearComentario(empresaId: string, uuid: string) {
  const refrescar = useRefrescar(empresaId);
  return useMutation({
    mutationFn: (texto: string) =>
      apiFetch<ComentarioCfdi>(`${cfdi(empresaId, uuid)}/comentarios`, { method: "POST", body: JSON.stringify({ texto }) }),
    onSuccess: refrescar,
  });
}

export function useBorrarComentario(empresaId: string, uuid: string) {
  const refrescar = useRefrescar(empresaId);
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`${cfdi(empresaId, uuid)}/comentarios/${id}`, { method: "DELETE" }),
    onSuccess: refrescar,
  });
}

export function useEvidencias(empresaId: string, uuid: string) {
  return useQuery({
    queryKey: ["cfdi-notas", empresaId, uuid, "evidencias"],
    queryFn: () => apiFetch<{ items: EvidenciaCfdi[] }>(`${cfdi(empresaId, uuid)}/evidencias`).then((r) => r.items),
  });
}

export function useSubirEvidencia(empresaId: string, uuid: string) {
  const refrescar = useRefrescar(empresaId);
  return useMutation({
    mutationFn: (archivo: File) => {
      const forma = new FormData();
      forma.append("archivo", archivo);
      return apiFetch<EvidenciaCfdi>(`${cfdi(empresaId, uuid)}/evidencias`, { method: "POST", body: forma });
    },
    onSuccess: refrescar,
  });
}

export function useBorrarEvidencia(empresaId: string, uuid: string) {
  const refrescar = useRefrescar(empresaId);
  return useMutation({
    mutationFn: (id: string) => apiFetch<void>(`${cfdi(empresaId, uuid)}/evidencias/${id}`, { method: "DELETE" }),
    onSuccess: refrescar,
  });
}

export function useDescargarEvidencia(empresaId: string, uuid: string) {
  return useMutation({
    mutationFn: async (evidencia: EvidenciaCfdi) =>
      guardarArchivo(await apiDescargar(`${cfdi(empresaId, uuid)}/evidencias/${evidencia.id}`), evidencia.nombre),
  });
}
