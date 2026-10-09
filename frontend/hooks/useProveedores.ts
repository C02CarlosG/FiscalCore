"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type { Proveedor, ProveedorIn, ProveedorPatch, ProveedoresLista } from "@/types/api";

const base = (empresaId: string) => `/api/v1/empresas/${empresaId}/proveedores`;

/** Catálogo de proveedores. Al consultarlo el servidor agrega los emisores de los CFDI recibidos que falten. */
export function useProveedores(empresaId: string, q: string) {
  return useQuery({
    queryKey: ["proveedores", empresaId, q],
    queryFn: () => apiFetch<ProveedoresLista>(`${base(empresaId)}${q ? `?q=${encodeURIComponent(q)}` : ""}`),
    enabled: Boolean(empresaId),
    placeholderData: keepPreviousData,
  });
}

/** Un cambio en el catálogo cambia la DIOT, que lo lee. */
function useRefrescar(empresaId: string) {
  const queryClient = useQueryClient();
  return () =>
    Promise.all(
      ["proveedores", "diot-flujo"].map((clave) => queryClient.invalidateQueries({ queryKey: [clave, empresaId] })),
    );
}

export function useCrearProveedor(empresaId: string) {
  const refrescar = useRefrescar(empresaId);
  return useMutation({
    mutationFn: (datos: ProveedorIn) =>
      apiFetch<Proveedor>(base(empresaId), { method: "POST", body: JSON.stringify(datos) }),
    onSuccess: refrescar,
  });
}

export function useEditarProveedor(empresaId: string) {
  const refrescar = useRefrescar(empresaId);
  return useMutation({
    mutationFn: ({ id, cambios }: { id: string; cambios: ProveedorPatch }) =>
      apiFetch<Proveedor>(`${base(empresaId)}/${id}`, { method: "PATCH", body: JSON.stringify(cambios) }),
    onSuccess: refrescar,
  });
}
