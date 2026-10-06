"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "@/lib/api-client";
import type {
  Asignacion,
  AsignacionHistorial,
  CambioPlan,
  CuentaSuscripcion,
  MiSuscripcionDatos,
  Plan,
} from "@/components/suscripcion/tipos";

const BASE = "/api/v1/suscripcion";
const CLAVE = ["suscripcion"];

export function useMiSuscripcion() {
  return useQuery({ queryKey: [...CLAVE, "mia"], queryFn: () => apiFetch<MiSuscripcionDatos>(BASE) });
}

export function useMiHistorial() {
  return useQuery({
    queryKey: [...CLAVE, "historial"],
    queryFn: () => apiFetch<AsignacionHistorial[]>(`${BASE}/historial`),
  });
}

/** Historial completo de una cuenta (administrador de la plataforma); se pide al abrirlo. */
export function useHistorialCuenta(usuarioId: string, habilitado: boolean) {
  return useQuery({
    queryKey: [...CLAVE, "historial", usuarioId],
    queryFn: () => apiFetch<AsignacionHistorial[]>(`${BASE}/admin/cuentas/${usuarioId}/historial`),
    enabled: habilitado,
  });
}

export function usePlanes() {
  return useQuery({ queryKey: [...CLAVE, "planes"], queryFn: () => apiFetch<Plan[]>(`${BASE}/planes`) });
}

export function useCuentas(busqueda: string, habilitado: boolean) {
  return useQuery({
    queryKey: [...CLAVE, "cuentas", busqueda],
    queryFn: () => apiFetch<CuentaSuscripcion[]>(`${BASE}/admin/cuentas?q=${encodeURIComponent(busqueda)}`),
    enabled: habilitado,
  });
}

export function useAsignarPlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ usuarioId, asignacion }: { usuarioId: string; asignacion: Asignacion }) =>
      apiFetch<MiSuscripcionDatos>(`${BASE}/admin/cuentas/${usuarioId}`, {
        method: "PUT",
        body: JSON.stringify(asignacion),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CLAVE }),
  });
}

export function useEditarPlan() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ clave, cambio }: { clave: string; cambio: CambioPlan }) =>
      apiFetch<Plan>(`${BASE}/admin/planes/${clave}`, { method: "PUT", body: JSON.stringify(cambio) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: CLAVE }),
  });
}
