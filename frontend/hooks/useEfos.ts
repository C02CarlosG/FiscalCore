"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { EfosEstado } from "@/types/api";

/** Estado de la lista 69-B: fecha del archivo del SAT, antigüedad y último intento de importación. */
export function useEfosEstado() {
  return useQuery({ queryKey: ["efos-estado"], queryFn: () => apiFetch<EfosEstado>("/api/v1/efos/estado") });
}

function useRefrescar() {
  const cliente = useQueryClient();
  return () => {
    cliente.invalidateQueries({ queryKey: ["efos-estado"] });
    for (const k of ["cfdi-listado", "cfdi-resumen", "proveedores"]) cliente.invalidateQueries({ queryKey: [k] });
  };
}

/** Descarga la lista del SAT ahora (solo administradores de la plataforma). */
export function useImportarEfos() {
  const refrescar = useRefrescar();
  return useMutation({
    mutationFn: () => apiFetch<unknown>("/api/v1/admin/efos/importar", { method: "POST" }),
    onSuccess: refrescar,
  });
}

/** Sube un CSV de la lista a mano (solo administradores de la plataforma). */
export function useSubirEfos() {
  const refrescar = useRefrescar();
  return useMutation({
    mutationFn: (archivo: File) => {
      const datos = new FormData();
      datos.append("archivo", archivo);
      return apiFetch<unknown>("/api/v1/admin/efos/subir", { method: "POST", body: datos });
    },
    onSuccess: refrescar,
  });
}
